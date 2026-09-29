"""Ticket 11: your Sunday notes as input, checked against the data.

Note format, one claim per line (lines starting with # are ignored):

    who | what you saw | evidence to check[, more evidence] [| type]

    Nabers | open deep all game, Winston never looked | deep targets, separation, read thrown
    OL | lost the pass pro battle on 3rd down | pressure, sacks | scheme
    Daboll | too conservative on 4th down | 4th downs | decisions

`type` is players / scheme / decisions. If you leave it off it's guessed from `who`.

Notes can come from other people too, for backtesting or comparison:
    private/notes/2026_wk03.md           you (source "me")
    private/notes/2026_wk03_skinner.md   source "skinner"
Keep the original take and its link on a `#` comment line above each claim, so every
claim can be traced back to what was actually said.

`bbt notes N` writes private/notes/<week>_verdicts.csv with the free-data evidence for each
claim, plus the SūmerBrain questions for anything free data can't answer. You fill in the
`verdict` column (supported / contradicted / mixed / can't check). `bbt eye` then scores your
eye across the season.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field

import polars as pl

from bbt import config

VERDICTS = ["supported", "contradicted", "mixed", "can't check"]

UNITS = {
    "ol": "offense", "o-line": "offense", "offensive line": "offense", "offense": "offense",
    "defense": "defense", "d": "defense", "secondary": "defense", "pass rush": "defense",
    "dl": "defense", "d-line": "defense", "defensive line": "defense", "lbs": "defense",
    "linebackers": "defense", "special teams": "special", "st": "special",
}
DECISION_WHO = {"daboll", "coach", "coaching", "playcalling", "play calling", "staff", "hc", "oc", "dc"}

# Evidence that needs paid data (SūmerBrain / NFL Pro) or film.
PAID_EVIDENCE = {
    "separation", "pressure rate", "coverage", "routes", "route", "man", "zone", "personnel",
    "formation", "missed tackles", "run scheme", "gap", "blocking", "yards before contact",
    "win rate", "pass rush win rate", "time to throw",
}
# Free data has a proxy (sacks, hits) but the real number is paid: check both.
PARTIAL_EVIDENCE = {"pressure", "pressures", "pass pro", "pass protection", "pass rush"}


@dataclass
class Claim:
    line_no: int
    who: str
    what: str
    evidence: list[str]
    kind: str
    evidence_values: dict = field(default_factory=dict)
    needs_paid: list[str] = field(default_factory=list)


def _guess_kind(who: str) -> str:
    w = who.strip().lower()
    if w in DECISION_WHO:
        return "decisions"
    if w in UNITS:
        return "scheme"
    return "players"


def parse(text: str) -> list[Claim]:
    claims = []
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            raise SystemExit(f"notes line {i}: need 'who | what | evidence', got: {raw!r}")
        who, what, ev = parts[0], parts[1], parts[2]
        kind = parts[3].lower() if len(parts) > 3 and parts[3] else _guess_kind(who)
        if kind not in ("players", "scheme", "decisions"):
            raise SystemExit(f"notes line {i}: type must be players/scheme/decisions, got {kind!r}")
        evidence = [e.strip().lower() for e in re.split(r"[,;]", ev) if e.strip()]
        claims.append(Claim(i, who, what, evidence, kind))
    return claims


# --------------------------------------------------------------------------- free-data checks

def _player_mask(game: pl.DataFrame, who: str, col: str) -> pl.Expr:
    """Match 'Nabers' or 'M.Nabers' against short names like 'M.Nabers'."""
    last = who.split()[-1].split(".")[-1]
    return pl.col(col).fill_null("").str.contains(f"(?i){re.escape(last)}$")


def _rp(game: pl.DataFrame) -> pl.DataFrame:
    return game.filter(pl.col("play_type").is_in(["pass", "run"]) & pl.col("epa").is_not_null())


def _player_evidence(game: pl.DataFrame, who: str, ev: str, team: str) -> dict | None:
    rp = _rp(game).filter(pl.col("posteam") == team)
    tgt = rp.filter(_player_mask(rp, who, "receiver_player_name") & (pl.col("pass") == 1))
    car = rp.filter(_player_mask(rp, who, "rusher_player_name") & (pl.col("rush") == 1))
    qb = rp.filter(_player_mask(rp, who, "passer_player_name"))
    team_targets = rp.filter(pl.col("receiver_player_name").is_not_null()).height
    ftn = tgt.filter(pl.col("has_ftn").fill_null(False))

    if ev in ("targets", "target share", "target"):
        return {"targets": tgt.height, "team_targets": team_targets,
                "target_share": round(tgt.height / team_targets, 3) if team_targets else None,
                "catches": int(tgt["complete_pass"].sum()), "yards": int(tgt["receiving_yards"].fill_null(0).sum()),
                "epa": round(tgt["epa"].sum(), 2)}
    if ev in ("deep targets", "deep", "deep target"):
        deep = tgt.filter(pl.col("air_yards") >= 20)
        team_deep = rp.filter(pl.col("air_yards") >= 20).height
        return {"deep_targets": deep.height, "team_deep_attempts": team_deep,
                "deep_catches": int(deep["complete_pass"].sum()),
                "avg_depth_of_target": round(tgt["air_yards"].mean(), 1) if tgt.height else None}
    if ev in ("read thrown", "reads", "read"):
        if ftn.is_empty():
            return {"status": "FTN not published for this game yet"}
        counts = ftn.group_by("read_thrown").len().sort("read_thrown")
        return {"read_thrown_on_targets": dict(zip(counts["read_thrown"], counts["len"])),
                "legend": "1 = first read, 2 = second read, CHK = checkdown, DES = designed, SD = scramble drill"}
    if ev in ("drops", "drop"):
        if ftn.is_empty():
            return {"status": "FTN not published for this game yet"}
        return {"drops": int(ftn["is_drop"].sum()), "catchable_targets": int(ftn["is_catchable_ball"].sum()),
                "contested_targets": int(ftn["is_contested_ball"].sum())}
    if ev in ("carries", "rushing", "runs", "yards per carry", "ypc"):
        return {"carries": car.height, "yards": int(car["rushing_yards"].fill_null(0).sum()),
                "ypc": round(car["rushing_yards"].mean(), 2) if car.height else None,
                "epa": round(car["epa"].sum(), 2), "success_rate": round(car["success"].mean(), 3) if car.height else None}
    if ev in ("epa", "efficiency", "success", "success rate"):
        plays = pl.concat([tgt, car, qb]).unique(subset=["play_id"])
        return {"plays": plays.height, "epa_total": round(plays["epa"].sum(), 2),
                "epa_per_play": round(plays["epa"].mean(), 3) if plays.height else None,
                "success_rate": round(plays["success"].mean(), 3) if plays.height else None}
    if ev in ("penalties", "penalty", "flags"):
        pens = game.filter((pl.col("penalty") == 1) & _player_mask(game, who, "penalty_player_name"))
        return {"penalties": pens.height, "yards": int(pens["penalty_yards"].sum()),
                "types": pens["penalty_type"].to_list()}
    if ev in ("sacks", "sacked", "pressure", "hits"):
        if qb.height:
            return {"dropbacks": qb.height, "sacks": int(qb["sack"].sum()), "qb_hits": int(qb["qb_hit"].sum()),
                    "note": "free data has sacks + hits only; pressure rate needs Sūmer"}
        sk = game.filter(_player_mask(game, who, "sack_player_name")
                         | _player_mask(game, who, "half_sack_1_player_name")
                         | _player_mask(game, who, "half_sack_2_player_name"))
        hits = game.filter(_player_mask(game, who, "qb_hit_1_player_name")
                           | _player_mask(game, who, "qb_hit_2_player_name"))
        return {"sacks": sk.height, "qb_hits": hits.height,
                "note": "free data has sacks + hits only; pressures need Sūmer"}
    if ev in ("completion", "accuracy", "cpoe", "passing", "interception worthy", "turnover worthy"):
        qbf = qb.filter(pl.col("has_ftn").fill_null(False))
        return {"dropbacks": qb.height, "cpoe": round(qb["cpoe"].mean(), 1) if qb.height else None,
                "epa_per_dropback": round(qb["epa"].mean(), 3) if qb.height else None,
                "interception_worthy": int(qbf["is_interception_worthy"].sum()) if qbf.height else "FTN pending",
                "throwaways": int(qbf["is_throw_away"].sum()) if qbf.height else "FTN pending"}
    return None


def _unit_evidence(game: pl.DataFrame, side: str, ev: str, team: str) -> dict | None:
    col = "posteam" if side == "offense" else "defteam"
    rp = _rp(game).filter(pl.col(col) == team)
    db = rp.filter(pl.col("pass") == 1)
    ftn = rp.filter(pl.col("has_ftn").fill_null(False))
    if ev in ("sacks", "pressure", "pass pro", "pass protection", "pass rush", "hits"):
        return {"dropbacks": db.height, "sacks": int(db["sack"].sum()), "qb_hits": int(db["qb_hit"].sum()),
                "sack_rate": round(db["sack"].mean(), 3) if db.height else None,
                "note": "pressure rate needs Sūmer"}
    if ev in ("blitz", "blitzes", "blitz rate"):
        f = ftn.filter(pl.col("pass") == 1)
        if f.is_empty():
            return {"status": "FTN not published for this game yet"}
        return {"dropbacks_charted": f.height, "blitzes": int((f["n_blitzers"] > 0).sum()),
                "blitz_rate": round((f["n_blitzers"] > 0).mean(), 3),
                "epa_vs_blitz": round(f.filter(pl.col("n_blitzers") > 0)["epa"].mean() or 0, 3)}
    if ev in ("run game", "rushing", "runs", "run defense", "run d"):
        r = rp.filter(pl.col("rush") == 1)
        return {"runs": r.height, "yards": int(r["yards_gained"].sum()),
                "ypc": round(r["yards_gained"].mean(), 2) if r.height else None,
                "epa_per_run": round(r["epa"].mean(), 3) if r.height else None,
                "success_rate": round(r["success"].mean(), 3) if r.height else None}
    if ev in ("3rd down", "third down", "3rd downs", "third downs"):
        t = rp.filter(pl.col("down") == 3)
        return {"third_downs": t.height, "conversions": int(t["third_down_converted"].sum()),
                "rate": round(t["third_down_converted"].mean(), 3) if t.height else None}
    if ev in ("penalties", "penalty", "flags"):
        pens = game.filter((pl.col("penalty") == 1) & (pl.col("penalty_team") == team))
        pens = pens.filter(pl.col("posteam") == team) if side == "offense" else pens.filter(pl.col("defteam") == team)
        return {"penalties": pens.height, "yards": int(pens["penalty_yards"].sum()),
                "types": pens["penalty_type"].to_list()}
    if ev in ("epa", "efficiency", "success", "success rate"):
        return {"plays": rp.height, "epa_per_play": round(rp["epa"].mean(), 3),
                "success_rate": round(rp["success"].mean(), 3)}
    if ev in ("box", "stacked box", "men in box"):
        if ftn.is_empty():
            return {"status": "FTN not published for this game yet"}
        return {"avg_box": round(ftn["n_defense_box"].mean(), 2),
                "eight_plus_rate": round((ftn["n_defense_box"] >= 8).mean(), 3)}
    return None


def _decision_evidence(game: pl.DataFrame, ev: str, team: str) -> dict | None:
    if ev in ("4th downs", "4th down", "fourth down", "fourth downs", "go for it"):
        fd = game.filter((pl.col("posteam") == team) & (pl.col("down") == 4)
                         & pl.col("play_type").is_in(["pass", "run", "punt", "field_goal"]))
        return {"fourth_downs": fd.height,
                "went_for_it": int(fd["play_type"].is_in(["pass", "run"]).sum()),
                "see": "packet section 'Decisions' for league go-rates in each spot"}
    if ev in ("pass rate", "run pass", "play calling", "playcalling", "proe", "early down"):
        rp = _rp(game).filter(pl.col("posteam") == team)
        return {"pass_rate": round(rp["pass"].mean(), 3), "proe": round(rp["pass_oe"].mean() / 100, 3),
                "early_down_pass": round(rp.filter(pl.col("down") <= 2)["pass"].mean(), 3)}
    if ev in ("timeouts", "clock"):
        to = game.filter((pl.col("timeout") == 1) & (pl.col("timeout_team") == team))
        return {"timeouts": to.select("qtr", "time").rows()}
    return None


def check(claims: list[Claim], game: pl.DataFrame, team: str = config.TEAM) -> list[Claim]:
    for c in claims:
        who = c.who.strip().lower()
        for ev in c.evidence:
            if ev in PAID_EVIDENCE:
                c.needs_paid.append(ev)
                continue
            if c.kind == "decisions" or who in DECISION_WHO:
                val = _decision_evidence(game, ev, team)
            elif who in UNITS:
                val = _unit_evidence(game, UNITS[who], ev, team)
            else:
                val = _player_evidence(game, c.who, ev, team)
            if val is None or ev in PARTIAL_EVIDENCE:
                c.needs_paid.append(ev)
            if val is not None:
                c.evidence_values[ev] = val
    return claims


def sumerbrain_questions(claims: list[Claim], game_label: str) -> list[dict]:
    """Guardrailed questions for SūmerBrain, only for evidence free data couldn't answer.

    Each question gets an explicit definition, asks for the counts behind any percentage,
    and is meant to be asked twice (the agent does this). Different answers = unreliable.
    """
    qs = []
    for c in claims:
        for ev in c.needs_paid:
            qs.append({
                "claim_line": c.line_no,
                "question": (
                    f"For {game_label} only: {ev} for {c.who}. Define it explicitly: say exactly "
                    f"what counts in the numerator and denominator. Give the raw counts (e.g. "
                    f"'7 of 31 dropbacks'), not only a percentage. Only use this game's snaps."
                ),
                "ask_twice": True,
            })
    return qs


def notes_path(week: int, source: str = "me"):
    tag = config.week_tag(week)
    return config.NOTES_DIR / (f"{tag}.md" if source == "me" else f"{tag}_{source}.md")


def write_verdicts(claims: list[Claim], week: int, source: str = "me") -> tuple[str, str]:
    """Write the verdicts CSV (keeps any verdicts you already filled in) + SūmerBrain questions."""
    config.NOTES_DIR.mkdir(parents=True, exist_ok=True)
    tag = config.week_tag(week) + ("" if source == "me" else f"_{source}")
    path = config.NOTES_DIR / f"{tag}_verdicts.csv"
    existing = {}
    if path.exists():
        with path.open() as f:
            for r in csv.DictReader(f):
                existing[(r["who"], r["what"])] = r
    fields = ["line", "type", "who", "what", "evidence_asked", "free_evidence", "needs_paid_or_film",
              "paid_evidence", "verdict", "comment"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for c in claims:
            old = existing.get((c.who, c.what), {})
            w.writerow({
                "line": c.line_no, "type": c.kind, "who": c.who, "what": c.what,
                "evidence_asked": "; ".join(c.evidence),
                "free_evidence": json.dumps(c.evidence_values, default=str),
                "needs_paid_or_film": "; ".join(c.needs_paid),
                "paid_evidence": old.get("paid_evidence", ""),
                "verdict": old.get("verdict", ""),
                "comment": old.get("comment", ""),
            })
    qpath = config.NOTES_DIR / f"{tag}_sumerbrain_questions.json"
    qpath.write_text(json.dumps(sumerbrain_questions(claims, f"week {week} ({config.SEASON})"), indent=2))
    return str(path), str(qpath)


def eye_score() -> pl.DataFrame:
    """Share of checkable notes the data supported, per source and claim type, all graded weeks.

    'mixed' counts as half. "can't check" and blanks are left out of the denominator.
    """
    rows = []
    for p in sorted(config.NOTES_DIR.glob("*_verdicts.csv")):
        # 2026_wk03_verdicts.csv -> me ; 2026_wk03_skinner_verdicts.csv -> skinner
        middle = p.name[len("2026_wk03"):-len("_verdicts.csv")].strip("_")
        with p.open() as f:
            for r in csv.DictReader(f):
                v = (r.get("verdict") or "").strip().lower()
                if v in ("supported", "contradicted", "mixed"):
                    rows.append({"source": middle or "me", "week": p.name[:9], "type": r["type"], "verdict": v})
    if not rows:
        return pl.DataFrame()
    df = pl.DataFrame(rows).with_columns(
        pl.col("verdict").replace_strict({"supported": 1.0, "mixed": 0.5, "contradicted": 0.0}).alias("score"))
    aggs = [pl.len().alias("checked"),
            (pl.col("verdict") == "supported").sum().alias("supported"),
            (pl.col("verdict") == "contradicted").sum().alias("contradicted"),
            pl.col("score").mean().alias("eye_score")]
    by_type = df.group_by("source", "type").agg(aggs)
    total = df.group_by("source").agg(aggs).with_columns(pl.lit("ALL").alias("type")).select(by_type.columns)
    return pl.concat([by_type, total]).sort("source", pl.col("type") == "ALL", "type")
