"""Load nflverse data into one local DuckDB file and read it back as polars.

Tables:
  pbp        play-by-play, current season + baseline seasons
  ftn        FTN charting (lands a few days after each game)
  snaps      snap counts
  schedules  schedule + final scores
  players    player id crosswalk (gsis <-> pfr)
View:
  plays      pbp LEFT JOIN ftn on game id + play id
"""

from __future__ import annotations

import time

import duckdb
import nflreadpy as nfl
import polars as pl

from bbt import config


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(config.DB_PATH), read_only=read_only)


def _try(loader, seasons):
    """FTN/snap data for a brand-new season can be missing; don't crash the refresh."""
    try:
        return loader(seasons)
    except Exception as exc:  # noqa: BLE001 - nflreadpy raises plain Exceptions
        print(f"  ! {loader.__name__}({seasons}) failed: {exc}")
        return None


def refresh(season: int = config.SEASON, include_baseline: bool = True) -> None:
    """Re-download from nflverse and rebuild every table. Safe to run any time."""
    seasons = sorted(set(([*config.BASELINE_SEASONS] if include_baseline else []) + [season]))
    t0 = time.time()
    con = connect()

    pbp = nfl.load_pbp(seasons)
    ftn = _try(nfl.load_ftn_charting, seasons)
    snaps = _try(nfl.load_snap_counts, [season])
    schedules = nfl.load_schedules([season])
    players = nfl.load_players().select(
        "gsis_id", "pfr_id", "display_name", "short_name", "position", "latest_team"
    )

    for name, df in [("pbp", pbp), ("ftn", ftn), ("snaps", snaps),
                     ("schedules", schedules), ("players", players)]:
        if df is None:
            continue
        con.register("_df", df.to_arrow())
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _df")
        con.unregister("_df")
        print(f"  {name:<10} {df.height:>7,} rows")

    _create_plays_view(con, has_ftn=ftn is not None)
    con.close()
    print(f"  refreshed seasons {seasons} in {time.time() - t0:.0f}s")


def _create_plays_view(con, has_ftn: bool) -> None:
    if not has_ftn:
        con.execute("CREATE OR REPLACE VIEW plays AS SELECT *, false AS has_ftn FROM pbp")
        return
    # FTN play id is an integer, pbp play_id is a float -> cast before joining.
    con.execute(
        """
        CREATE OR REPLACE VIEW plays AS
        SELECT p.*,
               f.nflverse_play_id IS NOT NULL AS has_ftn,
               f.starting_hash, f.qb_location, f.n_offense_backfield, f.n_defense_box,
               f.is_no_huddle, f.is_motion, f.is_play_action, f.is_screen_pass, f.is_rpo,
               f.is_trick_play, f.is_qb_out_of_pocket, f.is_interception_worthy,
               f.is_throw_away, f.read_thrown, f.is_catchable_ball, f.is_contested_ball,
               f.is_created_reception, f.is_drop, f.is_qb_sneak, f.n_blitzers,
               f.n_pass_rushers, f.is_qb_fault_sack
        FROM pbp p
        LEFT JOIN ftn f
          ON p.game_id = f.nflverse_game_id
         AND CAST(p.play_id AS INTEGER) = f.nflverse_play_id
        """
    )


def ensure_db() -> None:
    if not config.DB_PATH.exists():
        print("No local database yet, loading from nflverse (one time, ~1 min)...")
        refresh()


def query(sql: str, params: list | None = None) -> pl.DataFrame:
    ensure_db()
    con = connect(read_only=True)
    try:
        return con.execute(sql, params or []).pl()
    finally:
        con.close()


def season_plays(season: int = config.SEASON) -> pl.DataFrame:
    return query("SELECT * FROM plays WHERE season = ? ORDER BY game_id, play_id", [season])


def baseline_plays() -> pl.DataFrame:
    """Every loaded season (baseline + current). Used for comparables."""
    return query("SELECT * FROM pbp ORDER BY game_id, play_id")


def schedule(season: int = config.SEASON) -> pl.DataFrame:
    return query("SELECT * FROM schedules WHERE season = ? ORDER BY week", [season])


def game_id_for(week: int, team: str = config.TEAM, season: int = config.SEASON) -> str:
    sched = schedule(season).filter(
        (pl.col("week") == week) & ((pl.col("home_team") == team) | (pl.col("away_team") == team))
    )
    if sched.is_empty():
        raise SystemExit(f"{team} has no game in week {week} of {season} (bye week?)")
    return sched["game_id"][0]


def opponent_for(week: int, team: str = config.TEAM, season: int = config.SEASON) -> str:
    row = schedule(season).filter(
        (pl.col("week") == week) & ((pl.col("home_team") == team) | (pl.col("away_team") == team))
    ).row(0, named=True)
    return row["away_team"] if row["home_team"] == team else row["home_team"]


def game_plays(game_id: str) -> pl.DataFrame:
    return query("SELECT * FROM plays WHERE game_id = ? ORDER BY play_id", [game_id])


def table(name: str, where: str = "", params: list | None = None) -> pl.DataFrame:
    return query(f"SELECT * FROM {name} {where}", params)
