"""Ticket 5: this game's gameplan vs the team's own norms vs the league.

Offense rates use real run and pass plays only (no penalties, kneels, spikes or special teams).
FTN rates (motion, play action, blitz) are null until FTN publishes the game.
"""

from __future__ import annotations

import polars as pl

from bbt import config


def _run_pass(plays: pl.DataFrame) -> pl.DataFrame:
    return plays.filter(pl.col("play_type").is_in(["pass", "run"]) & pl.col("epa").is_not_null())


def _ftn_rate(flag: str) -> pl.Expr:
    """Share of FTN-charted plays with this flag. Null if nothing is charted yet."""
    charted = pl.col("has_ftn").fill_null(False)
    return pl.col(flag).filter(charted).cast(pl.Float64).mean()


OFFENSE_METRICS: dict[str, tuple[str, pl.Expr]] = {
    "plays": ("Run + pass plays", pl.len().cast(pl.Float64)),
    "pass_rate": ("Pass rate", pl.col("pass").mean()),
    "proe": ("Pass rate over expected", pl.col("pass_oe").mean() / 100),
    "early_down_pass": ("Early-down pass rate (1st/2nd)",
                        pl.col("pass").filter(pl.col("down") <= 2).mean()),
    "shotgun": ("Shotgun rate", pl.col("shotgun").mean()),
    "no_huddle": ("No-huddle rate", pl.col("no_huddle").mean()),
    "motion": ("Motion rate (FTN)", _ftn_rate("is_motion")),
    "play_action": ("Play-action rate, dropbacks (FTN)",
                    pl.col("is_play_action").filter(pl.col("has_ftn").fill_null(False)
                                                     & (pl.col("pass") == 1)).cast(pl.Float64).mean()),
    "success": ("Success rate", pl.col("success").mean()),
    "epa": ("EPA per play", pl.col("epa").mean()),
    "epa_pass": ("EPA per dropback", pl.col("epa").filter(pl.col("pass") == 1).mean()),
    "epa_run": ("EPA per designed run", pl.col("epa").filter(pl.col("rush") == 1).mean()),
    "adot": ("Avg depth of target",
             pl.col("air_yards").filter(pl.col("air_yards").is_not_null()).mean()),
}

DEFENSE_METRICS: dict[str, tuple[str, pl.Expr]] = {
    "epa": ("EPA per play allowed", pl.col("epa").mean()),
    "success": ("Success rate allowed", pl.col("success").mean()),
    "sack_rate": ("Sack rate", pl.col("sack").filter(pl.col("pass") == 1).mean()),
    "blitz": ("Blitz rate, dropbacks (FTN)",
              (pl.col("n_blitzers") > 0).filter(pl.col("has_ftn").fill_null(False)
                                                & (pl.col("pass") == 1)).cast(pl.Float64).mean()),
    "box": ("Avg men in box (FTN)",
            pl.col("n_defense_box").filter(pl.col("has_ftn").fill_null(False)).cast(pl.Float64).mean()),
    "rushers": ("Avg pass rushers (FTN)",
                pl.col("n_pass_rushers").filter(pl.col("has_ftn").fill_null(False)
                                                & (pl.col("pass") == 1)).cast(pl.Float64).mean()),
}


def _summarise(df: pl.DataFrame, metrics: dict) -> dict[str, float | None]:
    if df.is_empty():
        return {k: None for k in metrics}
    row = df.select([expr.alias(k) for k, (_, expr) in metrics.items()]).row(0, named=True)
    return row


def compare(season: pl.DataFrame, game_id: str, team: str = config.TEAM,
            side: str = "offense") -> pl.DataFrame:
    """Three columns: this game, team's earlier games this season, league through this week."""
    week = season.filter(pl.col("game_id") == game_id)["week"][0]
    rp = _run_pass(season.filter(pl.col("week") <= week))
    team_col = "posteam" if side == "offense" else "defteam"
    metrics = OFFENSE_METRICS if side == "offense" else DEFENSE_METRICS

    this = _summarise(rp.filter((pl.col("game_id") == game_id) & (pl.col(team_col) == team)), metrics)
    prior = _summarise(rp.filter((pl.col("week") < week) & (pl.col(team_col) == team)), metrics)
    league = _summarise(rp, metrics)
    # "plays" is a count: show it per game, not summed over the sample
    if "plays" in metrics:
        per_game = rp.group_by("game_id", "posteam", "week").len()
        prior_games = per_game.filter((pl.col("week") < week) & (pl.col("posteam") == team))
        prior["plays"] = prior_games["len"].mean() if prior_games.height else None
        league["plays"] = per_game["len"].mean()

    rows = []
    for key, (label, _) in metrics.items():
        rows.append({
            "metric": key, "label": label, "this_game": this[key],
            f"{team}_prior": prior[key], "league": league[key],
        })
    df = pl.DataFrame(rows, schema={"metric": pl.Utf8, "label": pl.Utf8, "this_game": pl.Float64,
                                    f"{team}_prior": pl.Float64, "league": pl.Float64})
    return df.with_columns((pl.col("this_game") - pl.col(f"{team}_prior")).alias("vs_prior"))


def biggest_changes(cmp: pl.DataFrame, team: str = config.TEAM, n: int = 3) -> pl.DataFrame:
    """Rates that moved most vs the team's own norm, scaled by the league value so rates compare."""
    rates = cmp.filter(~pl.col("metric").is_in(["plays", "epa", "epa_pass", "epa_run", "adot", "box", "rushers"]))
    return (
        rates.filter(pl.col("vs_prior").is_not_null())
        .with_columns(pl.col("vs_prior").abs().alias("_abs"))
        .sort("_abs", descending=True)
        .head(n)
        .drop("_abs")
    )
