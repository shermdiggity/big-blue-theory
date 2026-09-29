"""Ticket 14: next opponent's tendencies and the weekly "watch for" scorecard.

A tendency is a rate like "early-down pass rate" measured for one team over a set of games.
`tendencies()` ranks the opponent's rates by how far they sit from the league (z-score
across teams), so the one that stands out floats to the top.

The scorecard logs one prediction a week as `metric over/under line`, and grades it
automatically after the game using the same metric definitions.
"""

from __future__ import annotations

import csv
from datetime import date

import polars as pl

from bbt import config

FTN = pl.col("has_ftn").fill_null(False)
DROPBACK = pl.col("pass") == 1

# name -> (label, side, filter on run/pass plays, value expression)
METRICS: dict[str, tuple[str, str, pl.Expr, pl.Expr]] = {
    "pass_rate_early": ("Pass rate, 1st & 2nd down", "offense", pl.col("down") <= 2, pl.col("pass")),
    "pass_rate_1st10": ("Pass rate, 1st & 10", "offense",
                        (pl.col("down") == 1) & (pl.col("ydstogo") == 10), pl.col("pass")),
    "pass_rate_short": ("Pass rate, 3rd/4th & 1-3", "offense",
                        (pl.col("down") >= 3) & (pl.col("ydstogo") <= 3), pl.col("pass")),
    "proe": ("Pass rate over expected", "offense", pl.lit(True), pl.col("pass_oe") / 100),
    "shotgun": ("Shotgun rate", "offense", pl.lit(True), pl.col("shotgun")),
    "no_huddle": ("No-huddle rate", "offense", pl.lit(True), pl.col("no_huddle")),
    "motion": ("Motion rate (FTN)", "offense", FTN, pl.col("is_motion").cast(pl.Float64)),
    "play_action": ("Play-action rate on dropbacks (FTN)", "offense", FTN & DROPBACK,
                    pl.col("is_play_action").cast(pl.Float64)),
    "screen": ("Screen rate on dropbacks (FTN)", "offense", FTN & DROPBACK,
               pl.col("is_screen_pass").cast(pl.Float64)),
    "rpo": ("RPO rate (FTN)", "offense", FTN, pl.col("is_rpo").cast(pl.Float64)),
    "deep_rate": ("Deep throw rate (air yards 20+)", "offense", pl.col("air_yards").is_not_null(),
                  (pl.col("air_yards") >= 20).cast(pl.Float64)),
    "rz_run_rate": ("Run rate inside the 20", "offense", pl.col("yardline_100") <= 20, pl.col("rush")),
    "off_epa": ("Offense EPA/play", "offense", pl.lit(True), pl.col("epa")),
    "def_blitz": ("Blitz rate on dropbacks (FTN)", "defense", FTN & DROPBACK,
                  (pl.col("n_blitzers") > 0).cast(pl.Float64)),
    "def_box8": ("8+ man box rate vs runs (FTN)", "defense", FTN & (pl.col("rush") == 1),
                 (pl.col("n_defense_box") >= 8).cast(pl.Float64)),
    "def_rush5": ("5+ pass rushers rate (FTN)", "defense", FTN & DROPBACK,
                  (pl.col("n_pass_rushers") >= 5).cast(pl.Float64)),
    "def_sack_rate": ("Sack rate (defense)", "defense", DROPBACK, pl.col("sack")),
    "def_epa": ("Defense EPA/play allowed", "defense", pl.lit(True), pl.col("epa")),
}


def _run_pass(plays: pl.DataFrame) -> pl.DataFrame:
    return plays.filter(pl.col("play_type").is_in(["pass", "run"]) & pl.col("epa").is_not_null())


def team_metric(plays: pl.DataFrame, team: str, metric: str) -> tuple[float | None, int]:
    _, side, filt, value = METRICS[metric]
    col = "posteam" if side == "offense" else "defteam"
    sub = _run_pass(plays).filter((pl.col(col) == team) & filt)
    if sub.is_empty():
        return None, 0
    return sub.select(value.mean()).item(), sub.height


def all_teams(plays: pl.DataFrame, metric: str) -> pl.DataFrame:
    _, side, filt, value = METRICS[metric]
    col = "posteam" if side == "offense" else "defteam"
    return (_run_pass(plays).filter(filt).group_by(col)
            .agg(value.mean().alias("value"), pl.len().alias("n")).rename({col: "team"}))


