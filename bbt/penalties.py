"""Ticket 6: the penalty ledger.

Every accepted penalty goes into one of three kinds:
  pre_snap  nothing happened but the flag (false start, delay of game, encroachment...)
  wiped     a play happened and was erased ("No Play"). What it was worth is in erased.py.
  added     the play stood and the penalty yards were added on

Offsetting penalties that wiped a play are listed as `offsetting` and credited to nobody.

Win probability is only credited to the penalty for pre_snap and wiped plays. On an `added`
play the wpa mixes the play itself with the flag, so it's left blank.
"""

from __future__ import annotations

import re

import polars as pl

PENALTY_SPLIT = re.compile(r"\bpenalty on\b", re.IGNORECASE)
CLOCK = re.compile(r"^\(\s*\d*:\d{2}\s*\)")
PAREN = re.compile(r"^\((?:[^()]*formation[^()]*|[^()]*shotgun[^()]*|[^()]*no huddle[^()]*|aborted)\)",
                   re.IGNORECASE)
# Pre-snap announcements that aren't a play ("79-L.Borom reported in as eligible.")
NOISE = re.compile(r"^(?:.*?reported in as eligible\.?|\*\* ?injury update:.*?(?:game|field)\.|timeout #\d+ by [A-Z]{2,3} at \d+:\d\d\.)\s*",
                   re.IGNORECASE)
GAIN = re.compile(r"\bfor (-?\d+) yards?\b")
NO_GAIN = re.compile(r"\bfor no gain\b")


def pre_penalty_text(desc: str) -> str:
    """The part of the play text before the first 'PENALTY on', minus clock/formation noise."""
    text = PENALTY_SPLIT.split(desc or "", maxsplit=1)[0].strip()
    text = CLOCK.sub("", text).strip()
    while True:
        new = PAREN.sub("", text).strip()
        new = NOISE.sub("", new).strip()
        if new == text:
            break
        text = new
    return text


def parse_erased(pre: str) -> dict:
    """What the wiped play would have been: kind, gain, TD / INT / sack / fumble flags."""
    low = pre.lower()
    if re.search(r"\bpunts\b", low):
        kind = "punt"
    elif re.search(r"\bkicks\b", low):
        kind = "kickoff"
    elif "field goal" in low:
        kind = "field_goal"
    elif "extra point" in low:
        kind = "extra_point"
    elif re.search(r"\b(pass|sacked|scrambles|spiked)\b", low):
        kind = "pass"
    elif re.search(r"\b(left|right) (end|tackle|guard)\b|\bup the middle\b|\bkneels\b|\brushes\b", low):
        kind = "run"
    else:
        kind = "other"

    m = GAIN.search(pre)
    if m:
        gain = int(m.group(1))
    elif NO_GAIN.search(pre) or "incomplete" in low:
        gain = 0
    else:
        gain = None

    return {
        "erased_kind": kind,
        "erased_gain": gain,
        "erased_td": "touchdown" in low,
        "erased_int": "intercepted" in low,
        "erased_sack": "sacked" in low,
        "erased_incomplete": "incomplete" in low,
        "erased_fumble": "fumbles" in low,
        "erased_fg_good": "field goal is good" in low,
    }


def classify(desc: str, play_type: str | None) -> str:
    low = (desc or "").lower()
    no_play = play_type == "no_play" or "no play" in low
    if "offsetting" in low and no_play:
        return "offsetting"
    if not no_play:
        return "added"
    return "wiped" if pre_penalty_text(desc) else "pre_snap"


