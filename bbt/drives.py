"""Ticket 3: drive-by-drive game flow."""

from __future__ import annotations

import polars as pl

# Plays that belong to the offense's possession (kickoffs belong to the kicking unit,
# and nflverse sometimes folds the opening kickoff into the next fixed_drive).
SCRIMMAGE = ["pass", "run", "no_play", "qb_kneel", "qb_spike", "punt", "field_goal"]
OFFENSE = ["pass", "run", "no_play", "qb_kneel", "qb_spike"]


def drive_table(game: pl.DataFrame) -> pl.DataFrame:
    """One row per possession, matching the official drive chart.

    Official fields (`drive_play_count`, `ydsnet`, `drive_time_of_possession`) come from the
    NFL feed; `off_epa` is our own sum over offensive snaps (penalty snaps included,
    special teams excluded).
    """
    plays = game.filter(pl.col("play_type").is_in(SCRIMMAGE) & pl.col("posteam").is_not_null())
    drives = (
        plays.sort("play_id")
        .group_by("fixed_drive", maintain_order=True)
        .agg(
            pl.col("posteam").first().alias("team"),
            pl.col("qtr").first().alias("qtr"),
            pl.col("time").first().alias("start_time"),
            pl.col("drive_start_yard_line").drop_nulls().last().alias("start"),
            pl.col("yardline_100").first().alias("start_yl100"),
            pl.col("drive_play_count").drop_nulls().last().cast(pl.Int32).alias("plays"),
            pl.col("ydsnet").drop_nulls().last().cast(pl.Int32).alias("yards"),
            pl.col("drive_time_of_possession").drop_nulls().last().alias("top"),
            pl.col("epa").filter(pl.col("play_type").is_in(OFFENSE)).sum().alias("off_epa"),
            pl.col("fixed_drive_result").drop_nulls().last().alias("result"),
            pl.col("drive_first_downs").drop_nulls().last().cast(pl.Int32).alias("first_downs"),
        )
        .sort("fixed_drive")
        .with_columns(pl.int_range(1, pl.len() + 1).alias("n"))
    )
    return drives.select(
        "n", "team", "qtr", "start_time", "start", "plays", "yards", "top",
        "first_downs", "off_epa", "result", "start_yl100", "fixed_drive",
    )


def drive_summary(drives: pl.DataFrame) -> pl.DataFrame:
    """Per team: drives, points-scoring drives, yards per drive, EPA per drive."""
    return (
        drives.group_by("team")
        .agg(
            pl.len().alias("drives"),
            pl.col("result").is_in(["Touchdown", "Field goal"]).sum().alias("scoring"),
            (pl.col("result") == "Touchdown").sum().alias("tds"),
            pl.col("yards").mean().round(1).alias("yds_per_drive"),
            pl.col("off_epa").mean().round(2).alias("epa_per_drive"),
            (100 - pl.col("start_yl100")).mean().round(1).alias("avg_start_own_yl"),
        )
        .sort("team")
    )
