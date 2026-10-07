"""The two copy-paste prompts for Claude in Chrome (one per paid site), and ingesting the replies.

    python -m bbt prompts 4   ->  private/prompts/2026_wk04_1_sumer.txt
                                  private/prompts/2026_wk04_2_nflpro.txt

Each prompt is self-contained: rules, route, this game's extra asks, SūmerBrain questions and
the reply format are all inlined, so nothing else needs to be pasted alongside it.

Game-specific extras come from private/notes/<tag>_asks.md (sections `## sumer` and
`## nflpro`), written while reading that week's notes. SūmerBrain questions come from
private/notes/<tag>_sumerbrain_questions.json.

    python -m bbt ingest 4 reply.txt   -> merges a pasted reply into private/paid/<tag>.json + _raw.txt
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from bbt import config, data, film, notes

RULES = """RULES (follow exactly; my paid accounts depend on it)
- Read only. Never click export, download, share, settings, account, billing or upgrade. Never log in or out or type credentials.
- This game only. Don't browse other games, weeks or teams beyond what's listed.
- Human pace, one tab (the one I'm looking at). At least 10 seconds between page loads, 5 seconds between clicks. Hard cap for this run: {cap}. Stop at the cap and send what you have.
- Only the normal page: no dev tools, console, page source, API calls or URL editing. Click visible links and controls only.
- Copy numbers exactly as shown (same rounding; percentages stay 0-100). Don't calculate or fix anything. If a number isn't on the page, use null and add its path to missing_fields.
- Read the page text first. If a number is visible on screen but missing from the text, read it from a screenshot and add its path to screenshot_fields.
- Describe pages by breadcrumb, never by URL.
- CAPTCHA, "unusual activity", rate-limit message or forced logout: stop immediately, don't retry, tell me where you were. Generic "Something went wrong": wait 30 seconds, try once more, then skip it and note it in agent_notes.
- Dropdowns fade in slowly: wait until a list is fully open before picking."""

SUMER_ROUTE = """ROUTE (about 4 page loads, 10-15 minutes)
1. SūmerLive -> the game -> View Stats.
   a. Giants tab -> "nyg": Team Tendencies (offensive personnel, run concepts, defense block). Pass Game and Run Game blocks (the value comes BEFORE its label). Passing Performance tabs By Personnel, By Coverage, By Route, Pressure, Blitz. Rushing Performance tabs By Concept, By Gap, By Box, By Personnel. Each split row: label, share %, EPA, comp %, comp, att, yds, sacks (passing) or att, yds, YACo (rushing).
   b. The play-by-play feed on the game page: for every Giants designed run, one line with quarter, clock, down & distance, personnel chip, run concept, gap (A-D + side), box (light/heavy) and any player tags. Read it from the page text; don't open each card.
   c. Opponent tab -> "opp": the same panels (this is what the Giants defense faced). Skip its play feed.
2. Teams -> Week: Regular Season -> Week {week}. Side = Offense: copy the NYG row (every column, label: value) -> "teams_offense". Side = Defense: NYG row -> "teams_defense".
3. Players -> Week {week}, Team NYG (both stick across positions). Offensive Line, Cornerback, Safety, Linebacker, Edge Rusher, Defensive Interior: every NYG row (label: value, including Player)."""

NFLPRO_ROUTE = """ROUTE (about 7 page loads, 15-20 minutes)
Background tabs don't take clicks: work in the visible tab. The scoreboard strip sits just above the game tabs, so make sure clicks land on the tab and not on another game.
1. Games -> Week dropdown -> Week {week} -> the NYG game card.
2. Stats tab. It says "Sorry, no results!" first and fills in 20-30 seconds later (ignore the "available the day after" banner). Read Passing, Rushing, Receiving in Overview, then toggle Advanced (blank for about 10s) and add those columns to the same player rows. Both teams. -> "game_stats".
3. Play By Play tab. If Play Type can be limited to pass + run, do that and note it. Team = NYG: note "Number of plays" as personnel "ALL", then each Personnel option and its count. Repeat for the opponent. -> "personnel".
4. Watch Film -> Film Room, Game = this game: the "N plays matching" count with no filter, then Pressure, then Blitz (one at a time). Counts only, don't play clips. -> "film_room".
5. Next Gen Stats -> Team Defense, Week {week}: NYG row of Pass Defense and Run Defense. Then Team Offense: NYG row of Passing, Rushing, Receiving. -> "ngs_team_defense", "ngs_team_offense".
6. Game -> Insights: copy each card's text verbatim -> "insights"."""

SUMERBRAIN = """SŪMERBRAIN (Sūmer's AI chat; do this after the tables, about 20-30 minutes)
For each question below:
1. Open a NEW SūmerBrain chat and PASTE the question (don't type it: typing drops letters). Paste only the text after the [bracketed label]. Check it reads correctly, then send. Wait for the full answer (it can take 1-5 minutes).
2. If it answers, copy the answer verbatim and move to the next question. Ask each question ONCE.
3. If it says it needs film, isn't available with this access, or can't answer, send ONE follow-up in the same chat: "No film needed. What do your charting stats show on this, at the team or player level, for this game and the Giants' other games this season?" Copy that answer too. Never resend the same question.
4. If it errors, wait 30 seconds and try once more, then move on.
{questions}"""

SUMER_SKELETON = {
    "site": "sumer",
    "sumer": {
        "game_page": {
            "nyg": {"tendencies": {"offensive_personnel": [{"label": "11", "pct": None}],
                                   "run_concepts": [{"label": "Inside Zone", "pct": None}],
                                   "defensive_personnel": [{"label": "Nickel", "pct": None}],
                                   "man_rate": None, "zone_rate": None, "blitz_rate": None, "pressure_rate": None,
                                   "tfl_rate": None, "missed_tackle_rate": None},
                    "pass_game": {"pass_yards": None, "epa_per_play": None, "avg_time_to_pressure": None,
                                  "avg_time_to_throw": None, "adot": None},
                    "passing": {"by_personnel": [], "by_coverage": [{"label": "Cover 3", "share_pct": None, "epa": None,
                                                                     "comp_pct": None, "comp": None, "att": None,
                                                                     "yds": None, "sacks": None}],
                                "by_route": [], "pressure": [], "blitz": []},
                    "run_game": {"attempts": None, "rush_yards": None, "yards_after_contact": None, "epa_per_play": None},
                    "rushing": {"by_concept": [{"label": "Inside Zone", "share_pct": None, "epa": None, "att": None,
                                                "yds": None, "yaco": None}],
                                "by_gap": [], "by_box": [], "by_personnel": []},
                    "run_cards": ["Q1 12:34 1&10 | 21 personnel | Inside Zone | B gap right | light box | tags: ..."]},
            "opp": "same shape as nyg, without run_cards",
        },
        "teams_offense": {"<column label>": "<value as shown>"},
        "teams_defense": {"<column label>": "<value as shown>"},
        "players": {"offensive_line": [{"Player": "...", "<column label>": "<value>"}],
                    "cornerback": [], "safety": [], "linebacker": [], "edge_rusher": [], "defensive_interior": []},
    },
}

NFLPRO_SKELETON = {
    "site": "nfl_pro",
    "nfl_pro": {
        "game_stats": {"passing": [{"Player": "...", "Team": "...", "<column label>": "<value>"}],
                       "rushing": [], "receiving": []},
        "personnel": [{"team": "NYG", "personnel": "ALL", "plays": None, "play_type_filter": "pass+run or none"}],
        "film_room": {"all_plays": None, "pressure_plays": None, "blitz_plays": None},
        "ngs_team_defense": {"pass_defense": {"<column label>": "<value>"}, "run_defense": {}},
        "ngs_team_offense": {"passing": {}, "rushing": {}, "receiving": {}},
        "insights": ["verbatim card text"],
        "film_links": [{"play": "Q1 02:57", "url": "address bar after clicking the play"}],
    },
}

COMMON_TAIL = {
    "sumerbrain": [{"claim": "the [bracketed label] before the question", "question": "...", "answer_1": "its answer, verbatim", "answer_2": "the follow-up answer if you had to send the follow-up, else empty", "refused": False}],
    "extra_asks": [{"ask": "...", "answer": "verbatim from the page"}],
    "screenshot_fields": [], "missing_fields": [], "agent_notes": "",
    "usage": {"page_loads": 0, "clicks": 0, "minutes": 0},
}

REPLY = """REPLY FORMAT (important: the JSON block is required, not optional)
Send exactly two code blocks and nothing else of substance. If you're short on space, the JSON block comes first and is the one that must be complete:
1. ```json with this shape (keep these keys; fill in what the pages show; tables as "column label": "value as shown"):
{skeleton}
2. ```text with the raw page text of every page and panel you read, each starting with a line "=== <breadcrumb> ===".
I paste your reply straight into another tool, so keep both blocks complete."""


def _section(path, name: str) -> str:
    if not path.exists():
        return ""
    m = re.search(rf"^##\s*{name}\s*$(.*?)(?=^##\s|\Z)", path.read_text(), re.M | re.S | re.I)
    return m.group(1).strip() if m else ""


def _matchup(week: int) -> str:
    gid = data.game_id_for(week)
    _, _, away, home = gid.split("_")
    return f"{away} at {home}"


def _questions_block(questions) -> str:
    return SUMERBRAIN.format(questions="\n".join(
        f"{i}. [{q.get('claim', 'extra')}] {q['question']}" for i, q in enumerate(questions, 1)))


SUMERBRAIN_ONLY_SKELETON = {
    "site": "sumerbrain",
    "sumerbrain": [{"claim": "the [bracketed label] before the question", "question": "...",
                    "answer_1": "its answer, verbatim", "answer_2": "follow-up answer if sent, else empty",
                    "refused": False}],
    "agent_notes": "", "usage": {"chats": 0, "minutes": 0},
}


def build_sumerbrain(week: int) -> str | None:
    """Standalone SūmerBrain prompt for claims still open after the table runs."""
    tag = config.week_tag(week)
    questions = notes.open_claim_questions(week, f"the {config.SEASON} Week {week} game {_matchup(week)}")
    if not questions:
        return None
    text = "\n\n".join([
        f"You're helping me check my notes on one New York Giants game: {data.game_id_for(week)} "
        f"(Week {week}, {config.SEASON}), NYG vs {data.opponent_for(week)}. I'm logged into SūmerPass already. "
        "This run is SūmerBrain (Sūmer's AI chat) only. Don't browse any other pages.",
        "RULES: read only, one tab, never change settings or account pages, never type credentials. "
        "CAPTCHA, 'unusual activity', rate-limit message or forced logout: stop and tell me.",
        _questions_block(questions),
        REPLY.format(skeleton=json.dumps(SUMERBRAIN_ONLY_SKELETON, ensure_ascii=False)).replace(
            "2. ```text with the raw page text of every page and panel you read, each starting with a line \"=== <breadcrumb> ===\".",
            "2. ```text with every answer verbatim, each starting with \"=== <question number> ===\"."),
    ]) + "\n"
    path = config.PRIVATE_DIR / "prompts" / f"{tag}_3_sumerbrain.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return str(path)


FILM_RULES = """RULES (follow exactly; my paid account depends on it)
- Read only. Never click export, download, share, save, settings, account, billing or upgrade. Never log in or out or type credentials.
- This game only. Human pace, one tab (the one I'm looking at): at least 10 seconds between page loads, 5 seconds between clicks. Hard cap: 4 page loads, 50 clicks. Stop at the cap and send what you have.
- Click visible links and controls only: no dev tools, console, page source or URL editing.
- CAPTCHA, "unusual activity", rate-limit message or forced logout: stop immediately, don't retry, tell me where you were.
- Dropdowns fade in slowly: wait until a list is fully open before picking."""


def build_film(week: int) -> str | None:
    """Standalone NFL Pro prompt that only collects Film Room links for this week's clip list."""
    block = film.prompt_block(week)
    if not block:
        return None
    skeleton = {"site": "nfl_pro_film", "film_links": [{"play": "Q1 02:57", "url": "..."}],
                "agent_notes": "", "usage": {"page_loads": 0, "clicks": 0, "minutes": 0}}
    text = "\n\n".join([
        f"You're helping me collect NFL Pro Film Room links for one New York Giants game: {data.game_id_for(week)} "
        f"(Week {week}, {config.SEASON}), NYG vs {data.opponent_for(week)}. I'm logged into pro.nfl.com already.",
        FILM_RULES,
        "ROUTE: Watch Film → Film Room → set Season 2026, Week " + str(week) + ", Game = this game.",
        block,
        "REPLY FORMAT: one ```json block with this shape, nothing else of substance:\n" + json.dumps(skeleton),
    ]) + "\n"
    path = config.PRIVATE_DIR / "prompts" / f"{config.week_tag(week)}_4_film_links.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return str(path)


def build(week: int) -> tuple[str, str]:
    tag = config.week_tag(week)
    game_id = data.game_id_for(week)
    opp = data.opponent_for(week)
    asks_path = config.NOTES_DIR / f"{tag}_asks.md"
    questions = notes.open_claim_questions(week, f"the {config.SEASON} Week {week} game {_matchup(week)}")

    header = (f"You're helping me pull paid charting data for one New York Giants game: {game_id} "
              f"(Week {week}, {config.SEASON}), NYG vs {opp}. I'm logged in already.\n")
    out = []
    for site, n, route, cap, skel in (
        ("SūmerPass (sumersports.com)", "1_sumer", SUMER_ROUTE, "8 page loads, 45 clicks", SUMER_SKELETON),
        ("NFL Pro (pro.nfl.com)", "2_nflpro", NFLPRO_ROUTE, "10 page loads, 45 clicks", NFLPRO_SKELETON),
    ):
        parts = [header + f"This run is {site} only.\n", RULES.format(cap=cap), route.format(week=week)]
        extras = _section(asks_path, "sumer" if n == "1_sumer" else "nflpro")
        if n == "2_nflpro":
            fb = film.prompt_block(week)
            if fb:
                route = route + "\n\n" + fb.replace("{", "{{").replace("}", "}}")
        if extras:
            parts.append("EXTRA ASKS FOR THIS GAME (still within the caps; answers go in \"extra_asks\")\n" + extras)
        if n == "1_sumer" and questions:
            parts.append(_questions_block(questions))
        skeleton = {**skel, **COMMON_TAIL}
        if n != "1_sumer":
            skeleton = {k: v for k, v in skeleton.items() if k != "sumerbrain"}
        parts.append(REPLY.format(skeleton=json.dumps(skeleton, ensure_ascii=False)))
        text = "\n\n".join(parts) + "\n"
        path = config.PRIVATE_DIR / "prompts" / f"{tag}_{n}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        out.append(str(path))
    return out[0], out[1]


def ingest(week: int, reply_text: str) -> str:
    """Merge one pasted extension reply into the week's extract and raw text."""
    blocks = re.findall(r"```(\w*)\s*\n(.*?)```", reply_text, re.S)
    js = next((b for lang, b in blocks if lang.lower() == "json" or b.lstrip().startswith("{")), None)
    raw = next((b for lang, b in blocks if b is not js and lang.lower() != "json"), "")
    if js is None:
        raise SystemExit("No ```json block found in the reply")
    part = json.loads(js)
    site = part.get("site") or ("sumer" if "sumer" in part else "nfl_pro")

    tag = config.week_tag(week)
    config.PAID_DIR.mkdir(parents=True, exist_ok=True)
    jpath, rpath = config.PAID_DIR / f"{tag}.json", config.PAID_DIR / f"{tag}_raw.txt"
    ext = json.loads(jpath.read_text()) if jpath.exists() else {
        "schema_version": "v1", "season": config.SEASON, "week": week, "game_id": data.game_id_for(week),
        "team": config.TEAM, "opponent": data.opponent_for(week), "sources": [],
        "sumer": None, "nfl_pro": None, "missing_fields": ["sumer", "nfl_pro"],
        "screenshot_fields": [], "raw_text_file": rpath.name, "sumerbrain": [], "extra_asks": [], "agent_notes": "",
    }
    ext["extracted_at"] = datetime.now().isoformat(timespec="seconds")
    sb = part.get("sumerbrain") or []
    if site == "nfl_pro_film":
        np_ = ext.get("nfl_pro") or {}
        have = {l.get("play"): l for l in np_.get("film_links") or []}
        have.update({l.get("play"): l for l in part.get("film_links") or []})
        np_["film_links"] = list(have.values())
        ext["nfl_pro"] = np_
        jpath.write_text(json.dumps(ext, indent=1, ensure_ascii=False))
        return f"added {len(part.get('film_links') or [])} Film Room links"
    if site != "sumerbrain":
        ext[site] = part.get(site)
        ext["missing_fields"] = [m for m in ext.get("missing_fields", []) if m != site] + part.get("missing_fields", [])
        ext["screenshot_fields"] = ext.get("screenshot_fields", []) + part.get("screenshot_fields", [])
        ext["sources"] = [s for s in ext.get("sources", []) if s.get("source") != site] + [{"source": site, "page": "see raw text"}]
        for a in part.get("extra_asks") or []:
            ext.setdefault("extra_asks", []).append({**a, "site": site})
    # SūmerBrain answers: replace any earlier answer to the same claim, then file them on the claims
    asked = {qa.get("claim") for qa in sb}
    ext["sumerbrain"] = [q for q in ext.get("sumerbrain") or [] if q.get("claim") not in asked] + sb
    answers = {qa["claim"]: {k: qa.get(k) for k in ("question", "answer_1", "answer_2", "refused", "counts_given", "consistent")}
               for qa in sb if qa.get("claim") and qa["claim"] != "extra"}
    unmatched = []
    if answers and (config.NOTES_DIR / f"{tag}_verdicts.csv").exists():
        unmatched = notes.record_sumerbrain(week, answers)
    if part.get("agent_notes"):
        ext["agent_notes"] = (ext.get("agent_notes", "") + f"\n[{site}] " + part["agent_notes"]).strip()
    ext.setdefault("usage", {})[site] = part.get("usage")
    jpath.write_text(json.dumps(ext, indent=1, ensure_ascii=False))

    old = rpath.read_text() if rpath.exists() else ""
    old = re.sub(rf"##### {site} #####.*?(?=##### |\Z)", "", old, flags=re.S)
    rpath.write_text(old + f"##### {site} #####\n{raw}\n")
    msg = f"merged {site} into {jpath.name}"
    if answers:
        msg += f"; {len(answers)} SūmerBrain answers filed on claims"
    if unmatched:
        msg += f"; couldn't match: {unmatched}"
    return msg