def ledger(plays: pl.DataFrame) -> pl.DataFrame:
    """One row per accepted penalty (plus offsetting no-plays), classified and parsed."""
    pens = plays.filter(
        (pl.col("penalty") == 1)
        | (pl.col("desc").str.contains("(?i)offsetting") & (pl.col("play_type") == "no_play"))
    )
    if pens.is_empty():
        return pens.with_columns(pl.lit(None).alias("kind"))

    rows = []
    for r in pens.select("game_id", "play_id", "desc", "play_type").iter_rows(named=True):
        kind = classify(r["desc"], r["play_type"])
        pre = pre_penalty_text(r["desc"])
        parsed = parse_erased(pre) if kind in ("wiped", "offsetting") else parse_erased("")
        if kind not in ("wiped", "offsetting"):
            parsed = {k: None for k in parsed}
        rows.append({"game_id": r["game_id"], "play_id": r["play_id"], "kind": kind,
                     "erased_text": pre if kind in ("wiped", "offsetting") else None, **parsed})
    parsed_df = pl.DataFrame(rows, schema_overrides={
        "erased_gain": pl.Int64, "erased_td": pl.Boolean, "erased_int": pl.Boolean,
        "erased_sack": pl.Boolean, "erased_incomplete": pl.Boolean, "erased_fumble": pl.Boolean,
        "erased_fg_good": pl.Boolean,
        "erased_kind": pl.Utf8, "erased_text": pl.Utf8,
    })

    out = pens.join(parsed_df, on=["game_id", "play_id"], how="left")
    pen_is_off = pl.col("penalty_team") == pl.col("posteam")
    credited = pl.col("kind").is_in(["pre_snap", "wiped"])
    return out.with_columns(
        pl.when(pen_is_off).then(pl.lit("offense")).otherwise(pl.lit("defense")).alias("pen_side"),
        # From the penalized team's point of view (negative = the flag hurt them)
        pl.when(credited).then(pl.when(pen_is_off).then(pl.col("wpa")).otherwise(-pl.col("wpa")))
        .alias("wpa_to_penalized"),
        pl.when(credited).then(pl.when(pen_is_off).then(pl.col("epa")).otherwise(-pl.col("epa")))
        .alias("flag_epa_to_penalized"),
    ).select(
        "game_id", "week", "play_id", "qtr", "time", "posteam", "defteam", "down", "ydstogo",
        "yardline_100", "penalty_team", "pen_side", "penalty_player_name", "penalty_type",
        "penalty_yards", "kind", "erased_kind", "erased_gain", "erased_td", "erased_int",
        "erased_sack", "erased_incomplete", "erased_fumble", "erased_fg_good", "erased_text",
        "ep", "wpa", "epa", "wpa_to_penalized", "flag_epa_to_penalized", "desc",
    ).sort("game_id", "play_id")


def team_summary(led: pl.DataFrame, team: str) -> pl.DataFrame:
    """Counts and yards by kind, for flags on `team` and flags on its opponents."""
    return (
        led.filter(pl.col("kind") != "offsetting")
        .with_columns(pl.when(pl.col("penalty_team") == team).then(pl.lit(team))
                      .otherwise(pl.lit("opponent")).alias("on"))
        .group_by("on", "kind")
        .agg(pl.len().alias("flags"), pl.col("penalty_yards").sum().alias("yards"),
             # null for "added" flags: that wpa belongs to the play, not the penalty
             pl.col("wpa_to_penalized").sum().alias("wpa_to_penalized"))
        .with_columns(pl.when(pl.col("kind") == "added").then(None)
                      .otherwise(pl.col("wpa_to_penalized")).alias("wpa_to_penalized"))
        .sort("on", "kind")
    )


def hidden_offense_cost(plays: pl.DataFrame, team: str) -> pl.DataFrame:
    """Offense EPA/play with and without penalty snaps.

    Most efficiency numbers only count real run/pass plays, so pre-snap and wiped-play
    penalties quietly vanish. This shows how much they change the picture.
    """
    off = plays.filter((pl.col("posteam") == team) & pl.col("epa").is_not_null()
                       & pl.col("play_type").is_in(["pass", "run", "no_play"]))
    return off.group_by("game_id").agg(
        pl.col("epa").filter(pl.col("play_type") != "no_play").mean().alias("epa_play_run_pass_only"),
        pl.col("epa").mean().alias("epa_play_incl_penalty_snaps"),
        (pl.col("play_type") == "no_play").sum().alias("penalty_snaps"),
        pl.col("epa").filter(pl.col("play_type") == "no_play").sum().alias("epa_on_penalty_snaps"),
    ).sort("game_id")
