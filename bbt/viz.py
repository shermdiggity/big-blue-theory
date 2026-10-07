"""The Big Blue Theory chart look, and the chart kinds the pipeline can draw.

Every chart is a 1600 x 900 "card" (taller if it needs rows): brand rule and kicker, a headline
that says what the chart shows, a subtitle that says what's measured, the plot, and a footer with the
source. Charts are described as plain dicts (the week's `private/notes/<tag>_charts.json`), so the
session writes data + words and this module does the drawing:

    {"id": "pass_rush", "kind": "bars", "orientation": "v",
     "title": "Player A: pass-rush win rate by week", "subtitle": "Pressures above each bar",
     "source": "Sūmer charting", "fmt": "{:.0f}%", "highlight": ["Wk 3"],
     "rows": [{"label": "Wk 1", "value": 12}, ...]}     (made-up numbers; real ones stay in private/)

Kinds: bars, trend, grouped, split, diverging, dumbbell, panels, tiles (see KINDS / docs/charts.md).

Design rules (dataviz skill): one accent per chart, gray for the rest; thin marks with 4px rounded
data-ends; 2px surface gaps between fills; selective direct labels; text in ink colors, never the
series color; one value axis per plot (two measures = two panels); a legend for 2+ series.
Palette checked with the dataviz validator (blue/orange pass CVD separation and contrast on SURFACE).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyBboxPatch, PathPatch, Rectangle  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402

from bbt import config  # noqa: E402

# --- palette ---------------------------------------------------------------------------------------
SURFACE = "#fcfcfb"
PLANE = "#f4f3ef"        # tile / highlight-band fill
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
ACCENT = "#2a78d6"       # categorical slot 1: the Giants / the thing the chart is about
OTHER = "#eb6834"        # categorical slot 2: opponent / second series
SERIES = [ACCENT, OTHER, "#1baf7a", "#eda100"]
NEUTRAL = "#b9b8b2"      # de-emphasised marks
NEUTRAL_LIGHT = "#dddcd5"  # second part of a share bar
POS = ACCENT             # diverging poles (gray midpoint = the zero line)
NEG = "#e34948"
BRAND = "#0b2265"        # Giants navy: the brand rule only, never data

DPI = 200
PX = 72 / DPI            # one output pixel in points
RADIUS_PX = 8            # rounded data-end (4px at 1x; cards are 2x)
GAP_PT = 3 * PX * 2      # surface gap between adjacent fills
LINE_PT = 2.0
DOT = 62                 # scatter size (pt^2), ~8px at 1x

MARGIN = 0.42            # inches
FOOTER = 0.46

# --- fonts (Barlow, SIL Open Font License, bundled in bbt/fonts) ----------------------------------
FONT_DIR = Path(__file__).parent / "fonts"


def _load_fonts() -> tuple[str, str]:
    for f in FONT_DIR.glob("*.ttf"):
        try:
            font_manager.fontManager.addfont(str(f))
        except Exception:  # noqa: BLE001  a broken font file shouldn't stop the charts
            pass
    names = {f.name for f in font_manager.fontManager.ttflist}
    body = "Barlow" if "Barlow" in names else "DejaVu Sans"
    head = "Barlow Condensed" if "Barlow Condensed" in names else body
    return body, head


BODY, HEAD = _load_fonts()
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)  # DejaVu has no semibold: fine
matplotlib.rcParams.update({
    "font.family": [BODY, "DejaVu Sans"],   # DejaVu fills glyphs Barlow lacks (arrows)
    "axes.unicode_minus": True,
})


def _fam(head: bool = False) -> list[str]:
    return [HEAD if head else BODY, "DejaVu Sans"]


# --- the card --------------------------------------------------------------------------------------
class Card:
    """A figure with the house header and footer. Work in inches from the top-left."""

    def __init__(self, title: str, subtitle: str | None = None, source: str = "nflverse",
                 kicker: str = "", width: float = 8.0, height: float = 4.5,
                 legend: list[tuple[str, str, str]] | None = None):
        self.W, self.H = width, height
        self.fig = plt.figure(figsize=(width, height), dpi=DPI)
        self.fig.patch.set_facecolor(SURFACE)
        self.r = self.fig.canvas.get_renderer()
        fig = self.fig
        fig.add_artist(Rectangle((MARGIN / width, 1 - 0.27 / height), 0.42 / width, 0.05 / height,
                                 transform=fig.transFigure, color=BRAND, lw=0))
        y = 0.38
        if kicker:
            y += self.text(MARGIN, y, kicker.upper(), size=8.5, weight="semibold", color=INK_2) + 0.07
        for line in self.wrap(title, width - 2 * MARGIN, size=21, weight="bold", head=True):
            y += self.text(MARGIN, y, line, size=21, weight="bold", color=INK, head=True) + 0.02
        y += 0.04
        if subtitle:
            for line in self.wrap(subtitle, width - 2 * MARGIN, size=10.5):
                y += self.text(MARGIN, y, line, size=10.5, color=INK_2) + 0.03
        if legend:
            y += 0.08
            x = MARGIN
            for label, color, mark in legend:
                yc = y + 0.08
                if mark == "line":
                    fig.add_artist(Line2D([x / width, (x + 0.24) / width], [1 - yc / height] * 2,
                                          color=color, lw=LINE_PT, solid_capstyle="round"))
                    x += 0.32
                elif mark == "tick":
                    fig.add_artist(Line2D([(x + 0.06) / width] * 2, [1 - (yc - 0.08) / height,
                                                                     1 - (yc + 0.08) / height],
                                          color=color, lw=1.6))
                    x += 0.18
                else:
                    fig.add_artist(FancyBboxPatch((x / width, 1 - (yc + 0.06) / height), 0.12 / width,
                                                  0.12 / height, boxstyle="round,pad=0,rounding_size=0.004",
                                                  transform=fig.transFigure, color=color, lw=0))
                    x += 0.19
                w = self.measure(label, size=9.5)[0]
                self.text(x, y, label, size=9.5, color=INK_2)
                x += w + 0.28
            y += 0.18
        self.top = y + 0.22
        fig.add_artist(Line2D([MARGIN / width, 1 - MARGIN / width], [FOOTER / height] * 2, color=GRID, lw=0.8))
        self.text(MARGIN, height - FOOTER + 0.11, f"Source: {source}", size=8, color=MUTED)
        self.bottom = FOOTER + 0.18

    # text helpers (inches from top)
    def text(self, x, y, s, size=10, weight="normal", color=INK, head=False, ha="left", va="top", **kw):
        t = self.fig.text(x / self.W, 1 - y / self.H, s, fontsize=size, fontweight=weight, color=color,
                          family=_fam(head), ha=ha, va=va, **kw)
        return t.get_window_extent(self.r).height / DPI

    def measure(self, s, size=10, weight="normal", head=False) -> tuple[float, float]:
        t = self.fig.text(0, 0, s, fontsize=size, fontweight=weight, family=_fam(head))
        bb = t.get_window_extent(self.r)
        t.remove()
        return bb.width / DPI, bb.height / DPI

    def wrap(self, s, max_w, size=10, weight="normal", head=False) -> list[str]:
        lines, cur = [], ""
        for word in s.split():
            trial = f"{cur} {word}".strip()
            if cur and self.measure(trial, size, weight, head)[0] > max_w:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        return lines + ([cur] if cur else [])

    def axes(self, left=0.0, right=0.0, bottom=0.0, top=0.0, x0=None, x1=None):
        """An unstyled plot area inside the card. left/right/bottom/top are extra insets (inches)."""
        a = (x0 if x0 is not None else MARGIN) + left
        b = (x1 if x1 is not None else self.W - MARGIN) - right
        lo, hi = self.bottom + bottom, self.H - self.top - top
        ax = self.fig.add_axes([a / self.W, lo / self.H, (b - a) / self.W, (hi - lo) / self.H])
        ax.set_facecolor("none")
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(length=0, colors=INK_2, labelsize=9.5)
        for lab in ax.get_xticklabels() + ax.get_yticklabels():
            lab.set_family(_fam())
        ax.set_axisbelow(True)
        return ax

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.fig.savefig(path, dpi=DPI, facecolor=SURFACE)
        plt.close(self.fig)
        return path


# --- marks -----------------------------------------------------------------------------------------
def rbar(ax, base, value, center, thick, color, horizontal=True, zorder=2, gap=True):
    """A bar from base to value with only the data-end corners rounded (axis limits must be final)."""
    if value is None or value == base:
        return
    (x0p, y0p), (x1p, y1p) = ax.transData.transform([(0, 0), (1, 1)])
    sx, sy = abs(x1p - x0p), abs(y1p - y0p)
    s_al, s_ac = (sx, sy) if horizontal else (sy, sx)
    r = min(RADIUS_PX, abs(value - base) * s_al, thick * s_ac / 2)
    ra, rc = r / s_al, r / s_ac
    d = 1 if value > base else -1
    c0, c1 = center - thick / 2, center + thick / 2
    pts = [(base, c0), (value - d * ra, c0), (value, c0), (value, c0 + rc), (value, c1 - rc),
           (value, c1), (value - d * ra, c1), (base, c1), (base, c0)]
    codes = [MPath.MOVETO, MPath.LINETO, MPath.CURVE3, MPath.CURVE3, MPath.LINETO, MPath.CURVE3,
             MPath.CURVE3, MPath.LINETO, MPath.CLOSEPOLY]
    if not horizontal:
        pts = [(c, a) for a, c in pts]
    ax.add_patch(PathPatch(MPath(pts, codes), facecolor=color, edgecolor=SURFACE if gap else "none",
                           lw=GAP_PT if gap else 0, zorder=zorder, joinstyle="round"))


def _fmt(fmt: str, v) -> str:
    if v is None:
        return "–"
    s = fmt.format(v)
    return s.replace("-", "−")


def _label_col(card: Card, labels: list[str], size=10) -> float:
    return max((card.measure(lab, size)[0] for lab in labels), default=0)


def _value_xlim(card, ax, rows, fmt, size=10, min_room=0.0):
    """x limits that leave room (in inches) for the value labels at the bar ends."""
    vals = [r["value"] for r in rows]
    lo_v, hi_v = min([0] + vals), max([0] + vals)
    width_in = ax.get_position().width * card.W

    def room(sign):
        texts = [_fmt(fmt, r["value"]) + (f"  {r['note']}" if r.get("note") else "")
                 for r in rows if (r["value"] < 0) == (sign < 0) and r["value"] != 0]
        return (max((card.measure(t, size, "semibold")[0] for t in texts), default=0) + 0.14) if texts else min_room

    f_lo, f_hi = room(-1) / width_in, room(1) / width_in
    total = (hi_v - lo_v or 1) / max(0.2, 1 - f_lo - f_hi)
    return lo_v - f_lo * total, hi_v + f_hi * total


def _hbars(card, ax, rows, fmt, highlight, ref=None, color=None, size=10):
    """Horizontal bars on an existing axes; labels drawn by the caller as y ticks."""
    n = len(rows)
    hi = set(highlight or [])
    lo, hi_x = _value_xlim(card, ax, rows, fmt, size)
    if ref:
        lo, hi_x = min(lo, ref["value"]), max(hi_x, ref["value"])
    ax.set_xlim(lo, hi_x)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xticks([])
    ys = [n - 1 - i for i in range(n)]
    ax.set_yticks(ys, [r["label"] for r in rows])
    for lab, r in zip(ax.get_yticklabels(), rows):
        lab.set_family(_fam())
        lab.set_fontsize(size)
        lab.set_color(INK if (not hi or r["label"] in hi) else INK_2)
        lab.set_fontweight("semibold" if r["label"] in hi else "normal")
    ax.tick_params(axis="y", pad=8)
    ax.axvline(0, color=BASELINE, lw=1, zorder=3)
    thick = 0.62 if n > 2 else 0.5
    for y, r in zip(ys, rows):
        c = color or (ACCENT if (not hi or r["label"] in hi) else NEUTRAL)
        rbar(ax, 0, r["value"], y, thick, c)
        v = r["value"]
        txt = _fmt(fmt, v)
        if r.get("note"):  # value in ink, the note muted beside it
            txt += "  "
            off = card.measure(txt, size, "semibold")[0] * 72
            ax.annotate(r["note"], (v, y), xytext=(6 + off if v >= 0 else -6, 0), textcoords="offset points",
                        ha="left" if v >= 0 else "right", va="center", fontsize=size - 1, color=MUTED,
                        family=_fam())
            if v < 0:
                txt = _fmt(fmt, v)
        ax.annotate(txt, (v, y), xytext=(6 if v >= 0 else -6 - (card.measure("  " + r["note"], size - 1)[0] * 72
                                                                   if r.get("note") else 0), 0),
                    textcoords="offset points", ha="left" if v >= 0 else "right", va="center", fontsize=size,
                    fontweight="semibold" if (not hi or r["label"] in hi) else "normal",
                    color=INK if (not hi or r["label"] in hi) else INK_2, family=_fam())
    if ref:
        ax.axvline(ref["value"], color=INK_2, lw=1, ls=(0, (3, 2)), zorder=4)
        ax.annotate(ref.get("label", ""), (ref["value"], n - 0.4), xytext=(4, -2), textcoords="offset points",
                    ha="left", va="top", fontsize=8.5, color=INK_2, family=_fam())


# --- chart kinds -------------------------------------------------------------------------------------
def bars(card: Card, spec: dict):
    rows, fmt = spec["rows"], spec.get("fmt", "{:.0f}")
    hi = spec.get("highlight") or []
    if spec.get("orientation", "h") == "h":
        lw = _label_col(card, [r["label"] for r in rows])
        ax = card.axes(left=lw + 0.14)
        _hbars(card, ax, rows, fmt, hi, spec.get("ref"))
        return
    ax = card.axes(bottom=0.32)
    n = len(rows)
    vals = [r["value"] for r in rows]
    top = max(vals + [0] + ([spec["ref"]["value"]] if spec.get("ref") else []))
    low = min(vals + [0])
    span = (top - low) or 1
    ax.set_ylim(low - (0.1 * span if low < 0 else 0), top + 0.16 * span)
    ax.set_xlim(-0.6, n - 0.4)
    ax.set_yticks([])
    ax.set_xticks(range(n), [r["label"] for r in rows])
    for lab, r in zip(ax.get_xticklabels(), rows):
        lab.set_family(_fam())
        lab.set_fontsize(10)
        lab.set_color(INK if (not hi or r["label"] in hi) else INK_2)
        lab.set_fontweight("semibold" if r["label"] in hi else "normal")
    ax.tick_params(axis="x", pad=8)
    ax.axhline(0, color=BASELINE, lw=1, zorder=3)
    w = min(0.62, 0.9 - 0.04 * n)
    for i, r in enumerate(rows):
        on = not hi or r["label"] in hi
        rbar(ax, 0, r["value"], i, w, ACCENT if on else NEUTRAL, horizontal=False)
        ax.annotate(_fmt(fmt, r["value"]), (i, r["value"]), xytext=(0, 5), textcoords="offset points",
                    ha="center", va="bottom", fontsize=11 if on else 10, family=_fam(),
                    fontweight="semibold" if on else "normal", color=INK if on else INK_2)
        if r.get("note"):
            ax.annotate(r["note"], (i, r["value"]), xytext=(0, 21 if on else 19), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8.5, color=MUTED, family=_fam())
    if spec.get("ref"):
        ref = spec["ref"]
        ax.axhline(ref["value"], color=INK_2, lw=1, ls=(0, (3, 2)), zorder=4)
        ax.annotate(ref.get("label", ""), (n - 0.4, ref["value"]), xytext=(0, 4), textcoords="offset points",
                    ha="right", va="bottom", fontsize=8.5, color=INK_2, family=_fam())


def trend(card: Card, spec: dict):
    xs, series, fmt = spec["x"], spec["series"], spec.get("fmt", "{:.0f}")
    n = len(xs)
    allv = [v for s in series for v in s["values"] if v is not None]
    lo, hi = spec.get("ylim", [min(0, min(allv)), max(allv) * 1.15])
    tick_w = max(card.measure(_fmt(fmt, t), 9)[0] for t in (spec.get("yticks") or [lo, hi]))
    end_w = max(card.measure(f"{s['name']}  {_fmt(fmt, s['values'][-1])}", 10.5, "semibold")[0] for s in series)
    ax = card.axes(bottom=0.3, left=tick_w + 0.12, right=end_w + 0.25)
    ax.set_ylim(lo, hi)
    ax.set_xlim(-0.35, n - 0.65)
    ticks = spec.get("yticks") or [t for t in ax.get_yticks() if lo <= t <= hi]
    ax.set_yticks(ticks, [_fmt(fmt, t) for t in ticks])
    ax.set_xticks(range(n), xs)
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_family(_fam())
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.tick_params(axis="x", pad=8)
    ax.tick_params(axis="y", pad=6, labelcolor=MUTED, labelsize=9)
    hx = spec.get("highlight_x")
    if hx in xs:
        i = xs.index(hx)
        ax.axvspan(i - 0.32, i + 0.32, color=PLANE, lw=0, zorder=0)
        ax.get_xticklabels()[i].set_fontweight("semibold")
        ax.get_xticklabels()[i].set_color(INK)
    if spec.get("ref"):
        ax.axhline(spec["ref"]["value"], color=INK_2, lw=1, ls=(0, (3, 2)))
        ax.annotate(spec["ref"].get("label", ""), (0 - 0.3, spec["ref"]["value"]), xytext=(0, 4),
                    textcoords="offset points", fontsize=8.5, color=INK_2, family=_fam())
    ends = []
    for k, s in enumerate(series):
        c = NEUTRAL if s.get("muted") else SERIES[k % len(SERIES)]
        pts = [(i, v) for i, v in enumerate(s["values"]) if v is not None]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=c, lw=LINE_PT, solid_capstyle="round",
                solid_joinstyle="round", zorder=3)
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=DOT, color=c, edgecolor=SURFACE, lw=1.6, zorder=4)
        if hx in xs and hx != xs[pts[-1][0]]:
            v = s["values"][xs.index(hx)]
            ax.annotate(_fmt(fmt, v), (xs.index(hx), v), xytext=(0, 9), textcoords="offset points",
                        ha="center", fontsize=10, fontweight="semibold", color=INK, family=_fam())
        ends.append([pts[-1][1], s["name"], pts[-1][1], pts[-1][0]])
    # end labels, nudged apart so they don't collide
    span = hi - lo
    ends.sort(key=lambda e: e[0])
    for j in range(1, len(ends)):
        if ends[j][2] - ends[j - 1][2] < 0.09 * span:
            ends[j][2] = ends[j - 1][2] + 0.09 * span
    for v, name, ypos, xi in ends:
        ax.annotate(f"{name}  ", (xi, ypos), xytext=(12, 0), textcoords="offset points", va="center",
                    ha="left", fontsize=9.5, color=INK_2, family=_fam(), annotation_clip=False)
        w = card.measure(f"{name}  ", 9.5)[0] * 72
        ax.annotate(_fmt(fmt, v), (xi, ypos), xytext=(12 + w, 0), textcoords="offset points", va="center",
                    ha="left", fontsize=10.5, fontweight="semibold", color=INK, family=_fam(),
                    annotation_clip=False)


def grouped(card: Card, spec: dict):
    groups, series, fmt = spec["groups"], spec["series"], spec.get("fmt", "{:.0f}")
    ax = card.axes(bottom=0.55 if spec.get("notes") else 0.32)
    ns = len(series)
    allv = [v for s in series for v in s["values"] if v is not None]
    ax.set_ylim(min(0, min(allv)), max(allv) * 1.16)
    ax.set_xlim(-0.6, len(groups) - 0.4)
    ax.set_yticks([])
    ax.set_xticks(range(len(groups)), groups)
    hi = set(spec.get("highlight") or [])
    for lab, g in zip(ax.get_xticklabels(), groups):
        lab.set_family(_fam())
        lab.set_fontsize(10.5)
        lab.set_fontweight("semibold" if g in hi else "normal")
        lab.set_color(INK if (not hi or g in hi) else INK_2)
    ax.tick_params(axis="x", pad=8)
    ax.axhline(0, color=BASELINE, lw=1, zorder=3)
    width = 0.74 / ns
    for k, s in enumerate(series):
        for i, v in enumerate(s["values"]):
            x = i - 0.37 + width * (k + 0.5)
            rbar(ax, 0, v, x, width, SERIES[k], horizontal=False)
            on = not hi or groups[i] in hi
            ax.annotate(_fmt(fmt, v), (x, v or 0), xytext=(0, 5), textcoords="offset points", ha="center",
                        va="bottom", fontsize=10.5 if on else 9.5, family=_fam(),
                        fontweight="semibold" if on else "normal", color=INK if on else INK_2)
    for i, g in enumerate(groups):
        note = (spec.get("notes") or {}).get(g)
        if note:
            ax.annotate(note, (i, 0), xytext=(0, -26), textcoords="offset points", ha="center", va="top",
                        fontsize=8.5, color=MUTED, family=_fam(), annotation_clip=False)


def split(card: Card, spec: dict):
    rows, parts = spec["rows"], spec["parts"]
    hi = set(spec.get("highlight") or [])
    lw = _label_col(card, [r["label"] for r in rows])
    nw = max(_label_col(card, [r.get("note", "") for r in rows], 9.5),
             card.measure(spec.get("note_header", ""), 8.5)[0])
    ax = card.axes(left=lw + 0.14, right=nw + 0.2)
    n = len(rows)
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xticks([])
    ys = [n - 1 - i for i in range(n)]
    ax.set_yticks(ys, [r["label"] for r in rows])
    for lab, r in zip(ax.get_yticklabels(), rows):
        lab.set_family(_fam())
        lab.set_fontsize(10.5)
        lab.set_fontweight("semibold" if r["label"] in hi else "normal")
        lab.set_color(INK if (not hi or r["label"] in hi) else INK_2)
    ax.tick_params(axis="y", pad=8)
    colors = [ACCENT] + [NEUTRAL_LIGHT, NEUTRAL][: len(parts) - 1]
    for y, r in zip(ys, rows):
        tot = sum(r["values"]) or 1
        x = 0.0
        for k, v in enumerate(r["values"]):
            share = v / tot
            if share <= 0:
                continue
            last = k == len(r["values"]) - 1
            if last:
                rbar(ax, x, x + share, y, 0.6, colors[k])
            else:
                ax.add_patch(Rectangle((x, y - 0.3), share, 0.6, facecolor=colors[k], edgecolor=SURFACE,
                                       lw=GAP_PT, zorder=2))
            if share >= 0.07:
                ax.text(x + 0.012, y, f"{share * 100:.0f}%", va="center", ha="left", fontsize=9.5,
                        fontweight="semibold", color="white" if k == 0 else INK_2, family=_fam(), zorder=5)
            x += share
        if r.get("note"):
            ax.annotate(r["note"], (1, y), xytext=(10, 0), textcoords="offset points", va="center",
                        fontsize=9.5, color=INK if r["label"] in hi else INK_2, family=_fam(),
                        fontweight="semibold" if r["label"] in hi else "normal", annotation_clip=False)
    if spec.get("note_header"):
        ax.annotate(spec["note_header"], (1, n - 0.4), xytext=(10, 2), textcoords="offset points",
                    va="bottom", fontsize=8.5, color=MUTED, family=_fam(), annotation_clip=False)


def diverging(card: Card, spec: dict):
    rows, fmt = spec["rows"], spec.get("fmt", "{:+.2f}")
    labels = [r["label"] for r in rows]
    lw = _label_col(card, labels, 10.5)
    sw = _label_col(card, [r.get("note", "") for r in rows], 9)
    ax = card.axes(left=max(lw, sw) + 0.16, bottom=0.25)
    n = len(rows)
    ax.set_xlim(*_value_xlim(card, ax, [{"value": r["value"]} for r in rows], fmt, 10.5, min_room=0.5))
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.axvline(0, color=BASELINE, lw=1.2, zorder=3)
    for i, r in enumerate(rows):
        y = n - 1 - i
        v = r["value"]
        rbar(ax, 0, v, y, 0.6, POS if v >= 0 else NEG)
        ax.annotate(_fmt(fmt, v), (v, y), xytext=(6 if v >= 0 else -6, 0), textcoords="offset points",
                    ha="left" if v >= 0 else "right", va="center", fontsize=10.5, fontweight="semibold",
                    color=INK, family=_fam())
        x_lab = ax.get_xlim()[0]
        ax.annotate(r["label"], (x_lab, y), xytext=(-10, 4 if r.get("note") else 0), textcoords="offset points",
                    ha="right", va="center", fontsize=10.5, color=INK, family=_fam(), annotation_clip=False)
        if r.get("note"):
            ax.annotate(r["note"], (x_lab, y), xytext=(-10, -8), textcoords="offset points", ha="right",
                        va="center", fontsize=9, color=MUTED, family=_fam(), annotation_clip=False)
    neg, pos = spec.get("poles", ["← worse", "better →"])
    ax.annotate(neg, (ax.get_xlim()[0], -0.6), xytext=(0, -6), textcoords="offset points", ha="left",
                va="top", fontsize=9, color=MUTED, family=_fam(), annotation_clip=False)
    ax.annotate(pos, (ax.get_xlim()[1], -0.6), xytext=(0, -6), textcoords="offset points", ha="right",
                va="top", fontsize=9, color=MUTED, family=_fam(), annotation_clip=False)


def dumbbell(card: Card, spec: dict):
    """Two values per row on one shared scale (usual vs this game), a tick for a reference (league).
    The numbers sit in a column on the right so they never collide with the marks."""
    rows, fmt = spec["rows"], spec.get("fmt", "{:.0f}%")
    a_name, b_name, ref_name = spec.get("names", ["Usual", "This game", "League"])
    lw = _label_col(card, [r["label"] for r in rows], 10.5)
    col = 0.62
    ax = card.axes(left=lw + 0.16, bottom=0.3, right=3 * col + 0.2, top=0.28)
    n = len(rows)
    allv = [v for r in rows for v in (r.get("a"), r.get("b"), r.get("ref")) if v is not None]
    lo, hi = spec.get("xlim", [min(0, min(allv)), max(allv) * 1.08])
    ax.set_xlim(lo, hi)
    ax.set_ylim(-0.6, n - 0.4)
    ticks = spec.get("xticks") or [t for t in ax.get_xticks() if lo <= t <= hi]
    ax.set_xticks(ticks, [_fmt(fmt, t) for t in ticks])
    ax.tick_params(axis="x", labelcolor=MUTED, labelsize=9, pad=6)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ys = [n - 1 - i for i in range(n)]
    ax.set_yticks(ys, [r["label"] for r in rows])
    for lab in ax.get_yticklabels() + ax.get_xticklabels():
        lab.set_family(_fam())
    for lab in ax.get_yticklabels():
        lab.set_fontsize(10.5)
        lab.set_color(INK)
    ax.tick_params(axis="y", pad=8)
    x_cols = [card.W - MARGIN - col * (2 - k) for k in range(3)]   # right edges of the 3 number columns
    for k, name in enumerate([b_name.split(" (")[0], a_name.split(" (")[0], ref_name]):
        card.text(x_cols[k], card.top, name, size=8.5, color=MUTED, ha="right")
    for y, r in zip(ys, rows):
        a, b, ref = r.get("a"), r.get("b"), r.get("ref")
        if a is not None and b is not None:
            ax.plot([a, b], [y, y], color=NEUTRAL, lw=LINE_PT + 1, solid_capstyle="round", zorder=2)
        if ref is not None:
            ax.plot([ref, ref], [y - 0.22, y + 0.22], color=INK_2, lw=1.6, zorder=3)
        if a is not None:
            ax.scatter([a], [y], s=DOT + 20, color=NEUTRAL, edgecolor=SURFACE, lw=1.6, zorder=4)
        if b is not None:
            ax.scatter([b], [y], s=DOT + 30, color=ACCENT, edgecolor=SURFACE, lw=1.6, zorder=5)
        y_in = card.H - (ax.get_position().y0 * card.H + (y + 0.6) / n * ax.get_position().height * card.H)
        for k, v in enumerate((b, a, ref)):
            card.text(x_cols[k], y_in, _fmt(fmt, v), size=10.5 if k == 0 else 10, ha="right", va="center",
                      weight="semibold" if k == 0 else "normal", color=INK if k == 0 else INK_2)


def panels(card: Card, spec: dict):
    ps = spec["panels"]
    k = len(ps)
    gutter = 0.45
    width = (card.W - 2 * MARGIN - gutter * (k - 1)) / k
    for j, p in enumerate(ps):
        x0 = MARGIN + j * (width + gutter)
        card.text(x0, card.top - 0.08, p["title"], size=11, weight="semibold", color=INK)
        if p.get("subtitle"):
            card.text(x0, card.top + 0.14, p["subtitle"], size=9, color=MUTED)
        lw = _label_col(card, [r["label"] for r in p["rows"]], 10)
        ax = card.axes(x0=x0 + lw + 0.12, x1=x0 + width, top=0.5 if p.get("subtitle") else 0.32)
        _hbars(card, ax, p["rows"], p.get("fmt", "{:.1f}"), p.get("highlight") or [], p.get("ref"))


def tiles(card: Card, spec: dict):
    ts = spec["tiles"]
    k = len(ts)
    gutter = 0.22
    width = (card.W - 2 * MARGIN - gutter * (k - 1)) / k
    top, bottom = card.top - 0.05, card.H - card.bottom
    for j, t in enumerate(ts):
        x0 = MARGIN + j * (width + gutter)
        card.fig.add_artist(FancyBboxPatch((x0 / card.W, 1 - bottom / card.H), width / card.W,
                                           (bottom - top) / card.H, boxstyle="round,pad=0,rounding_size=0.012",
                                           transform=card.fig.transFigure, color=PLANE, lw=0))
        if t.get("highlight"):
            card.fig.add_artist(Rectangle((x0 / card.W, 1 - (top + 0.05) / card.H), width / card.W,
                                          0.05 / card.H, transform=card.fig.transFigure, color=ACCENT, lw=0))
        y = top + 0.24
        y += card.text(x0 + 0.2, y, t["value"], size=34, weight="semibold", color=INK) + 0.1
        for line in card.wrap(t["label"], width - 0.4, size=10.5, weight="medium"):
            y += card.text(x0 + 0.2, y, line, size=10.5, weight="medium", color=INK) + 0.03
        y += 0.06
        for line in card.wrap(t.get("context", ""), width - 0.4, size=9.5):
            y += card.text(x0 + 0.2, y, line, size=9.5, color=INK_2) + 0.03


KINDS = {"bars": bars, "trend": trend, "grouped": grouped, "split": split, "diverging": diverging,
         "dumbbell": dumbbell, "panels": panels, "tiles": tiles}


def _legend(spec: dict) -> list[tuple[str, str, str]] | None:
    kind = spec["kind"]
    if kind == "trend" and len(spec["series"]) > 1:
        return [(s["name"], NEUTRAL if s.get("muted") else SERIES[k], "line") for k, s in enumerate(spec["series"])]
    if kind == "grouped" and len(spec["series"]) > 1:
        return [(s["name"], SERIES[k], "sq") for k, s in enumerate(spec["series"])]
    if kind == "split":
        colors = [ACCENT, NEUTRAL_LIGHT, NEUTRAL]
        return [(p, colors[k], "sq") for k, p in enumerate(spec["parts"])]
    if kind == "dumbbell":
        a, b, ref = spec.get("names", ["Usual", "This game", "League"])
        return [(b, ACCENT, "sq"), (a, NEUTRAL, "sq"), (ref, INK_2, "tick")]
    return spec.get("legend")


def _height(spec: dict) -> float:
    if spec.get("height"):
        return spec["height"]
    rows = spec.get("rows") or []
    if spec["kind"] == "tiles":
        return 4.0
    if spec["kind"] == "dumbbell":
        return max(4.5, 2.8 + 0.42 * len(rows))
    if spec["kind"] in ("split", "diverging") or (spec["kind"] == "bars"
                                                               and spec.get("orientation", "h") == "h"):
        return max(4.5, 2.4 + 0.42 * len(rows))
    return 4.5


def render(spec: dict, path: Path, kicker: str = "") -> Path:
    if spec.get("kind") not in KINDS:
        raise ValueError(f"chart {spec.get('id')}: unknown kind {spec.get('kind')!r} (use one of {', '.join(KINDS)})")
    card = Card(spec["title"], spec.get("subtitle"), spec.get("source", "nflverse"),
                kicker=spec.get("kicker", kicker), width=spec.get("width", 8.0), height=_height(spec),
                legend=_legend(spec))
    KINDS[spec["kind"]](card, spec)
    return card.save(path)


# --- the week's chart specs ------------------------------------------------------------------------
def specs_path(week: int) -> Path:
    return config.NOTES_DIR / f"{config.week_tag(week)}_charts.json"


def load_specs(week: int) -> list[dict]:
    p = specs_path(week)
    if not p.exists():
        return []
    raw = json.loads(p.read_text())
    return raw["charts"] if isinstance(raw, dict) else raw


def chart_path(week: int, chart_id: str) -> Path:
    return config.CHARTS_DIR / f"{config.week_tag(week)}_{chart_id}.png"


def render_week(week: int, kicker: str = "") -> list[tuple[dict, Path]]:
    """Draw every chart in the week's spec file. Returns (spec, png) pairs in file order."""
    out = []
    for spec in load_specs(week):
        out.append((spec, render(spec, chart_path(week, spec["id"]), kicker)))
    return out
