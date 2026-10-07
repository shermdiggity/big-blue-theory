"""Ticket 15: the automatic charts every week gets from free data, drawn in the house style (bbt.viz).

The story charts for a week's notes come from `private/notes/<tag>_charts.json` (see bbt.viz);
these five need no spec: win probability, every drive, the flags, points erased league-wide, and
the gameplan vs the Giants' usual.
"""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl

from bbt import config, viz
from bbt.viz import ACCENT, BASELINE, GRID, INK, INK_2, MUTED, NEUTRAL, OTHER, PLANE, SURFACE, Card, rbar

CREDIT = "nflverse play-by-play"


def _kicker(team: str, opp: str, week: int | None) -> str:
    return f"Week {week} · {team} vs {opp}" if week else f"{team} vs {opp}"


def wp_chart(timeline: pl.DataFrame, swings: pl.DataFrame, team: str, opp: str, path: Path,
             week: int | None = None) -> Path:
    x, y = timeline["elapsed"].to_list(), (timeline["team_wp"] * 100).to_list()
    final = y[-1] if y else 50
    low, high = (min(y), max(y)) if y else (50, 50)
    title = f"{team} win probability vs {opp}"
    card = Card(title, "After every play. Numbered dots: the three biggest swings, listed below.",
                CREDIT, _kicker(team, opp, week), height=5.0)
    ax = card.axes(left=0.42, bottom=0.3 + 0.2 * min(3, swings.height), right=0.45)
    xmax = max(3600, max(x) if x else 3600)
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, 100)
    for q in (900, 1800, 2700):
        ax.axvline(q, color=GRID, lw=0.8, zorder=0)
    if xmax > 3600:
        ax.axvspan(3600, xmax, color=PLANE, lw=0, zorder=0)
    ax.axhline(50, color=BASELINE, lw=1, zorder=1)
    ax.set_xticks([450, 1350, 2250, 3150] + ([3600 + (xmax - 3600) / 2] if xmax > 3600 else []),
                  ["Q1", "Q2", "Q3", "Q4"] + (["OT"] if xmax > 3600 else []))
    ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.tick_params(axis="y", labelcolor=MUTED, labelsize=9)
    ax.tick_params(axis="x", pad=8)
    ax.fill_between(x, y, 50, color=ACCENT, alpha=0.10, lw=0, zorder=1)
    ax.plot(x, y, color=ACCENT, lw=viz.LINE_PT, solid_joinstyle="round", solid_capstyle="round", zorder=3)
    by_id = dict(zip(timeline["play_id"].to_list(), zip(x, y)))
    key = []
    for i, row in enumerate(swings.head(3).iter_rows(named=True), 1):
        if row["play_id"] not in by_id:
            continue
        px, py = by_id[row["play_id"]]
        ax.scatter([px], [py], s=150, color=INK, edgecolor=SURFACE, lw=1.6, zorder=5, clip_on=False)
        ax.annotate(str(i), (px, py), ha="center", va="center", fontsize=8, fontweight="bold", color="white",
                    zorder=6, family=viz._fam(), annotation_clip=False)
        desc = re.sub(r"^\(\s*\d*:\d+\)\s*(\((Shotgun|No Huddle[^)]*)\)\s*)*", "", row["desc"] or "")
        desc = desc if len(desc) <= 80 else desc[:80].rsplit(" ", 1)[0] + "…"
        key.append(f"{i}  {row['wpa_pts']:+.0f} pts, Q{int(row['qtr'])} {row['time']}: {desc}")
    for j, line in enumerate(key):  # the swings, spelled out under the plot
        card.text(viz.MARGIN, card.H - card.bottom + 0.02 - 0.2 * (len(key) - j), line, size=8.5, color=INK_2)
    ax.annotate(f"{final:.0f}%", (x[-1] if x else 0, final), xytext=(14, 0), textcoords="offset points",
                va="center", fontsize=10.5, fontweight="semibold", color=INK, family=viz._fam(),
                annotation_clip=False)
    return card.save(path)


SHORT_RESULT = {"Field goal": "FG", "Missed field goal": "Missed FG", "Turnover on downs": "Downs",
                "Touchdown": "TD", "Opp touchdown": "Opp TD"}


