"""Ticket 12: per-player table for one game.

Snap counts come from PFR (full names, pfr ids). Play-by-play uses gsis ids.
The `players` table bridges them.
"""

from __future__ import annotations

import polars as pl

from bbt import config, data


def _usage(game: pl.DataFrame, team: str) -> pl.DataFrame:
    """Targets, carries, dropbacks, EPA and success per gsis id, offense only."""
    rp = game.filter(pl.col("play_type").is_in(["pass", "run"]) & (pl.col("posteam") == team))
    frames = []
    for role, id_col, name_col, filt in [
        ("passer", "passer_player_id", "passer_player_name", pl.col("pass") == 1),
        ("target", "receiver_player_id", "receiver_player_name", pl.col("pass") == 1),
        ("carry", "rusher_player_id", "rusher_player_name", pl.col("rush") == 1),
    ]:
        f = rp.filter(filt & pl.col(id_col).is_not_null()).group_by(id_col).agg(
            pl.col(name_col).first().alias("name"),
            pl.len().alias(f"{role}s"),
            pl.col("epa").sum().alias(f"{role}_epa"),
            pl.col("success").mean().alias(f"{role}_success"),
            *([pl.col("air_yards").filter(pl.col("air_yards") >= 20).len().alias("deep_targets"),
               pl.col("complete_pass").sum().alias("catches"),
               pl.col("receiving_yards").sum().alias("rec_yards")] if role == "target" else []),
            *([pl.col("rushing_yards").sum().alias("rush_yards")] if role == "carry" else []),
            *([pl.col("passing_yards").sum().alias("pass_yards"),
               pl.col("sack").sum().alias("sacks_taken"),
               pl.col("interception").sum().alias("ints")] if role == "passer" else []),
        ).rename({id_col: "gsis_id"})
        frames.append(f)
    out = frames[0]
    for f in frames[1:]:
        out = out.join(f, on="gsis_id", how="full", coalesce=True, suffix="_r")
        if "name_r" in out.columns:
            out = out.with_columns(pl.coalesce("name", "name_r").alias("name")).drop("name_r")
    return out


def _penalties(game: pl.DataFrame, team: str) -> pl.DataFrame:
    return (
        game.filter((pl.col("penalty") == 1) & (pl.col("penalty_team") == team)
                    & pl.col("penalty_player_id").is_not_null())
        .group_by("penalty_player_id")
        .agg(pl.len().alias("penalties"), pl.col("penalty_yards").sum().alias("penalty_yards"),
             pl.col("penalty_player_name").first().alias("name"))
        .rename({"penalty_player_id": "gsis_id"})
    )


def player_table(game_id: str, team: str = config.TEAM) -> pl.DataFrame:
    game = data.game_plays(game_id)
    snaps = data.table("snaps", "WHERE game_id = ? AND team = ?", [game_id, team])
    xwalk = data.table("players").select("gsis_id", "pfr_id", "display_name", "position")

    usage = _usage(game, team).join(_penalties(game, team), on="gsis_id", how="full",
                                    coalesce=True, suffix="_pen")
    usage = usage.with_columns(pl.coalesce("name", "name_pen").alias("name")).drop("name_pen")

    if snaps.is_empty():
        base = usage.join(xwalk, on="gsis_id", how="left")
        base = base.with_columns(pl.lit(None, pl.Int64).alias("offense_snaps"),
                                 pl.lit(None, pl.Int64).alias("defense_snaps"),
                                 pl.lit(None, pl.Int64).alias("st_snaps"))
    else:
        s = snaps.select("pfr_player_id", pl.col("player").alias("snap_name"), "position",
                         "offense_snaps", "offense_pct", "defense_snaps", "defense_pct", "st_snaps")
        s = s.join(xwalk.select("gsis_id", "pfr_id"), left_on="pfr_player_id", right_on="pfr_id", how="left")
        base = s.join(usage, on="gsis_id", how="full", coalesce=True)
        base = base.join(xwalk.select("gsis_id", "display_name"), on="gsis_id", how="left")

    name = pl.coalesce([c for c in ["display_name", "snap_name", "name"] if c in base.columns])
    cols = ["player", "position", "offense_snaps", "offense_pct", "defense_snaps", "defense_pct",
            "st_snaps", "passers", "passer_epa", "pass_yards", "sacks_taken", "ints",
            "targets", "catches", "rec_yards", "deep_targets", "target_epa", "target_success",
            "carrys", "rush_yards", "carry_epa", "carry_success", "penalties", "penalty_yards",
            "gsis_id"]
    base = base.with_columns(name.alias("player"))
    for c in cols:
        if c not in base.columns:
            base = base.with_columns(pl.lit(None).alias(c))
    return (
        base.select(cols)
        .rename({"passers": "dropbacks", "carrys": "carries"})
        .sort(pl.coalesce(pl.col("offense_snaps"), pl.lit(0)) + pl.coalesce(pl.col("defense_snaps"), pl.lit(0)),
              descending=True)
    )
