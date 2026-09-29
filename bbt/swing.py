"""Ticket 4: the plays that swung win probability, from one team's point of view."""

from __future__ import annotations

import polars as pl

from bbt import config


def team_wpa(game: pl.DataFrame, team: str = config.TEAM) -> pl.DataFrame:
    """Add `team_wpa`: wpa is from the offense's view, so flip it when `team` is on defense."""
    return game.filter(pl.col("wpa").is_not_null() & pl.col("posteam").is_not_null()).with_columns(
        pl.when(pl.col("posteam") == team).then(pl.col("wpa")).otherwise(-pl.col("wpa")).alias("team_wpa"),
        pl.when(pl.col("posteam") == team).then(pl.col("wp")).otherwise(1 - pl.col("wp")).alias("team_wp"),
        (pl.col("posteam") == team).alias("team_on_offense"),
    )


def swing_plays(game: pl.DataFrame, team: str = config.TEAM, n: int = 10) -> pl.DataFrame:
    return (
        team_wpa(game, team)
        .with_columns(pl.col("team_wpa").abs().alias("abs_wpa"))
        .sort("abs_wpa", descending=True)
        .head(n)
        .select(
            "qtr", "time", "posteam", "down", "ydstogo", "yardline_100", "play_type",
            (pl.col("team_wp") * 100).round(1).alias("wp_before"),
            (pl.col("team_wpa") * 100).round(1).alias("wpa_pts"),
            "desc", "play_id",
        )
    )


def wp_timeline(game: pl.DataFrame, team: str = config.TEAM) -> pl.DataFrame:
    """Team win probability after every play (for the chart)."""
    home = game["home_team"][0]
    return (
        game.filter(pl.col("home_wp_post").is_not_null())
        .select(
            "play_id", "qtr", "game_seconds_remaining",
            (pl.col("home_wp_post") if home == team else 1 - pl.col("home_wp_post")).alias("team_wp"),
        )
        .with_columns((3600 - pl.col("game_seconds_remaining")).alias("elapsed"))
    )
