"""Ticket 15: charts you'd actually put in a post (PNG, light background).

Style: thin marks, recessive grid, one accent color for the Giants, neutral gray for
everyone else, text in ink colors (never the series color), selective labels.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import polars as pl  # noqa: E402

from bbt import config  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
TEAM_COLOR = "#2a78d6"   # categorical slot 1 (blue)
OPP_COLOR = "#eb6834"    # categorical slot 2 (orange)
NEUTRAL = "#b9b8b2"
CREDIT = "Data: nflverse"


def _style(ax, title: str, subtitle: str | None = None, ygrid: bool = True) -> None:
    fig = ax.figure
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9, length=0)
    if ygrid:
        ax.grid(axis="y", color=GRID, linewidth=1)
    else:
        ax.grid(axis="y", visible=False)
    ax.set_axisbelow(True)
    fig.text(0.02, 0.965, title, fontsize=14, fontweight="bold", color=INK, ha="left", va="top")
    if subtitle:
        fig.text(0.02, 0.915, subtitle, fontsize=10, color=INK_2, ha="left", va="top")
    fig.text(0.98, 0.015, f"{CREDIT}  ·  Big Blue Theory", fontsize=8, color=INK_2, ha="right")


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return path


def wp_chart(timeline: pl.DataFrame, swings: pl.DataFrame, team: str, opp: str, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.2))
    fig.subplots_adjust(top=0.82, bottom=0.12, left=0.07, right=0.97)
    x, y = timeline["elapsed"].to_list(), (timeline["team_wp"] * 100).to_list()
    ax.axhline(50, color=NEUTRAL, linewidth=1)
    ax.fill_between(x, y, 50, color=TEAM_COLOR, alpha=0.10, linewidth=0)
    ax.plot(x, y, color=TEAM_COLOR, linewidth=2, solid_joinstyle="round", solid_capstyle="round")
    ax.set_ylim(0, 100)
    ax.set_xlim(0, max(3600, max(x) if x else 3600))
    ax.set_xticks([0, 900, 1800, 2700, 3600], ["Q1", "Q2", "Q3", "Q4", "End"])
    ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])

    # Label the top 3 swings only
    by_id = dict(zip(timeline["play_id"].to_list(), zip(x, y)))
    for i, row in enumerate(swings.head(3).iter_rows(named=True), 1):
        if row["play_id"] not in by_id:
            continue
        px, py = by_id[row["play_id"]]
        ax.scatter([px], [py], s=40, color=TEAM_COLOR, edgecolor=SURFACE, linewidth=2, zorder=3)
        sign = "+" if row["wpa_pts"] > 0 else ""
        right_side = px > 0.8 * ax.get_xlim()[1]
        ax.annotate(f"{i}. {sign}{row['wpa_pts']:.0f} pts", (px, py),
                    xytext=(-8 if right_side else 6, 10 if py < 80 else -16), textcoords="offset points",
                    ha="right" if right_side else "left", fontsize=9, color=INK)
    final = y[-1] if y else 50
    _style(ax, f"{team} win probability vs {opp}",
           f"Ends at {final:.0f}%. Numbered dots are the three biggest swings (percentage points).")
    return _save(fig, path)


SHORT_RESULT = {"Field goal": "FG", "Missed field goal": "Missed FG", "Turnover on downs": "Downs",
                "Touchdown": "TD", "Opp touchdown": "Opp TD"}


def _field_x(team: str):
    """x = yards from the Giants' own goal line, 0-100."""
    return lambda posteam, yl100: 100 - yl100 if posteam == team else yl100


