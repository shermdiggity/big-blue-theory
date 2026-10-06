"""Ticket 9: check a browser-agent extract (schema v1) before trusting it.

Checks:
  errors   (the extract is rejected)
    - required fields present, game/week/team match
    - every null is listed in missing_fields
    - percentages inside 0-100
    - rate breakdowns (personnel, run concepts, split shares) sum to ~100
  warnings (look before you publish)
    - a number doesn't appear in the raw page text (possible invention); values the agent
      read from a screenshot are exempt but must pass the consistency checks
    - a split's share % doesn't match its own counts
    - different split tables disagree on the total (e.g. by-coverage vs pressure attempts)
    - counts don't match the free play-by-play (plays, pass attempts, sacks, runs)
    - SūmerBrain answers differ or give no counts
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from bbt import config

REQUIRED = ["schema_version", "season", "week", "game_id", "team", "opponent", "extracted_at",
            "sources", "sumer", "missing_fields", "raw_text_file"]
PCT_SUM_TOLERANCE = 2.0
SHARE_TOLERANCE = 1.5
NUMERIC_STR = re.compile(r"^[-−+]?\d[\d,]*(?:\.\d+)?\s*(?:%|sec|s|yds)?$")   # percentage points between a split's share % and its counts


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_numbers: int = 0
    screenshot_numbers: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        lines = [f"{'PASS' if self.ok else 'FAIL'}: {len(self.errors)} errors, {len(self.warnings)} warnings, "
                 f"{self.checked_numbers} numbers traced to page text, "
                 f"{self.screenshot_numbers} from screenshots"]
        lines += [f"  ERROR  {e}" for e in self.errors]
        lines += [f"  warn   {w}" for w in self.warnings]
        return "\n".join(lines)


@dataclass
class FreeCounts:
    """What the free play-by-play says, in Sūmer's denominators."""
    off_plays: int        # NYG run + pass + kneel + spike (no penalty snaps)
    pass_att: int         # NYG pass attempts incl. sacks (Sūmer game-page passing denominator)
    sacks_taken: int
    rushes: int           # NYG designed runs + scrambles
    opp_pass_att: int     # what NYG's defense faced
    opp_rushes: int
    sacks_made: int


def paths(week: int) -> tuple[Path, Path]:
    tag = config.week_tag(week)
    return config.PAID_DIR / f"{tag}.json", config.PAID_DIR / f"{tag}_raw.txt"


def load(week: int) -> dict | None:
    p, _ = paths(week)
    return json.loads(p.read_text()) if p.exists() else None