def _field_x(team: str):
    """x = yards from the Giants' own goal line, 0-100."""
    return lambda posteam, yl100: 100 - yl100 if posteam == team else yl100


def drive_chart(drives: pl.DataFrame, team: str, opp: str, path: Path, week: int | None = None) -> Path:
    n = drives.height
    card = Card(f"Every drive, {team} vs {opp}",
                f"Start to end of each drive. {team} drives go right, {opp} drives go left.",
                CREDIT, _kicker(team, opp, week), height=max(4.5, 2.3 + 0.3 * n),
                legend=[(team, ACCENT, "sq"), (opp, OTHER, "sq")])
    labels = []
    for d in drives.iter_rows(named=True):
        result = SHORT_RESULT.get(d["result"], d["result"])
        if result == "End of half" and d["qtr"] >= 4:
            result = "End of game"
        labels.append(f"{result} · {d['plays']} pl, {d['yards']} yds")
    lw = viz._label_col(card, labels, 9)
    ax = card.axes(left=0.62, right=lw + 0.2, bottom=0.3)
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.7, n - 0.3)
    ax.set_yticks([])
    ax.set_xticks([0, 20, 50, 80, 100], [f"{team} goal", f"{team} 20", "50", f"{opp} 20", f"{opp} goal"])
    ax.tick_params(axis="x", labelsize=8.5, labelcolor=MUTED, pad=6)
    for gx in (0, 100):
        ax.axvline(gx, color=BASELINE, lw=1, zorder=0)
    for gx in (20, 50, 80):
        ax.axvline(gx, color=GRID, lw=0.8, zorder=0)
    fx = _field_x(team)
    last_q = None
    for i, (d, lab) in enumerate(zip(drives.iter_rows(named=True), labels)):
        start = fx(d["team"], d["start_yl100"])
        end_yl100 = 0 if d["result"] == "Touchdown" else max(0, min(100, d["start_yl100"] - (d["yards"] or 0)))
        end = fx(d["team"], end_yl100)
        yrow = n - 1 - i
        mine = d["team"] == team
        if end == start:
            end = start + (0.6 if mine else -0.6)
        rbar(ax, start, end, yrow, 0.56, ACCENT if mine else OTHER)
        scored = d["result"] in ("Touchdown", "Field goal")
        ax.annotate(lab, (100, yrow), xytext=(10, 0), textcoords="offset points", va="center", fontsize=9,
                    color=INK if scored else INK_2, fontweight="semibold" if scored else "normal",
                    family=viz._fam(), annotation_clip=False)
        if d["qtr"] != last_q:
            ax.annotate(f"Q{int(d['qtr'])}", (0, yrow), xytext=(-10, 0), textcoords="offset points", ha="right",
                        va="center", fontsize=9, fontweight="semibold", color=INK_2, family=viz._fam(),
                        annotation_clip=False)
            last_q = d["qtr"]
    return card.save(path)


def erased_league_chart(totals: pl.DataFrame, team: str, path: Path) -> Path:
    t = totals.sort("ep_erased", descending=True)
    title = "Expected points erased by each team's own penalties"
    card = Card(title, f"Value of plays wiped out by flags, {config.SEASON} season to date",
                CREDIT + " (Big Blue Theory penalty ledger)", height=9.0)
    rows = [{"label": r["team"], "value": r["ep_erased"]} for r in t.iter_rows(named=True)]
    ax = card.axes(left=0.5, right=0.2)
    n = len(rows)
    vals = [r["value"] for r in rows]
    span = (max(vals + [0]) - min(vals + [0])) or 1
    ax.set_xlim(min(vals + [0]) - (0.14 if min(vals) < 0 else 0.02) * span, max(vals + [0]) + 0.12 * span)
    ax.set_ylim(-0.7, n - 0.3)
    ax.set_yticks(range(n)[::-1], [r["label"] for r in rows])
    for lab in ax.get_yticklabels():
        lab.set_fontsize(8.5)
        lab.set_family(viz._fam())
        if lab.get_text() == team:
            lab.set_fontweight("bold")
            lab.set_color(INK)
    ax.tick_params(axis="x", labelsize=8.5, labelcolor=MUTED)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.axvline(0, color=BASELINE, lw=1, zorder=3)
    for i, r in enumerate(rows):
        y = n - 1 - i
        mine = r["label"] == team
        rbar(ax, 0, r["value"], y, 0.62, ACCENT if mine else NEUTRAL)
        if mine or i in (0, n - 1):
            ax.annotate(f"{r['value']:.1f}".replace("-", "−"), (r["value"], y),
                        xytext=(5 if r["value"] >= 0 else -5, 0), textcoords="offset points",
                        ha="left" if r["value"] >= 0 else "right", va="center", fontsize=9,
                        fontweight="bold" if mine else "normal", color=INK if mine else INK_2, family=viz._fam())
    return card.save(path)