def tendencies(season: pl.DataFrame, team: str, through_week: int) -> pl.DataFrame:
    """Every metric for `team` through `through_week`, vs league mean/spread, sorted by |z|."""
    plays = season.filter(pl.col("week") <= through_week)
    rows = []
    for key, (label, side, _, _) in METRICS.items():
        teams = all_teams(plays, key).filter(pl.col("value").is_not_null())
        me = teams.filter(pl.col("team") == team)
        if me.is_empty() or teams.height < 5:
            continue
        v, n = me["value"][0], me["n"][0]
        mean, sd = teams["value"].mean(), teams["value"].std()
        rank = int((teams["value"] > v).sum()) + 1
        rows.append({"metric": key, "label": label, "side": side, "value": v, "n": n,
                     "league": mean, "z": (v - mean) / sd if sd else 0.0,
                     "rank": rank, "of": teams.height})
    return pl.DataFrame(rows).with_columns(pl.col("z").abs().alias("_abs")).sort(
        "_abs", descending=True).drop("_abs") if rows else pl.DataFrame()


def by_down_distance(season: pl.DataFrame, team: str, through_week: int) -> pl.DataFrame:
    """Pass rate and EPA by down and distance bucket, team vs league."""
    rp = _run_pass(season.filter(pl.col("week") <= through_week)).filter(pl.col("down").is_not_null())
    rp = rp.with_columns(
        (pl.when(pl.col("ydstogo") <= 3).then(pl.lit("1-3"))
         .when(pl.col("ydstogo") <= 6).then(pl.lit("4-6"))
         .when(pl.col("ydstogo") <= 10).then(pl.lit("7-10"))
         .otherwise(pl.lit("11+"))).alias("dist"),
        pl.col("down").cast(pl.Int32),
    )
    lg = rp.group_by("down", "dist").agg(pl.col("pass").mean().alias("league_pass_rate"))
    tm = rp.filter(pl.col("posteam") == team).group_by("down", "dist").agg(
        pl.len().alias("plays"), pl.col("pass").mean().alias("pass_rate"),
        pl.col("epa").mean().alias("epa_play"), pl.col("success").mean().alias("success"))
    order = {"1-3": 0, "4-6": 1, "7-10": 2, "11+": 3}
    return (tm.join(lg, on=["down", "dist"], how="left")
            .sort("down", pl.col("dist").replace_strict(order, return_dtype=pl.Int8)))


# --------------------------------------------------------------------------- scorecard

SCORECARD_FIELDS = ["season", "week", "opponent", "logged", "prediction", "metric", "direction",
                    "line", "actual", "grade", "note"]


def read_scorecard() -> list[dict]:
    if not config.SCORECARD_PATH.exists():
        return []
    with config.SCORECARD_PATH.open() as f:
        return list(csv.DictReader(f))


def write_scorecard(rows: list[dict]) -> None:
    with config.SCORECARD_PATH.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SCORECARD_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in SCORECARD_FIELDS})


def log_prediction(week: int, opponent: str, prediction: str, metric: str, direction: str,
                   line: float, season: int = config.SEASON) -> dict:
    if metric not in METRICS:
        raise SystemExit(f"Unknown metric {metric!r}. Options: {', '.join(METRICS)}")
    if direction not in ("over", "under"):
        raise SystemExit("direction must be 'over' or 'under'")
    rows = [r for r in read_scorecard() if not (r["season"] == str(season) and r["week"] == str(week))]
    row = {"season": season, "week": week, "opponent": opponent, "logged": date.today().isoformat(),
           "prediction": prediction, "metric": metric, "direction": direction, "line": line}
    rows.append(row)
    rows.sort(key=lambda r: (int(r["season"]), int(r["week"])))
    write_scorecard(rows)
    return row


def grade(week: int, game: pl.DataFrame, season: int = config.SEASON) -> dict | None:
    """Grade that week's prediction from the opponent's plays in that game."""
    rows = read_scorecard()
    for r in rows:
        if r["season"] == str(season) and r["week"] == str(week):
            actual, n = team_metric(game, r["opponent"], r["metric"])
            if actual is None:
                r["grade"], r["note"] = "no data", r.get("note", "")
            else:
                hit = actual > float(r["line"]) if r["direction"] == "over" else actual < float(r["line"])
                r["actual"] = round(actual, 4)
                r["grade"] = "HIT" if hit else "MISS"
                r["note"] = r.get("note") or f"n={n} plays"
            write_scorecard(rows)
            return r
    return None