def _walk(obj, prefix=""):
    """Yield (dotted_path, value) for every leaf."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def _number_forms(value: float) -> set[str]:
    forms = {str(value)}
    if isinstance(value, float):
        forms |= {f"{value:.1f}", f"{value:.2f}", f"{value:.3f}"}
        if value.is_integer():
            forms.add(str(int(value)))
    if isinstance(value, (int, float)) and value < 0:
        forms |= {f.replace("-", "−") for f in forms}  # pages often use a real minus sign
    return forms


def _splits(extract: dict):
    """Yield (path, rows) for every split table in the game page."""
    gp = (extract.get("sumer") or {}).get("game_page") or {}
    for side in ("nyg", "opp"):
        tab = gp.get(side) or {}
        for group in ("passing", "rushing"):
            for key, rows in (tab.get(group) or {}).items():
                if rows:
                    yield f"sumer.game_page.{side}.{group}.{key}", rows


def _dists(extract: dict):
    gp = (extract.get("sumer") or {}).get("game_page") or {}
    for side in ("nyg", "opp"):
        tend = ((gp.get(side) or {}).get("tendencies")) or {}
        for key in ("offensive_personnel", "run_concepts", "defensive_personnel"):
            if tend.get(key):
                yield f"sumer.game_page.{side}.tendencies.{key}", [d.get("pct") for d in tend[key]]


def _total(rows, key):
    vals = [r.get(key) for r in rows if isinstance(r.get(key), (int, float))]
    return sum(vals) if vals else None


def check(extract: dict, raw_text: str | None, week: int, game_id: str,
          free: FreeCounts | None = None) -> Report:
    r = Report()
    for k in REQUIRED:
        if k not in extract:
            r.errors.append(f"missing required field `{k}`")
    if r.errors:
        return r
    if extract.get("schema_version") != "v1":
        r.errors.append(f"schema_version {extract.get('schema_version')!r}, expected 'v1'")
    if extract["game_id"] != game_id:
        r.errors.append(f"game_id {extract['game_id']} != expected {game_id}")
    if extract["week"] != week:
        r.errors.append(f"week {extract['week']} != {week}")
    if extract["team"] != config.TEAM:
        r.errors.append(f"team {extract['team']} != {config.TEAM}")

    missing = set(extract.get("missing_fields") or [])
    shots = set(extract.get("screenshot_fields") or [])
    leaves = list(_walk({k: extract[k] for k in ("sumer", "nfl_pro") if extract.get(k)}))

    for path, v in leaves:
        if v is None and path not in missing:
            r.errors.append(f"`{path}` is null but not listed in missing_fields")
        is_pct = (path.endswith(("pct", "_rate")) or path.endswith("%") or "%" in path.rsplit(".", 1)[-1])
        if is_pct and isinstance(v, (int, float)) and not 0 <= v <= 100:
            r.errors.append(f"`{path}` = {v} is outside 0-100")

    for path, pcts in _dists(extract):
        vals = [p for p in pcts if p is not None]
        if vals and abs(sum(vals) - 100) > PCT_SUM_TOLERANCE:
            r.errors.append(f"`{path}` sums to {sum(vals):.1f}, not ~100")

    # split tables: shares sum to ~100, shares match their own counts
    totals: dict[str, dict[str, float]] = {}
    for path, rows in _splits(extract):
        shares = [x.get("share_pct") for x in rows if x.get("share_pct") is not None]
        if shares and abs(sum(shares) - 100) > PCT_SUM_TOLERANCE and not path.endswith("by_route"):
            r.errors.append(f"`{path}` shares sum to {sum(shares):.1f}, not ~100")
        # Sūmer passing splits: "comp/att" excludes sacks, but the share % is of dropbacks
        # (att + sacks). Rushing splits have no sacks, so this is plain att there.
        def plays(x):
            return (x.get("att") or 0) + (x.get("sacks") or 0)
        att_total = sum(plays(x) for x in rows if x.get("att") is not None)
        if att_total and not path.endswith("by_route"):  # routes leave out unlabeled throws
            side_group = path.rsplit(".", 1)[0]
            totals.setdefault(side_group, {})[path.rsplit(".", 1)[1]] = att_total
            for i, x in enumerate(rows):
                if x.get("share_pct") is not None and x.get("att") is not None:
                    implied = 100 * plays(x) / att_total
                    if abs(implied - x["share_pct"]) > SHARE_TOLERANCE:
                        r.warnings.append(f"`{path}[{i}]` ({x['label']}): share {x['share_pct']}% but "
                                          f"{plays(x)}/{att_total} plays = {implied:.1f}%")
    for side_group, by_key in totals.items():
        if len(set(by_key.values())) > 1:
            r.warnings.append(f"`{side_group}` split tables disagree on total plays: {by_key}")

    if free:
        _free_checks(extract, free, totals, r)
    if extract.get("nfl_pro"):
        _nfl_pro_checks(extract["nfl_pro"], r)

    if raw_text is None:
        r.errors.append("raw page text file not found. Can't verify any number")
    else:
        text = raw_text.replace(",", "")
        text_numbers = set(re.findall(r"[-−]?\d+(?:\.\d+)?", text))
        for path, v in leaves:
            if isinstance(v, str) and NUMERIC_STR.match(v.strip()):
                v = _num(v)  # verbatim "12.3%", "1.23 sec", "-4.5%"
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            if path in shots:
                r.screenshot_numbers += 1
                continue
            r.checked_numbers += 1
            if not (_number_forms(v) & text_numbers):
                r.warnings.append(f"`{path}` = {v} not found in raw page text")

    for q in extract.get("sumerbrain") or []:
        if q.get("answer_2") and q.get("answer_1", "").strip() != q["answer_2"].strip() and not q.get("consistent"):
            r.warnings.append(f"SūmerBrain claim line {q.get('claim_line')}: answers differ -> unreliable")
        if not q.get("counts_given"):
            r.warnings.append(f"SūmerBrain claim line {q.get('claim_line')}: no raw counts given")
    return r


def _free_checks(extract: dict, free: FreeCounts, totals: dict, r: Report) -> None:
    def warn_if(label, paid, freev, tol=1):
        paid = _num(paid)
        if paid is not None and freev is not None and abs(paid - freev) > tol:
            r.warnings.append(f"{label}: Sūmer {paid} vs free play-by-play {freev}")

    plays = ((extract.get("sumer") or {}).get("teams_offense") or {}).get("Plays")
    warn_if("NYG offensive plays (Teams > Offense 'Plays')", plays, free.off_plays)

    nyg_pass = totals.get("sumer.game_page.nyg.passing", {})
    opp_pass = totals.get("sumer.game_page.opp.passing", {})
    nyg_rush = totals.get("sumer.game_page.nyg.rushing", {})
    opp_rush = totals.get("sumer.game_page.opp.rushing", {})
    if nyg_pass:
        warn_if("NYG dropbacks (game page splits, att + sacks)", max(nyg_pass.values()), free.pass_att)
    if opp_pass:
        warn_if(f"{extract['opponent']} dropbacks (game page splits, att + sacks)", max(opp_pass.values()), free.opp_pass_att)
    if nyg_rush:
        warn_if("NYG rush attempts (game page splits)", max(nyg_rush.values()), free.rushes, tol=2)
    if opp_rush:
        warn_if(f"{extract['opponent']} rush attempts (game page splits)", max(opp_rush.values()), free.opp_rushes, tol=2)

    gp = (extract.get("sumer") or {}).get("game_page") or {}
    for side, freev, label in (("nyg", free.sacks_taken, "NYG sacks taken"),
                               ("opp", free.sacks_made, "NYG sacks made")):
        rows = (((gp.get(side) or {}).get("passing") or {}).get("pressure")) or []
        warn_if(f"{label} (Pressure split)", _total(rows, "sacks"), freev, tol=0)


def _num(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, str):
        m = re.search(r"[-−]?\d+(?:\.\d+)?", v.replace(",", ""))
        return float(m.group().replace("−", "-")) if m else None
    return None


def _nfl_pro_checks(np_: dict, r: Report) -> None:
    """Internal consistency inside NFL Pro."""
    film = np_.get("film_room") or {}
    passing = ((np_.get("game_stats") or {}).get("passing")) or []
    qbp = [_num(row.get("QBP")) for row in passing if _num(row.get("QBP")) is not None]
    if film.get("pressure_plays") is not None and qbp and abs(sum(qbp) - film["pressure_plays"]) > 0:
        r.warnings.append(f"NFL Pro: Film Room pressure plays {film['pressure_plays']} != sum of QBP "
                          f"on the Stats tab {sum(qbp):.0f}")
    by_team: dict[str, dict] = {}
    for row in np_.get("personnel") or []:
        # With Play Type = All, "ALL" includes kickoffs/punts that have no personnel grouping.
        if str(row.get("play_type_filter", "")).lower() in ("all", "none", ""):
            continue
        by_team.setdefault(row["team"], {})[row["personnel"]] = row.get("plays")
    for team, d in by_team.items():
        total = d.get("ALL")
        parts = [v for k, v in d.items() if k != "ALL" and v is not None]
        if total is not None and parts and abs(sum(parts) - total) > 1:
            r.warnings.append(f"NFL Pro personnel for {team}: groupings sum to {sum(parts)} but ALL = {total}")


# Same idea measured by both paid sources: (label, sumer path, nfl_pro path). Paths are
# tuples into the extract; the last element of a Sūmer/NFL Pro row path is the column label.
CROSS = [
    ("NYG defense blitz rate", ("sumer", "teams_defense", "Blitz %"),
     ("nfl_pro", "ngs_team_defense", "pass_defense", "Blitz %")),
    ("NYG defense pressure rate", ("sumer", "teams_defense", "Pressure %"),
     ("nfl_pro", "ngs_team_defense", "pass_defense", "QBP %")),
    ("NYG defense time to pressure", ("sumer", "teams_defense", "TTP"),
     ("nfl_pro", "ngs_team_defense", "pass_defense", "TTP")),
    ("Opponent time to throw", ("sumer", "teams_defense", "TTT"),
     ("nfl_pro", "ngs_team_defense", "pass_defense", "TTT")),
    ("NYG QB time to throw", ("sumer", "game_page", "nyg", "pass_game", "avg_time_to_throw"),
     ("nfl_pro", "ngs_team_offense", "passing", "TTT")),
]


def _dig(d, path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def cross_source(extract: dict) -> list[dict]:
    """Where Sūmer and NFL Pro measure the same thing, side by side. Disagreement is content,
    not an error: they chart independently. Big gaps are worth a sentence in the post."""
    rows = []
    qb_rows = ((_dig(extract, ("nfl_pro", "game_stats", "passing"))) or [])
    team = extract.get("team", config.TEAM)

    def qb_col(nyg_qb: bool, col: str):
        """Fallback when the NGS team pages weren't read: the QB rows on the game Stats tab.
        The opponent QB's row describes NYG's defense (blitz faced, pressures, TTT)."""
        for row in qb_rows:
            is_nyg = f"({team})" in str(row.get("Player", "")) or row.get("Team") == team
            if is_nyg == nyg_qb and row.get(col) is not None:
                return _num(row.get(col))
        return None
    fallback = {"NYG defense blitz rate": (False, "Blitz %"), "NYG defense pressure rate": (False, "QBP %"),
                "Opponent time to throw": (False, "TTT"), "NYG QB time to throw": (True, "TTT")}
    for label, sp, npp in CROSS:
        a, b = _num(_dig(extract, sp)), _num(_dig(extract, npp))
        if b is None and label in fallback:
            b = qb_col(*fallback[label])
        if a is not None or b is not None:
            rows.append({"measure": label, "sumer": a, "nfl_pro": b,
                         "gap": None if a is None or b is None else round(b - a, 2)})
    pers = {(p["team"], p["personnel"]): p.get("plays") for p in (_dig(extract, ("nfl_pro", "personnel")) or [])}
    s11 = next((d.get("pct") for d in (_dig(extract, ("sumer", "game_page", "nyg", "tendencies",
                                                      "offensive_personnel")) or []) if d.get("label", "").startswith("11")), None)
    n11 = pers.get(("NYG", "1 RB, 1 TE, 3 WR"))
    if s11 is not None or n11 is not None:
        rows.append({"measure": "NYG 11 personnel (Sūmer %, NFL Pro plays)", "sumer": s11, "nfl_pro": n11, "gap": None})
    return rows


def free_counts(game: pl.DataFrame, team: str = config.TEAM) -> FreeCounts:
    rp = game.filter(pl.col("play_type").is_in(["pass", "run"]))
    off = rp.filter(pl.col("posteam") == team)
    de = rp.filter(pl.col("defteam") == team)
    kneels = game.filter((pl.col("posteam") == team) & pl.col("play_type").is_in(["qb_kneel", "qb_spike"])).height
    return FreeCounts(
        off_plays=off.height + kneels,
        pass_att=int(off["pass_attempt"].sum()),
        sacks_taken=int(off["sack"].sum()),
        rushes=int(off["rush_attempt"].sum()),
        opp_pass_att=int(de["pass_attempt"].sum()),
        opp_rushes=int(de["rush_attempt"].sum()),
        sacks_made=int(de["sack"].sum()),
    )


def free_snap_counts(game: pl.DataFrame, team: str = config.TEAM) -> tuple[int, int]:
    """Offensive/defensive snaps from play-by-play: run, pass and wiped plays (not pre-snap flags).

    Matches PFR/official snap counts. (Sūmer's 'Plays' excludes penalty snaps: see free_counts.)
    """
    from bbt.penalties import classify

    scrimmage = game.filter(pl.col("play_type").is_in(["pass", "run", "qb_kneel", "qb_spike", "no_play"]))
    scrimmage = scrimmage.filter(
        (pl.col("play_type") != "no_play")
        | pl.struct("desc", "play_type").map_elements(
            lambda r: classify(r["desc"], r["play_type"]) != "pre_snap", return_dtype=pl.Boolean)
    )
    return (scrimmage.filter(pl.col("posteam") == team).height,
            scrimmage.filter(pl.col("defteam") == team).height)


def run_check(week: int, game: pl.DataFrame, game_id: str) -> Report | None:
    extract = load(week)
    if extract is None:
        return None
    _, raw_path = paths(week)
    raw = raw_path.read_text() if raw_path.exists() else None
    return check(extract, raw, week, game_id, free_counts(game))