def penalty_game_chart(est: pl.DataFrame, team: str, opp: str, path: Path, week: int | None = None) -> Path:
    """One bar per credited flag in the game: total EP cost to the team that committed it."""
    g = est.filter(pl.col("kind").is_in(["pre_snap", "wiped"])).sort("play_id")
    if g.is_empty():
        return path
    card = Card(f"Penalties, {team} vs {opp}: expected points each flag cost",
                "Pre-snap and wiped-play penalties in game order, cost to the team that committed it", CREDIT, _kicker(team, opp, week), height=max(4.5, 2.4 + 0.34 * g.height),
                legend=[(team, ACCENT, "sq"), (opp, OTHER, "sq")])
    labels = [f"Q{int(r['qtr'])} {r['time']}  {r['penalty_type']}" for r in g.iter_rows(named=True)]
    lw = viz._label_col(card, labels, 9)
    ax = card.axes(left=lw + 0.14, bottom=0.1)
    vals = g["total_cost_to_penalized"].fill_null(0).to_list()
    rows = [{"value": v} for v in vals]
    ax.set_xlim(*viz._value_xlim(card, ax, rows, "{:+.1f}", 9))
    n = len(vals)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xticks([])
    ax.set_yticks(range(n)[::-1], labels)
    for lab, tm in zip(ax.get_yticklabels(), g["penalty_team"].to_list()):
        lab.set_fontsize(9)
        lab.set_family(viz._fam())
        lab.set_color(INK if tm == team else INK_2)
    ax.tick_params(axis="y", pad=8)
    ax.axvline(0, color=BASELINE, lw=1, zorder=3)
    for i, (v, tm) in enumerate(zip(vals, g["penalty_team"].to_list())):
        y = n - 1 - i
        rbar(ax, 0, v, y, 0.6, ACCENT if tm == team else OTHER)
        ax.annotate(f"{v:+.1f}".replace("-", "−"), (v, y), xytext=(5 if v >= 0 else -5, 0),
                    textcoords="offset points", ha="left" if v >= 0 else "right", va="center", fontsize=9,
                    color=INK, family=viz._fam())
    return card.save(path)


RATE_METRICS = ["pass_rate", "early_down_pass", "shotgun", "no_huddle", "motion", "play_action", "success"]


def gameplan_chart(cmp: pl.DataFrame, team: str, opp: str, path: Path, week: int | None = None) -> Path:
    """This game vs the team's usual vs the league, for the rate metrics (one shared % scale)."""
    rows = []
    for r in cmp.filter(pl.col("metric").is_in(RATE_METRICS)).iter_rows(named=True):
        if r["this_game"] is None:
            continue
        rows.append({"label": r["label"].replace(" (FTN)", "").replace(", dropbacks", " (dropbacks)"), "b": r["this_game"] * 100,
                     "a": None if r[f"{team}_prior"] is None else r[f"{team}_prior"] * 100,
                     "ref": None if r["league"] is None else r["league"] * 100})
    if not rows:
        return path
    title = f"{team} offense vs {opp}: this game vs usual vs league"
    spec = {"kind": "dumbbell", "rows": rows, "fmt": "{:.0f}%", "xlim": [0, 100], "xticks": [0, 25, 50, 75, 100],
            "names": [f"{team} usual (prior games)", "This game", "League"]}
    card = Card(title, "Giants offense, real run and pass plays only. FTN rates appear once FTN charts the game.",
                CREDIT + " / FTN Data via nflverse", _kicker(team, opp, week), height=viz._height(spec),
                legend=viz._legend(spec))
    viz.dumbbell(card, spec)
    return card.save(path)
