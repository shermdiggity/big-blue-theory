"""Build a paid-data extract straight from pasted page text.

Sometimes the browser extension sends back page text instead of the JSON block. The page
layouts are regular enough to parse: Sūmer's split rows ("Cover 3 • 12.3% | +0.45 | 67% COMP |
4/6 comp · 50 yds · 1 sacks"), its tables (header line + " | " rows), and "Label Value | ..."
team rows. Values are kept exactly as shown; nothing is computed.

    python -m bbt ingest-raw 4 private/paid/2026_wk04_raw.txt
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from bbt import config, data

PASS_SPLIT = re.compile(r"^(?P<label>.+?) • (?P<share>[\d.]+)% \| (?P<epa>[+-]?[\d.]+) \| (?P<comp_pct>\d+)% COMP \| "
                        r"(?P<comp>\d+)/(?P<att>\d+) comp · (?P<yds>-?\d+) yds · (?P<sacks>\d+) sacks")
RUSH_SPLIT = re.compile(r"^(?P<label>.+?) • (?P<share>[\d.]+)% \| (?P<epa>[+-]?[\d.]+) \| (?P<yaco>\d+) YACo \| "
                        r"(?P<att>\d+) att · (?P<yds>-?\d+) yds")
GAP_SPLIT = re.compile(r"^(?P<label>[A-D] Gap|Other) (?P<epa>[+-]?[\d.]+) \| (?P<yaco>\d+) YACo \| (?P<att>\d+) att · (?P<yds>-?\d+) yds")
ROUTE_SPLIT = re.compile(r"^(?:\[label from screenshot: )?(?P<label>[A-Za-z ]+?)\]? (?P<epa>[+-]?[\d.]+) (?P<comp_pct>\d+)% COMP "
                         r"(?P<comp>\d+) comp · (?P<att>\d+) att · (?P<yds>-?\d+) yds")
DIST_ITEM = re.compile(r"([\w ]+?) • ([\d.]+)%")


def _n(s):
    s = s.replace("−", "-")
    return float(s) if "." in s else int(s)


def _sections(text: str) -> dict[str, list[str]]:
    out, cur = {}, None
    for line in text.splitlines():
        if line.startswith("=== "):
            cur = line.strip("= ").strip()
            out[cur] = []
        elif cur and line.strip():
            out[cur].append(line.strip())
    return out


def _find(secs, *needles):
    for k, v in secs.items():
        if all(n.lower() in k.lower() for n in needles):
            return v
    return []


def _splits(lines, kind):
    rows = []
    for ln in lines:
        m = (PASS_SPLIT if kind == "pass" else RUSH_SPLIT).match(ln) or (GAP_SPLIT.match(ln) if kind == "rush" else None)
        if not m:
            continue
        d = m.groupdict()
        row = {"label": d["label"].strip(), "share_pct": _n(d["share"]) if d.get("share") else None, "epa": _n(d["epa"]),
               "att": _n(d["att"]), "yds": _n(d["yds"])}
        if kind == "pass":
            row |= {"comp_pct": _n(d["comp_pct"]), "comp": _n(d["comp"]), "sacks": _n(d["sacks"])}
        else:
            row |= {"yaco": _n(d["yaco"])}
        rows.append(row)
    return rows or None


def _routes(lines):
    rows = [{"label": m["label"].strip(), "epa": _n(m["epa"]), "comp_pct": _n(m["comp_pct"]), "comp": _n(m["comp"]),
             "att": _n(m["att"]), "yds": _n(m["yds"])} for ln in lines if (m := ROUTE_SPLIT.match(ln))]
    return rows or None


def _dist(line):
    return [{"label": a.strip(), "pct": _n(b)} for a, b in DIST_ITEM.findall(line)] or None


def _label_rate(lines, label):
    for ln in lines:
        m = re.search(rf"{re.escape(label)} ([\d.]+)%", ln)
        if m:
            return _n(m.group(1))
    return None


def _team_row(lines):
    if not lines:
        return None
    row = {}
    for part in " | ".join(lines).split(" | "):
        k, _, v = part.strip().rpartition(" ")
        if k:
            row[k] = v
    return row


def _table(lines):
    if len(lines) < 2:
        return None
    head = [h.strip() for h in lines[0].split("|")]
    return [dict(zip(head, [c.strip() for c in ln.split("|")])) for ln in lines[1:]]


def _team_tab(secs, team_name):
    t = _find(secs, team_name, "Team Tendencies")
    tend = {}
    for ln in t:
        if ln.startswith("Offensive Personnel Rate"):
            tend["offensive_personnel"] = _dist(ln.split(":", 1)[1])
        elif ln.startswith("Run Concept Rate"):
            tend["run_concepts"] = _dist(ln.split(":", 1)[1])
        elif ln.startswith("Defensive Personnel Rate"):
            tend["defensive_personnel"] = _dist(ln.split(":", 1)[1])
        elif ln.startswith("Man Zone Rate"):
            d = {x["label"]: x["pct"] for x in _dist(ln.split(":", 1)[1]) or []}
            tend["man_rate"], tend["zone_rate"] = d.get("Man"), d.get("Zone")
    for key, label in (("blitz_rate", "Blitz Rate"), ("pressure_rate", "Pressure Rate"),
                       ("tfl_rate", "Tackle for Loss Rate"), ("missed_tackle_rate", "Missed Tackle Rate"),
                       ("play_action_rate", "Play Action Rate"), ("screen_rate", "Screen Rate")):
        v = next((float(m.group(1)) for ln in t if (m := re.search(rf"{label} ([\d.]+)%", ln))), None)
        tend[key] = v
    pg = " ".join(_find(secs, team_name, "Pass Game"))

    def grab(pat, s):
        m = re.search(pat, s)
        return _n(m.group(1)) if m else None
    rg = " ".join(_find(secs, team_name, "Run Game"))
    return {
        "tendencies": tend,
        "pass_game": {"pass_yards": grab(r"(-?\d+) Pass Yards", pg), "epa_per_play": grab(r"([+-]?[\d.]+) Pass EPA", pg),
                      "avg_time_to_pressure": grab(r"Time to Pressure ([\d.]+)", pg),
                      "avg_time_to_throw": grab(r"Time to Throw ([\d.]+)", pg), "adot": grab(r"Depth of Target ([\d.]+)", pg)},
        "passing": {k: (_routes(_find(secs, team_name, "By Route")) if k == "by_route"
                        else _splits(_find(secs, team_name, "Passing Performance", lab), "pass"))
                    for k, lab in (("by_personnel", "By Personnel"), ("by_coverage", "By Coverage"),
                                   ("by_route", "By Route"), ("pressure", "> Pressure"), ("blitz", "> Blitz"))},
        "run_game": {"attempts": grab(r"(\d+) Attempts", rg), "rush_yards": grab(r"(-?\d+) Rush Yards", rg),
                     "yards_after_contact": grab(r"(\d+) Yards After Contact", rg),
                     "epa_per_play": grab(r"([+-]?[\d.]+) Rush EPA", rg)},
        "rushing": {k: _splits(_find(secs, team_name, "Rushing Performance", lab), "rush")
                    for k, lab in (("by_personnel", "By Personnel"), ("by_concept", "By Concept"),
                                   ("by_gap", "By Gap"), ("by_box", "By Box"))},
    }


def _nflpro_rows(lines):
    rows = []
    for ln in lines:
        parts = [p.strip() for p in ln.split(" | ")]
        row = {"Player": parts[0]}
        for p in parts[1:]:
            k, _, v = p.rpartition(" ")
            row[k] = v
        rows.append(row)
    return rows or None


def build(week: int, raw_text: str) -> dict:
    sumer_txt, _, nfl_txt = raw_text.partition("##### nfl_pro #####")
    s, n = _sections(sumer_txt), _sections(nfl_txt)
    run_cards = _find(s, "Giants designed runs")
    if not run_cards:  # raw Sūmer play feed: "Run | NYG | 02:25 - 4th | desc | 2nd & 11 at ARZ 40 | chips..."
        for ln in sumer_txt.splitlines():
            m = re.match(rf"^Run \| {config.TEAM} \| (\d\d:\d\d) - (\w+) \| (.*)$", ln.strip())
            if m:
                q = {"1st": "Q1", "2nd": "Q2", "3rd": "Q3", "4th": "Q4"}.get(m.group(2), m.group(2))
                run_cards.append(f"{q} {m.group(1)} | {m.group(3)}")
    nyg = _team_tab(s, "New York Giants tab")
    if run_cards:
        nyg["run_cards"] = run_cards
    players = {}
    for key, lab in (("offensive_line", "Offensive Line"), ("cornerback", "Cornerback"), ("safety", "Safety"),
                     ("linebacker", "Linebacker"), ("edge_rusher", "Edge Rusher"),
                     ("defensive_interior", "Defensive Interior")):
        players[key] = _table(_find(s, "Players", lab))
    pers = []
    for ln in _find(n, "Play By Play", "Personnel"):
        for m in re.finditer(r"(ALL|(?:6 OL, )?\d RB, \d TE, \d WR) (\d+)", ln):
            pers.append({"team": "NYG", "personnel": m.group(1), "plays": int(m.group(2)), "play_type_filter": "All"})
    film = " ".join(_find(n, "Film Room"))

    def fr(pat):
        m = re.search(pat, film)
        return int(m.group(1)) if m else None
    ext = {
        "schema_version": "v1", "season": config.SEASON, "week": week, "game_id": data.game_id_for(week),
        "team": config.TEAM, "opponent": data.opponent_for(week),
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
        "sources": [{"source": "sumer", "page": "SūmerLive game page, Teams, Players"},
                    {"source": "nfl_pro", "page": "Game Stats, Play By Play, Film Room, Insights"}],
        "sumer": {"game_page": {"nyg": nyg, "opp": _team_tab(s, "Cardinals tab") if _find(s, "Cardinals tab") else None},
                  "teams_offense": _team_row(_find(s, "Teams > Offense")),
                  "teams_defense": _team_row(_find(s, "Teams > Defense")),
                  "players": players},
        "nfl_pro": {"game_stats": {"passing": _nflpro_rows(_find(n, "Passing")),
                                   "rushing": (_nflpro_rows(_find(n, "Rushing", "NYG")) or []) + (_nflpro_rows(_find(n, "Rushing", "ARI")) or []),
                                   "receiving": _nflpro_rows(_find(n, "Receiving"))},
                    "personnel": pers or None,
                    "film_room": {"all_plays": fr(r"(\d+) plays matching"), "pressure_plays": fr(r"Pressure: (\d+)"),
                                  "blitz_plays": fr(r"Blitz: (\d+)")},
                    "insights": _find(n, "Insights") or None},
        "screenshot_fields": [], "missing_fields": [], "raw_text_file": f"{config.week_tag(week)}_raw.txt",
        "sumerbrain": [], "extra_asks": [], "agent_notes": "Built from pasted page text (no JSON block).",
    }
    # record every null so the checker knows they're known gaps
    def walk(o, p=""):
        if isinstance(o, dict):
            for k, v in o.items():
                yield from walk(v, f"{p}.{k}" if p else k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                yield from walk(v, f"{p}[{i}]")
        else:
            yield p, o
    ext["missing_fields"] = [p for p, v in walk({"sumer": ext["sumer"], "nfl_pro": ext["nfl_pro"]}) if v is None]
    return ext


def ingest_raw(week: int, raw_path) -> str:
    raw = open(raw_path).read()
    ext = build(week, raw)
    tag = config.week_tag(week)
    config.PAID_DIR.mkdir(parents=True, exist_ok=True)
    (config.PAID_DIR / f"{tag}.json").write_text(json.dumps(ext, indent=1, ensure_ascii=False))
    dest = config.PAID_DIR / f"{tag}_raw.txt"
    if str(dest) != str(raw_path):
        dest.write_text(raw)
    return f"built {tag}.json from page text ({len(ext['missing_fields'])} known gaps)"
