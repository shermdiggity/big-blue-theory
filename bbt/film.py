"""The week's clip list: every play the analysis points at, with an NFL Pro Film Room link.

Plays come from two places, automatically:
  - the biggest win-probability swings
  - any "Q3 2:30"-style reference in your verdicts or SūmerBrain's answers
The NFL Pro prompt asks the extension to open each one in Film Room and copy its link.
Links land in the extract as nfl_pro.film_links and show up in the notes doc.

These links play for anyone logged into NFL+ Premium. They're for your own study and for
subscribers; NFL video can't be re-uploaded to a public post.
"""

from __future__ import annotations

import csv
import json
import re

import polars as pl

from bbt import config, data, paid, swing

CLOCK_REF = re.compile(r"\bQ([1-5])\s+(\d{1,2}):(\d{2})\b")
MAX_CLIPS = 14


def _refs(text: str) -> list[tuple[int, str]]:
    return [(int(q), f"{int(m):02d}:{s}") for q, m, s in CLOCK_REF.findall(text or "")]


def clip_list(week: int, team: str = config.TEAM) -> pl.DataFrame:
    game_id = data.game_id_for(week, team)
    game = data.game_plays(game_id).filter(pl.col("desc").is_not_null() & pl.col("qtr").is_not_null())
    wanted: dict[tuple[int, str], str] = {}   # insertion order = priority
    swings = list(swing.swing_plays(game, team, n=5).iter_rows(named=True))
    for r in swings[:3]:   # the three biggest swings always make it
        wanted.setdefault((int(r["qtr"]), r["time"]), f"swing play ({r['wpa_pts']:+.0f} WP pts)")
    vpath = config.NOTES_DIR / f"{config.week_tag(week)}_verdicts.csv"
    if vpath.exists():
        for r in csv.DictReader(vpath.open()):
            text = r.get("comment", "") + " " + r.get("sumerbrain", "")
            for ref in _refs(text):
                wanted.setdefault(ref, f"{r['who']}: {r['what'][:50]}")
    for r in swings[3:]:
        wanted.setdefault((int(r["qtr"]), r["time"]), f"swing play ({r['wpa_pts']:+.0f} WP pts)")

    plays = game.filter(pl.col("play_type").is_in(["pass", "run", "no_play", "punt", "field_goal", "kickoff"]))
    rows = []
    for (q, t), why in wanted.items():
        hit = plays.filter((pl.col("qtr") == q) & (pl.col("time") == t))
        if hit.is_empty():
            continue
        p = hit.row(0, named=True)
        dn = f"{int(p['down'])}&{int(p['ydstogo'])}" if p["down"] is not None else ""
        rows.append({"play": f"Q{q} {t}", "qtr": q, "time": t, "down": dn, "why": why,
                     "desc": re.sub(r"^\(\d+:\d+\)\s*", "", p["desc"])[:150]})
    df = pl.DataFrame(rows, schema={"play": pl.Utf8, "qtr": pl.Int64, "time": pl.Utf8, "down": pl.Utf8,
                                    "why": pl.Utf8, "desc": pl.Utf8})
    # keep the highest-priority plays, then show them in game order
    return df.head(MAX_CLIPS).sort(["qtr", "time"], descending=[False, True])


def links(week: int) -> dict[str, str]:
    ext = paid.load(week) or {}
    out = {}
    for item in ((ext.get("nfl_pro") or {}).get("film_links") or []):
        if item.get("url"):
            out[_norm(item.get("play", ""))] = item["url"]
    return out


def _norm(play: str) -> str:
    refs = _refs(play)
    return f"Q{refs[0][0]} {refs[0][1]}" if refs else play.strip()


def render(week: int) -> str:
    clips = clip_list(week)
    if clips.is_empty():
        return ""
    lk = links(week)
    lines = ["\n## Clips to watch\n",
             "_NFL Pro Film Room → Game: this game. ▶ links work for anyone logged into NFL+ Premium._\n"]
    for r in clips.iter_rows(named=True):
        url = lk.get(r["play"])
        head = f"[▶ {r['play']}]({url})" if url else f"**{r['play']}**"
        lines.append(f"- {head} {r['down']} · {r['desc']}  \n  _why: {r['why']}_\n")
    if not lk:
        lines.append("\n_No Film Room links yet: they come back with the NFL Pro reply._\n")
    return "".join(lines)


def prompt_block(week: int) -> str:
    clips = clip_list(week)
    if clips.is_empty():
        return ""
    plays = "\n".join(f"- {r['play']} ({r['down']}): {r['desc'][:90]}" for r in clips.iter_rows(named=True))
    return f"""FILM ROOM LINKS (last step, about 10 minutes, counts toward the click cap)
In Watch Film → Film Room with Game = this game, find each play below (the list shows quarter, clock and description; page through with the arrows, 25 per page). Click the play so it loads, then copy the page address from the address bar. Don't play more than a few seconds, don't click Share or Save Search. If the address doesn't change per play, say so once and stop this step. If an address has anything that looks like a token or session id in it, don't copy it; note "token" instead.
{plays}
Put them in "film_links": [{{"play": "Q1 02:57", "url": "..."}}]."""
