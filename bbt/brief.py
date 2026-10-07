"""The weekly notes doc: one file to write the post from.

    python -m bbt brief 4  ->  private/briefs/2026_wk04.md

It pulls together:
  - your notes, each turned into a nugget: verdict, what the data says, evidence, film to check
  - things you didn't note that the data flags (gameplan shifts, swing plays, penalties)
  - paid-data highlights, the extension's extra-ask answers and SūmerBrain answers
  - where Sūmer and NFL Pro disagree
  - last week's watch-for grade and next opponent's standout tendencies
  - the film list and charts
The full packet (every table) is built alongside it as the appendix.
"""

from __future__ import annotations

import csv
import json

import polars as pl

from bbt import config, data, erased, gameplan, notes, opponent, packet, paid, penalties, swing, viz

AUTO_CHARTS = ["wp", "gameplan", "drives", "penalties", "erased_league"]
ICON = {"sumerbrain": "🧠", "supported": "✅", "contradicted": "❌", "mixed": "🟡", "can't check": "❔", "": "⬜"}


def _pct(v):
    return "–" if v is None else f"{v * 100:.0f}%"


def _chart_md(spec: dict, path) -> str:
    return f"\n![{spec.get('title', path.stem)}](../charts/{path.name})\n"


def _notes_section(tag: str, story: list | None = None, placed: set | None = None) -> list[str]:
    """Each note with its verdict; a story chart whose spec names the claim goes right under it."""
    story, placed = story or [], placed if placed is not None else set()
    out = ["## Your notes, checked\n"]
    found = False
    for p in sorted(config.NOTES_DIR.glob(f"{tag}*_verdicts.csv")):
        source = p.name[len(tag):-len("_verdicts.csv")].strip("_") or "me"
        rows = list(csv.DictReader(p.open()))
        if not rows:
            continue
        found = True
        if source != "me":
            out.append(f"\n### Notes from: {source}\n")
        week = int(tag.split("wk")[1][:2])
        asked = {q.get("claim", "").lower() for q in notes.open_claim_questions(week, "", source)}
        counts = {}
        for r in rows:
            counts[r.get("verdict", "")] = counts.get(r.get("verdict", ""), 0) + 1
        out.append(" · ".join(f"{ICON.get(k, '⬜')} {k or 'not graded'} {v}" for k, v in counts.items()) + "\n")
        for r in rows:
            v = (r.get("verdict") or "").strip()
            out.append(f"\n**{ICON.get(v, '⬜')} {r['who']}: {r['what']}**  \n")
            out.append(f"*{v or 'not graded yet'}* · {r['type']}  \n")
            if r.get("comment"):
                out.append(f"{r['comment']}  \n")
            if r.get("paid_evidence"):
                out.append(f"Paid data: {r['paid_evidence']}  \n")
            if r.get("sumerbrain"):
                a = json.loads(r["sumerbrain"])
                if a.get("refused") and not a.get("answer_2"):
                    out.append("> 🧠 SūmerBrain couldn't answer this one.  \n")
                else:
                    flag = " **Two asks gave different numbers: treat as unreliable.**" if a.get("consistent") is False else ""
                    out.append(f"> 🧠 **SūmerBrain** (Sūmer's charting, not table-verified unless noted above):{flag} "
                               f"{a.get('answer_2') if a.get('refused') else a.get('answer_1', '')}  \n")
            elif f"{r['who']}: {r['what']}".lower() in asked:
                out.append(f"_Open: sent to SūmerBrain (`bbt prompts --sumerbrain-only`)._  \n")
            claim = f"{r['who']}: {r['what']}".lower()
            for spec, png in story:
                key = (spec.get("claim") or "").lower()
                if key and claim.startswith(key) and png.name not in placed:
                    placed.add(png.name)
                    out.append(_chart_md(spec, png))
    if not found:
        out.append("_No notes for this week yet. Send them over in the usual `who | what | evidence` style "
                   "(or just as bullet points) and they get checked._\n")
    return out


