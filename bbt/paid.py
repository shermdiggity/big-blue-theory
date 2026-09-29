"""Ticket 9: check a browser-agent extract before trusting it.

Checks:
  errors   (the extract is rejected)
    - required fields present, game/week/team match
    - every null is listed in missing_fields
    - percentages inside 0-100
    - distribution percentages sum to ~100
  warnings (look before you publish)
    - a reported number doesn't appear anywhere in the raw page text (possible invention)
    - snap totals don't match the free play-by-play count
    - SūmerBrain gave different answers to the same question (mark "unreliable")
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from bbt import config

REQUIRED = ["schema_version", "season", "week", "game_id", "team", "extracted_at", "sources",
            "sumer", "nfl_pro", "missing_fields", "raw_text_file"]
PCT_SUM_TOLERANCE = 2.0
SNAP_TOLERANCE = 0.05


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_numbers: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        lines = [f"{'PASS' if self.ok else 'FAIL'}: {len(self.errors)} errors, "
                 f"{len(self.warnings)} warnings, {self.checked_numbers} numbers traced to page text"]
        lines += [f"  ERROR  {e}" for e in self.errors]
        lines += [f"  warn   {w}" for w in self.warnings]
        return "\n".join(lines)


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


def _number_in_text(value: float, text_numbers: set[str]) -> bool:
    candidates = {str(value)}
    if isinstance(value, float):
        candidates |= {f"{value:.1f}", f"{value:.2f}", f"{value:.0f}" if value.is_integer() else ""}
        if value.is_integer():
            candidates.add(str(int(value)))
    return bool(candidates & text_numbers)


def check(extract: dict, raw_text: str | None, week: int, game_id: str,
          free_offense_snaps: int | None = None, free_defense_snaps: int | None = None) -> Report:
    r = Report()

    for k in REQUIRED:
        if k not in extract:
            r.errors.append(f"missing required field `{k}`")
    if r.errors:
        return r
    if extract["game_id"] != game_id:
        r.errors.append(f"game_id {extract['game_id']} != expected {game_id}")
    if extract["week"] != week:
        r.errors.append(f"week {extract['week']} != {week}")
    if extract["team"] != config.TEAM:
        r.errors.append(f"team {extract['team']} != {config.TEAM}")

    missing = set(extract.get("missing_fields") or [])
    leaves = list(_walk({k: extract[k] for k in ("sumer", "nfl_pro") if k in extract}))

    # every null accounted for
    for path, v in leaves:
        if v is None and path not in missing:
            r.errors.append(f"`{path}` is null but not listed in missing_fields")

    # percent ranges + distributions that should sum to ~100
    for path, v in leaves:
        if (path.endswith(".pct") or path.endswith("_rate")) and isinstance(v, (int, float)):
            if not 0 <= v <= 100:
                r.errors.append(f"`{path}` = {v} is outside 0-100")
            elif 0 < v <= 1 and path.endswith("_rate"):
                r.warnings.append(f"`{path}` = {v}: looks like a fraction, pages show 0-100")
    for path, dist in _distributions(extract):
        pcts = [d.get("pct") for d in dist if d.get("pct") is not None]
        if pcts and abs(sum(pcts) - 100) > PCT_SUM_TOLERANCE:
            r.errors.append(f"`{path}` percentages sum to {sum(pcts):.1f}, not ~100")

    # snaps vs free data
    for side, free in (("offense", free_offense_snaps), ("defense", free_defense_snaps)):
        paid = (extract.get("sumer") or {}).get(side, {}).get("snaps")
        if paid and free and abs(paid - free) / free > SNAP_TOLERANCE:
            r.warnings.append(f"sumer.{side}.snaps = {paid} but free play-by-play has {free} "
                              f"({(paid - free) / free:+.0%})")
        personnel = (extract.get("sumer") or {}).get(side, {}).get("personnel") or []
        counts = [d.get("count") for d in personnel if d.get("count") is not None]
        if paid and counts and abs(sum(counts) - paid) > max(2, paid * 0.02):
            r.warnings.append(f"sumer.{side}.personnel counts sum to {sum(counts)}, snaps = {paid}")

    # trace every number to the raw text
    if raw_text is None:
        r.errors.append("raw page text file not found. Can't verify any number")
    else:
        text_numbers = set(re.findall(r"-?\d+(?:\.\d+)?", raw_text.replace(",", "")))
        for path, v in leaves:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            r.checked_numbers += 1
            if not _number_in_text(v, text_numbers):
                r.warnings.append(f"`{path}` = {v} not found in raw page text")

    for q in extract.get("sumerbrain") or []:
        if q.get("answer_1", "").strip() != q.get("answer_2", "").strip() and not q.get("consistent"):
            r.warnings.append(f"SūmerBrain claim line {q.get('claim_line')}: answers differ -> unreliable")
        if not q.get("counts_given"):
            r.warnings.append(f"SūmerBrain claim line {q.get('claim_line')}: no raw counts given")
    return r


def _distributions(extract: dict):
    s, n = extract.get("sumer") or {}, extract.get("nfl_pro") or {}
    for side in ("offense", "defense"):
        for key in ("personnel", "formations", "coverage_faced", "coverage"):
            d = (s.get(side) or {}).get(key)
            if d:
                yield f"sumer.{side}.{key}", d
    if n.get("run_scheme"):
        yield "nfl_pro.run_scheme", n["run_scheme"]


def free_snap_counts(game: pl.DataFrame, team: str = config.TEAM) -> tuple[int, int]:
    """Offensive/defensive snaps from play-by-play: run, pass and wiped plays (not pre-snap flags)."""
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
    off, de = free_snap_counts(game)
    return check(extract, raw, week, game_id, off, de)
