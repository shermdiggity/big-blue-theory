"""Ticket 13: every 4th down and 2-point try, and how often the league goes for it there."""

from __future__ import annotations

import polars as pl

from bbt import config

GO = ["pass", "run"]
KICK = ["punt", "field_goal"]


def _dist_bucket() -> pl.Expr:
    return (pl.when(pl.col("ydstogo") <= 1).then(pl.lit("1"))
            .when(pl.col("ydstogo") <= 3).then(pl.lit("2-3"))
            .when(pl.col("ydstogo") <= 5).then(pl.lit("4-5"))
            .when(pl.col("ydstogo") <= 10).then(pl.lit("6-10"))
            .otherwise(pl.lit("11+")).alias("dist_bucket"))


def _field_bucket() -> pl.Expr:
    """yardline_100 in bands: own half is split coarser than opponent territory."""
    return (pl.when(pl.col("yardline_100") <= 5).then(pl.lit("opp 1-5"))
            .when(pl.col("yardline_100") <= 20).then(pl.lit("opp 6-20"))
            .when(pl.col("yardline_100") <= 35).then(pl.lit("opp 21-35"))
            .when(pl.col("yardline_100") <= 50).then(pl.lit("opp 36-50"))
            .when(pl.col("yardline_100") <= 70).then(pl.lit("own 30-49"))
            .otherwise(pl.lit("own 1-29")).alias("field_bucket"))


def _fourth_downs(plays: pl.DataFrame) -> pl.DataFrame:
    """Real 4th-down decisions. Penalty no-plays and kneels aren't decisions."""
    return plays.filter(
        (pl.col("down") == 4) & pl.col("play_type").is_in(GO + KICK)
        & (pl.col("qb_kneel").fill_null(0) == 0)
    ).with_columns(
        pl.col("play_type").is_in(GO).alias("went_for_it"),
        _dist_bucket(), _field_bucket(),
    )


def league_go_rates(baseline: pl.DataFrame) -> pl.DataFrame:
    """Go-for-it rate by distance x field bucket, excluding the last 5 min of the game
    and blowouts, where the decision is forced by the score."""
    fd = _fourth_downs(baseline).filter(
        (pl.col("game_seconds_remaining") > 300) & (pl.col("score_differential").abs() <= 16)
    )
    return fd.group_by("dist_bucket", "field_bucket").agg(
        pl.len().alias("league_n"), pl.col("went_for_it").mean().alias("league_go_rate"),
    )


def fourth_downs(game: pl.DataFrame, baseline: pl.DataFrame, team: str = config.TEAM) -> pl.DataFrame:
    fd = _fourth_downs(game).filter(pl.col("posteam") == team)
    rates = league_go_rates(baseline)
    return fd.join(rates, on=["dist_bucket", "field_bucket"], how="left").with_columns(
        pl.col("play_type").replace({"pass": "go (pass)", "run": "go (run)",
                                     "punt": "punt", "field_goal": "FG"}).alias("decision"),
        (pl.col("wp") * 100).round(1).alias("wp_before"),
        ((pl.col("wp") + pl.col("wpa")) * 100).round(1).alias("wp_after"),
        pl.when(pl.col("went_for_it"))
        .then(pl.when(pl.col("fourth_down_converted") == 1).then(pl.lit("converted"))
              .otherwise(pl.lit("failed")))
        .when(pl.col("play_type") == "field_goal").then(pl.col("field_goal_result"))
        .otherwise(pl.lit("")).alias("result"),
    ).select(
        "qtr", "time", "ydstogo", "yardline_100", "score_differential", "decision", "result",
        "wp_before", "wp_after", "dist_bucket", "field_bucket", "league_go_rate", "league_n", "desc",
    )


def two_point_tries(game: pl.DataFrame, team: str = config.TEAM) -> pl.DataFrame:
    """2-point tries, plus XPs so you can see the choice after every TD."""
    tries = game.filter(
        (pl.col("posteam") == team)
        & ((pl.col("two_point_attempt") == 1) | (pl.col("extra_point_attempt") == 1))
    )
    return tries.select(
        "qtr", "time", "score_differential",
        pl.when(pl.col("two_point_attempt") == 1).then(pl.lit("2-pt")).otherwise(pl.lit("XP"))
        .alias("choice"),
        pl.coalesce("two_point_conv_result", "extra_point_result").alias("result"),
        (pl.col("wp") * 100).round(1).alias("wp_before"),
        ((pl.col("wp") + pl.col("wpa")) * 100).round(1).alias("wp_after"),
        "desc",
    )
