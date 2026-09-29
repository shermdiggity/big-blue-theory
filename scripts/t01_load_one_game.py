"""Ticket 1: load one Giants game straight from nflverse and print every play.

    python scripts/t01_load_one_game.py 2026_03_TEN_NYG

Read each `desc` next to its columns. That's how you learn what the columns mean.
The columns worth keeping are listed in docs/columns.md.
"""

import sys

import nflreadpy as nfl
import polars as pl

GAME_ID = sys.argv[1] if len(sys.argv) > 1 else "2026_03_TEN_NYG"
SEASON = int(GAME_ID[:4])

COLS = ["qtr", "time", "posteam", "down", "ydstogo", "yardline_100", "play_type",
        "yards_gained", "epa", "wpa", "desc"]

pbp = nfl.load_pbp([SEASON])
game = pbp.filter(pl.col("game_id") == GAME_ID)

pl.Config.set_tbl_rows(-1)
pl.Config.set_fmt_str_lengths(160)
pl.Config.set_tbl_width_chars(260)
pl.Config.set_float_precision(2)

print(f"{GAME_ID}: {game.height} rows")
print(game.select(COLS))