def drive_chart(drives: pl.DataFrame, team: str, opp: str, path: Path) -> Path:
    n = drives.height
    fig, ax = plt.subplots(figsize=(10, 0.36 * n + 2))
    fig.subplots_adjust(top=1 - 1.1 / (0.36 * n + 2), bottom=0.8 / (0.36 * n + 2), left=0.05, right=0.68)
    fx = _field_x(team)
    for i, d in enumerate(drives.iter_rows(named=True)):
        start = fx(d["team"], d["start_yl100"])
        end_yl100 = max(0, min(100, d["start_yl100"] - (d["yards"] or 0)))
        if d["result"] == "Touchdown":
            end_yl100 = 0
        end = fx(d["team"], end_yl100)
        color = TEAM_COLOR if d["team"] == team else OPP_COLOR
        yrow = n - 1 - i
        ax.plot([start, end], [yrow, yrow], color=color, linewidth=6, solid_capstyle="round")
        ax.scatter([end], [yrow], s=36, color=color, edgecolor=SURFACE, linewidth=2, zorder=3)
        result = SHORT_RESULT.get(d["result"], d["result"])
        if result == "End of half" and d["qtr"] >= 4:
            result = "End of game"
        ax.text(102, yrow, f"Q{int(d['qtr'])} {d['team']}  {result} · {d['plays']} pl, {d['yards']} yds",
                va="center", fontsize=8.5, color=INK, clip_on=False)
    for gx in (0, 100):
        ax.axvline(gx, color=INK_2, linewidth=1)
    ax.axvline(50, color=GRID, linewidth=1)
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.8, n - 0.2)
    ax.set_yticks([])
    ax.set_xticks([0, 20, 50, 80, 100], [f"{team} goal", f"{team} 20", "50", f"{opp} 20", f"{opp} goal"])
    ax.grid(False)
    _style(ax, f"Every drive, {team} vs {opp}",
           f"Blue = {team} (drives go right), orange = {opp} (drives go left). Dot = where it ended.",
           ygrid=False)
    return _save(fig, path)


def erased_league_chart(totals: pl.DataFrame, team: str, path: Path) -> Path:
    t = totals.sort("ep_erased")
    fig, ax = plt.subplots(figsize=(8, 9))
    fig.subplots_adjust(top=0.88, bottom=0.07, left=0.10, right=0.95)
    colors = [TEAM_COLOR if tm == team else NEUTRAL for tm in t["team"]]
    ax.barh(t["team"].to_list(), t["ep_erased"].to_list(), height=0.62, color=colors)
    ax.axvline(0, color=INK_2, linewidth=1)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=1)
    for tick in ax.get_yticklabels():
        if tick.get_text() == team:
            tick.set_fontweight("bold")
            tick.set_color(INK)
    me = t.filter(pl.col("team") == team)
    if me.height:
        v = me["ep_erased"][0]
        idx = t["team"].to_list().index(team)
        ax.text(v + (0.2 if v >= 0 else -0.2), idx, f"{v:.1f}", va="center",
                ha="left" if v >= 0 else "right", fontsize=9, color=INK, fontweight="bold")
    ax.set_xlabel("Expected points erased by the team's own penalties", color=INK_2, fontsize=9)
    _style(ax, "Points erased by penalties",
           f"Value of plays wiped out by each team's flags, {config.SEASON} season to date", ygrid=False)
    return _save(fig, path)


def penalty_game_chart(est: pl.DataFrame, team: str, opp: str, path: Path) -> Path:
    """One bar per credited flag in the game: total EP cost to the team that committed it."""
    g = est.filter(pl.col("kind").is_in(["pre_snap", "wiped"])).sort("play_id")
    if g.is_empty():
        return path
    labels = [f"Q{int(r['qtr'])} {r['time']}  {r['penalty_team']} {r['penalty_type']}"
              for r in g.iter_rows(named=True)]
    vals = g["total_cost_to_penalized"].fill_null(0).to_list()
    colors = [TEAM_COLOR if tm == team else OPP_COLOR for tm in g["penalty_team"]]
    fig, ax = plt.subplots(figsize=(10, 0.34 * len(labels) + 2))
    fig.subplots_adjust(top=1 - 1.1 / (0.34 * len(labels) + 2), bottom=0.9 / (0.34 * len(labels) + 2),
                        left=0.38, right=0.95)
    ypos = list(range(len(labels)))[::-1]
    ax.barh(ypos, vals, height=0.6, color=colors)
    ax.set_yticks(ypos, labels, fontsize=8.5)
    ax.axvline(0, color=INK_2, linewidth=1)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=1)
    ax.set_xlabel("Expected points the flag cost the team that committed it", color=INK_2, fontsize=9)
    _style(ax, f"What the flags cost, {team} vs {opp}",
           f"Pre-snap and wiped-play penalties only. Blue = {team}, orange = {opp}.", ygrid=False)
    return _save(fig, path)