def _auto_section(season, game, game_id, week, team, baseline) -> list[str]:
    out = ["\n## What the data flags (beyond your notes)\n"]
    cmp = gameplan.compare(season, game_id, team, "offense")
    ch = gameplan.biggest_changes(cmp, team)
    for r in ch.iter_rows(named=True):
        out.append(f"- **Gameplan:** {r['label']} {_pct(r['this_game'])} vs {_pct(r[f'{team}_prior'])} usual "
                   f"(league {_pct(r['league'])}).\n")
    dcmp = gameplan.compare(season, game_id, team, "defense")
    dch = gameplan.biggest_changes(dcmp, team, n=2)
    for r in dch.iter_rows(named=True):
        out.append(f"- **Defense:** {r['label']} {_pct(r['this_game'])} vs {_pct(r[f'{team}_prior'])} usual "
                   f"(league {_pct(r['league'])}).\n")
    sw = swing.swing_plays(game, team, n=3)
    for r in sw.iter_rows(named=True):
        out.append(f"- **Swing play** ({r['wpa_pts']:+.0f} WP pts, Q{int(r['qtr'])} {r['time']}): {r['desc'][:160]}\n")
    led = penalties.ledger(season)
    est = erased.estimate(led, baseline)
    totals = erased.team_totals(est)
    g = est.filter((pl.col("game_id") == game_id) & (pl.col("penalty_team") == team)
                   & pl.col("kind").is_in(["pre_snap", "wiped"]))
    out.append(f"- **Penalties:** {g.height} pre-snap/wiped-play flags on {team} this game, costing "
               f"{g['total_cost_to_penalized'].sum():.1f} EP. Season: {erased.headline(totals, team)}\n")
    return out


def _paid_section(week: int, game, game_id: str) -> list[str]:
    ext = paid.load(week)
    out = ["\n## Paid data (Sūmer + NFL Pro)\n"]
    if ext is None:
        return out + ["_Not in yet: paste the two Claude in Chrome replies into the session._\n"]
    rep = paid.run_check(week, game, game_id)
    out.append(f"Check: **{'PASS' if rep.ok else 'FAIL'}**, {len(rep.warnings)} warnings "
               f"(details in the packet).\n")
    have = [s for s in ("sumer", "nfl_pro") if ext.get(s)]
    out.append(f"Sources in: {', '.join(have) or 'none'}.\n")
    xs = paid.cross_source(ext)
    if xs:
        out.append("\n**Where Sūmer and NFL Pro disagree** (they chart independently; say so in the post if it matters)\n\n")
        out.append(packet.md_table(pl.DataFrame(xs)))
    for a in ext.get("extra_asks") or []:
        out.append(f"\n- **{a.get('ask', '')}** ({a.get('site', '')}): {a.get('answer', '')}\n")
    for q in ext.get("sumerbrain") or []:
        same = q.get("consistent")
        flag = "consistent" if same else "**answers differ, treat as unreliable**"
        out.append(f"\n- SūmerBrain: _{q.get('question', '')[:120]}…_ → {q.get('answer_1', '')} ({flag})\n")
    cards = ((((ext.get("sumer") or {}).get("game_page") or {}).get("nyg") or {}).get("run_cards")) or []
    if cards:
        out.append("\n<details><summary>Giants run cards (Sūmer)</summary>\n\n" + "".join(f"- {c}\n" for c in cards)
                   + "\n</details>\n")
    return out


