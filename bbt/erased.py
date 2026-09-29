"""Ticket 7: points erased by penalties.

For each wiped play, find real plays that look like it: same down, similar distance,
similar field position, same kind of play and a similar result (gain, INT, sack,
incompletion). Their average EPA is roughly what the erased play was worth.

Scores don't need comparables. In nflverse a touchdown is always worth exactly 7 EP and a
made field goal exactly 3, so an erased TD is worth `7 - ep` and an erased FG `3 - ep`.

Sign convention: every `*_to_penalized` number is from the penalized team's point of view.
`erased_ep_to_penalized` > 0 means the flag took away something good for the team that
committed it (a holding call that wiped a 20-yard run). < 0 means the flag wiped something
bad for them (defensive offside that wiped their own sack is good for the offense, bad for
the defense that jumped).

Total cost of a wiped-play flag vs "no flag, play stands":
    cost = erased_ep_to_penalized - flag_epa_to_penalized
"""

from __future__ import annotations

import polars as pl

MIN_COMPARABLES = 15


def _comparable_pool(baseline: pl.DataFrame) -> pl.DataFrame:
    """Clean run/pass plays with a real outcome."""
    return baseline.filter(
        pl.col("play_type").is_in(["pass", "run"])
        & (pl.col("penalty").fill_null(0) == 0)
        & pl.col("epa").is_not_null()
        & pl.col("down").is_not_null()
    ).select(
        "down", "ydstogo", "yardline_100", "yards_gained", "epa", "pass", "touchdown",
        "interception", "sack", "incomplete_pass", "fumble_lost",
    )


def _match(pool: pl.DataFrame, row: dict, dist_tol: float, yl_tol: float) -> pl.DataFrame:
    is_pass = row["erased_kind"] == "pass"
    c = pool.filter(
        (pl.col("down") == row["down"])
        & ((pl.col("ydstogo") - row["ydstogo"]).abs() <= dist_tol)
        & ((pl.col("yardline_100") - row["yardline_100"]).abs() <= yl_tol)
        & (pl.col("pass") == (1 if is_pass else 0))
    )
    if row["erased_td"]:
        return c.filter(pl.col("touchdown") == 1)
    if row["erased_int"]:
        return c.filter(pl.col("interception") == 1)
    if row["erased_fumble"]:
        return c.filter(pl.col("fumble_lost") == 1)
    if row["erased_incomplete"]:
        return c.filter(pl.col("incomplete_pass") == 1)
    gain = row["erased_gain"]
    if gain is None:
        return c.clear()
    gain_tol = max(1, round(abs(gain) * 0.15))
    c = c.filter(
        (pl.col("touchdown") == 0) & (pl.col("interception") == 0) & (pl.col("fumble_lost") == 0)
        & ((pl.col("yards_gained") - gain).abs() <= gain_tol)
    )
    return c.filter(pl.col("sack") == (1 if row["erased_sack"] else 0))


def estimate(led: pl.DataFrame, baseline: pl.DataFrame) -> pl.DataFrame:
    """Add erased EP estimates to every wiped scrimmage play in the ledger."""
    pool = _comparable_pool(baseline)
    wiped = led.filter(
        (pl.col("kind") == "wiped") & pl.col("down").is_not_null()
        & (pl.col("erased_kind").is_in(["pass", "run"]) | pl.col("erased_fg_good"))
    )
    out = []
    for row in wiped.iter_rows(named=True):
        est, n, how = None, 0, None
        if row["erased_td"] and row["ep"] is not None:
            est, how = 7 - row["ep"], "exact: TD = 7 - ep"
        elif row["erased_fg_good"] and row["ep"] is not None:
            est, how = 3 - row["ep"], "exact: FG = 3 - ep"
        # Otherwise start tight and widen until there are enough comparables.
        for dist_tol, yl_tol in ([] if est is not None else [(1, 5), (2, 8), (3, 12), (5, 20)]):
            m = _match(pool, row, dist_tol, yl_tol)
            if m.height >= MIN_COMPARABLES:
                est, n, how = m["epa"].mean(), m.height, f"dist±{dist_tol} yl±{yl_tol}"
                break
        out.append({"game_id": row["game_id"], "play_id": row["play_id"],
                    "erased_epa_off": est, "n_comparables": n, "match": how})
    est_df = pl.DataFrame(out, schema={"game_id": pl.Utf8, "play_id": pl.Float64,
                                       "erased_epa_off": pl.Float64, "n_comparables": pl.Int64,
                                       "match": pl.Utf8})
    res = led.join(est_df, on=["game_id", "play_id"], how="left")
    pen_is_off = pl.col("penalty_team") == pl.col("posteam")
    return res.with_columns(
        pl.when(pen_is_off).then(pl.col("erased_epa_off")).otherwise(-pl.col("erased_epa_off"))
        .alias("erased_ep_to_penalized"),
    ).with_columns(
        (pl.col("erased_ep_to_penalized").fill_null(0) - pl.col("flag_epa_to_penalized"))
        .alias("total_cost_to_penalized"),
    )


def team_totals(est: pl.DataFrame, by_game: bool = False) -> pl.DataFrame:
    """Per penalized team (optionally per game): EP erased and the total cost of flags.

    `ep_erased` sums the erased value of wiped plays (net). `ep_erased_gains` counts only
    the plays that were good for the penalized team: the "stuff you lost" number.
    """
    keys = ["penalty_team", "game_id"] if by_game else ["penalty_team"]
    credited = est.filter(pl.col("kind").is_in(["pre_snap", "wiped"]))
    return (
        credited.group_by(keys)
        .agg(
            (pl.col("kind") == "wiped").sum().alias("wiped_plays"),
            (pl.col("kind") == "pre_snap").sum().alias("pre_snap_flags"),
            (pl.col("erased_ep_to_penalized") > 0).sum().alias("wiped_good_plays"),
            (pl.col("erased_td") & (pl.col("pen_side") == "offense")).sum().alias("tds_wiped"),
            pl.col("erased_ep_to_penalized").sum().alias("ep_erased"),
            pl.col("erased_ep_to_penalized").filter(pl.col("erased_ep_to_penalized") > 0).sum()
            .alias("ep_erased_gains"),
            pl.col("total_cost_to_penalized").sum().alias("total_ep_cost"),
            pl.col("wpa_to_penalized").sum().alias("wpa_to_penalized"),
        )
        .with_columns(
            pl.col("ep_erased").rank("ordinal", descending=True).alias("rank_ep_erased")
            if not by_game else pl.lit(None).alias("rank_ep_erased"),
            pl.col("total_ep_cost").rank("ordinal", descending=True).alias("rank_total_cost")
            if not by_game else pl.lit(None).alias("rank_total_cost"),
        )
        .sort(keys if by_game else "ep_erased", descending=not by_game)
        .rename({"penalty_team": "team"})
    )


def headline(totals: pl.DataFrame, team: str) -> str:
    row = totals.filter(pl.col("team") == team)
    if row.is_empty():
        return f"No wiped plays or pre-snap flags on {team} yet."
    r = row.row(0, named=True)
    n = totals.height
    return (
        f"{team} penalties have erased {r['ep_erased']:.1f} expected points of plays "
        f"({_ordinal(r['rank_ep_erased'])} most of {n} teams), and all their pre-snap + "
        f"wiped-play flags have cost {r['total_ep_cost']:.1f} EP in total "
        f"({_ordinal(r['rank_total_cost'])} most)."
    )


def _ordinal(n: int) -> str:
    n = int(n)
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