def build(week: int, team: str = config.TEAM) -> str:
    tag = config.week_tag(week)
    season = data.season_plays()
    baseline = data.baseline_plays()
    game_id = data.game_id_for(week, team)
    game = season.filter(pl.col("game_id") == game_id)
    if game.is_empty():
        raise SystemExit(f"No play-by-play for {game_id} yet. nflverse updates nightly.")
    opp = data.opponent_for(week, team)
    home, away = game["home_team"][0], game["away_team"][0]
    hs, as_ = int(game["total_home_score"].max()), int(game["total_away_score"].max())
    nyg_pts, opp_pts = (hs, as_) if home == team else (as_, hs)
    result = "W" if nyg_pts > opp_pts else ("L" if nyg_pts < opp_pts else "T")
    has_ftn = bool(game["has_ftn"].fill_null(False).any())

    packet_path = packet.build(week, team)  # appendix + the automatic charts
    story = viz.render_week(week)  # charts from <tag>_charts.json
    placed: set[str] = set()

    out = [f"# Week {week} notes doc: {team} {nyg_pts}, {opp} {opp_pts} ({result})\n",
           "_Private. Everything you need to write the post: your notes checked, what the data adds, "
           "paid-data highlights, film to watch, next week._\n",
           "\n> Writing rules: keep **what happened**, **what was probably supposed to happen** and "
           "**your opinion** separate. Put the number next to every claim. Say what can't be known "
           "from outside (line calls, checks). One idea per post. *One must imagine the Giants fan happy.*\n",
           f"\nData status: play-by-play ✅ · FTN charting {'✅' if has_ftn else '⏳ not published yet'} · "
           f"paid {'✅' if paid.load(week) else '⏳ not in yet'}\n\n"]
    out += _notes_section(tag, story, placed)
    out += _auto_section(season, game, game_id, week, team, baseline)
    out += _paid_section(week, game, game_id)

    sc = [r for r in opponent.read_scorecard() if r["week"] == str(week) and r["season"] == str(config.SEASON)]
    out.append("\n## Scorecard\n")
    if sc:
        if not sc[0].get("grade"):
            opponent.grade(week, game)
            sc = [r for r in opponent.read_scorecard() if r["week"] == str(week)]
        r = sc[0]
        out.append(f"Last week's watch-for: *{r['prediction']}* → **{r.get('grade') or 'ungraded'}** "
                   f"(actual {r.get('actual') or '–'}, line {r['direction']} {r['line']}).\n")
    else:
        out.append(f"_No watch-for was logged for week {week}._\n")

    try:
        nxt = data.opponent_for(week + 1, team)
    except SystemExit:
        nxt = None
    if nxt:
        tend = opponent.tendencies(season, nxt, week).head(3)
        out.append(f"\n## Next: {nxt} (week {week + 1}). Watch-for candidates\n")
        for r in tend.iter_rows(named=True):
            v = f"{r['value']:+.2f}" if r["metric"].endswith("epa") else _pct(r["value"])
            lg = f"{r['league']:+.2f}" if r["metric"].endswith("epa") else _pct(r["league"])
            out.append(f"- {r['label']}: **{v}** vs league {lg} (rank {r['rank']} of {r['of']}) · metric `{r['metric']}`\n")
        out.append("\nPick one and tell me the line; it goes in the public scorecard.\n")

    from bbt import film
    out.append(film.render(week))

    out.append("\n## Charts\n\n_PNG cards in `private/charts/`, sized for a post (1600 px wide). "
               f"Story charts come from `private/notes/{tag}_charts.json`; the rest build every week._\n")
    rest = [(s, p) for s, p in story if p.name not in placed]
    if rest:
        out.append("\n### More story charts\n" + "".join(_chart_md(s, p) for s, p in rest))
    auto = [p for p in (config.CHARTS_DIR / f"{tag}_{n}.png" for n in AUTO_CHARTS) if p.exists()]
    out.append("\n### Every week (free data)\n" + "".join(f"\n![{p.stem}](../charts/{p.name})\n" for p in auto))
    out.append(f"\n---\nFull tables: `{packet_path}`. Credit in the post: {config.FTN_CREDIT}; "
               "play-by-play from nflverse.\n")

    path = config.PRIVATE_DIR / "briefs" / f"{tag}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(out))
    return str(path)
