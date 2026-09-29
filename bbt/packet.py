"""Ticket 10: the weekly game packet: one Markdown file to write the post from."""

from __future__ import annotations

import json
from datetime import datetime

import polars as pl

from bbt import (charts, config, data, decisions, drives, erased, gameplan, notes, opponent, paid,
                 penalties, players, swing)


def md_table(df: pl.DataFrame, pct: tuple[str, ...] = (), dec: dict | None = None,
             max_rows: int | None = None) -> str:
    """polars -> Markdown table. `pct` columns show as %, `dec` sets decimals per column."""
    if df.is_empty():
        return "_none_\n"
    dec = dec or {}
    if max_rows:
        df = df.head(max_rows)

    def fmt(col, v):
        if v is None:
            return "–"
        if isinstance(v, bool):
            return "yes" if v else ""
        if isinstance(v, float):
            if col in pct:
                return f"{v * 100:.1f}%"
            if col in dec:
                return f"{v:.{dec[col]}f}"
            return f"{v:.0f}" if v.is_integer() else f"{v:.2f}"
        return str(v).replace("|", "/").replace("\n", " ")

    head = "| " + " | ".join(df.columns) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    body = ["| " + " | ".join(fmt(c, v) for c, v in zip(df.columns, row)) + " |" for row in df.iter_rows()]
    return "\n".join([head, sep, *body]) + "\n"


def _gameplan_table(cmp: pl.DataFrame, team: str) -> str:
    counts = {"plays"}
    decimals = {"epa", "epa_pass", "epa_run"}
    rows = []
    for r in cmp.iter_rows(named=True):
        def f(v, key=r["metric"]):
            if v is None:
                return "–"
            if key in counts:
                return f"{v:.0f}"
            if key in decimals:
                return f"{v:+.2f}"
            if key in ("adot", "box", "rushers"):
                return f"{v:.1f}"
            return f"{v * 100:.1f}%"
        rows.append({"": r["label"], "this game": f(r["this_game"]), f"{team} before": f(r[f"{team}_prior"]),
                     "league": f(r["league"])})
    return md_table(pl.DataFrame(rows))


SPLIT_COLS = ["label", "share_pct", "epa", "comp_pct", "comp", "att", "yds", "sacks", "yaco"]


def _paid_section(ext: dict, team: str) -> str:
    """Sūmer game page, Teams rows and Players tables as readable Markdown."""
    out = []
    s = ext.get("sumer") or {}
    gp = s.get("game_page") or {}
    opp = ext.get("opponent", "opp")
    for side, title in (("nyg", f"{team} offense (Giants tab)"),
                        ("opp", f"{opp} offense = what {team}'s defense faced ({opp} tab)")):
        tab = gp.get(side)
        if not tab:
            continue
        out.append(f"\n### {title}\n")
        tend = tab.get("tendencies") or {}
        for key in ("offensive_personnel", "run_concepts", "defensive_personnel"):
            if tend.get(key):
                out.append(f"\n**{key.replace('_', ' ').title()}**: " + ", ".join(
                    f"{d['label']} {d['pct']}" for d in tend[key] if d.get("pct") is not None) + "\n")
        scalars = {k: v for k, v in {**tend, **(tab.get("pass_game") or {}), **(tab.get("run_game") or {})}.items()
                   if not isinstance(v, list)}
        if scalars:
            out.append("\n" + md_table(pl.DataFrame([{k: (None if v is None else str(v)) for k, v in scalars.items()}])))
        for group in ("passing", "rushing"):
            for key, rows in (tab.get(group) or {}).items():
                if rows:
                    df = pl.DataFrame(rows, infer_schema_length=None)
                    cols = [c for c in SPLIT_COLS if c in df.columns and df[c].null_count() < df.height]
                    out.append(f"\n**{group.title()}: {key.replace('_', ' ')}**\n\n" + md_table(df.select(cols)))
    for key, title in (("teams_offense", f"Teams > Offense, {team} row"),
                       ("teams_defense", f"Teams > Defense, {team} row")):
        row = s.get(key)
        if row:
            out.append(f"\n### {title}\n\n" + md_table(pl.DataFrame(
                [{"stat": k, "value": str(v)} for k, v in row.items()])))
    np_ = ext.get("nfl_pro") or {}
    for group, rows in (np_.get("game_stats") or {}).items():
        if rows:
            df = pl.DataFrame([{k: (None if v is None else str(v)) for k, v in r.items()} for r in rows],
                              infer_schema_length=None)
            out.append(f"\n### NFL Pro game stats: {group}\n\n" + md_table(df))
    for key in ("ngs_team_defense", "ngs_team_offense"):
        for view, row in (np_.get(key) or {}).items():
            if row:
                out.append(f"\n### NGS {key.replace('ngs_', '').replace('_', ' ')}: {view.replace('_', ' ')}\n\n"
                           + md_table(pl.DataFrame([{"stat": k, "value": str(v)} for k, v in row.items()])))
    if np_.get("personnel"):
        out.append("\n### NFL Pro personnel (Play By Play counts)\n\n" + md_table(pl.DataFrame(np_["personnel"])))
    if np_.get("film_room"):
        out.append("\n**Film Room counts:** " + ", ".join(f"{k} {v}" for k, v in np_["film_room"].items()) + "\n")
    for card in np_.get("insights") or []:
        out.append(f"\n> {card}\n")
    for pos, rows in (s.get("players") or {}).items():
        if rows:
            df = pl.DataFrame([{k: (None if v is None else str(v)) for k, v in r.items()} for r in rows],
                              infer_schema_length=None)
            out.append(f"\n### Players: {pos.replace('_', ' ')}\n\n" + md_table(df))
    return "".join(out)


def build(week: int, team: str = config.TEAM, make_charts: bool = True) -> str:
    season = data.season_plays()
    baseline = data.baseline_plays()
    game_id = data.game_id_for(week, team)
    game = season.filter(pl.col("game_id") == game_id)
    if game.is_empty():
        raise SystemExit(f"No play-by-play for {game_id} yet. nflverse updates nightly, try tomorrow.")
    opp = data.opponent_for(week, team)
    tag = config.week_tag(week)
    has_ftn = bool(game["has_ftn"].fill_null(False).any())
    home, away = game["home_team"][0], game["away_team"][0]
    hs, as_ = int(game["total_home_score"].max()), int(game["total_away_score"].max())

    out: list[str] = []
    w = out.append
    w(f"# Game packet: {away} {as_} @ {home} {hs} (Week {week}, {config.SEASON})\n")
    w(f"_Built {datetime.now():%Y-%m-%d %H:%M}. PRIVATE: contains paid data, don't commit or share._\n")
    w(f"- FTN charting: {'**in**' if has_ftn else '**not published yet** (motion / play action / blitz / reads blank)'}. "
      f"Credit: {config.FTN_CREDIT}.\n")

    # --- drives
    d = drives.drive_table(game)
    w("\n## 1. Game flow: drives\n")
    w(md_table(d.drop("start_yl100", "fixed_drive"), dec={"off_epa": 2}))
    w("\n" + md_table(drives.drive_summary(d), dec={"epa_per_drive": 2}))

    # --- swing plays
    sw = swing.swing_plays(game, team)
    w(f"\n## 2. Swing plays ({team} win probability)\n")
    w(md_table(sw.drop("play_id").rename({"wp_before": "wp_before_%", "wpa_pts": "swing_pts"})))

    # --- gameplan
    w("\n## 3. Gameplan vs norms\n")
    w(f"Run and pass plays only. '{team} before' = weeks 1–{week - 1}. League = all teams through week {week}.\n\n")
    w("**Offense**\n\n")
    cmp = gameplan.compare(season, game_id, team, "offense")
    w(_gameplan_table(cmp, team))
    changes = gameplan.biggest_changes(cmp, team)
    if changes.height:
        w("\nBiggest changes vs their own norm: " + "; ".join(
            f"{r['label']} {r['this_game'] * 100:.0f}% (usually {r[f'{team}_prior'] * 100:.0f}%)"
            for r in changes.iter_rows(named=True)) + ".\n")
    w("\n**Defense**\n\n")
    w(_gameplan_table(gameplan.compare(season, game_id, team, "defense"), team))
    hidden = penalties.hidden_offense_cost(season, team).filter(pl.col("game_id") == game_id)
    if hidden.height:
        h = hidden.row(0, named=True)
        w(f"\nPenalty snaps are left out of those numbers. Counting them, offense EPA/play goes from "
          f"{h['epa_play_run_pass_only']:+.3f} to {h['epa_play_incl_penalty_snaps']:+.3f} "
          f"({h['penalty_snaps']} penalty snaps, {h['epa_on_penalty_snaps']:+.1f} EPA).\n")

    # --- penalties
    led = penalties.ledger(season)
    est = erased.estimate(led, baseline)
    g_est = est.filter(pl.col("game_id") == game_id)
    totals = erased.team_totals(est)
    w("\n## 4. Penalty ledger\n")
    w(md_table(penalties.team_summary(g_est, team), dec={"wpa_to_penalized": 3}))
    w("\n" + md_table(
        g_est.select("qtr", "time", "penalty_team", "penalty_player_name", "penalty_type", "penalty_yards",
                     "kind", "erased_gain", "erased_td", "erased_ep_to_penalized",
                     "flag_epa_to_penalized", "total_cost_to_penalized", "wpa_to_penalized")
        .rename({"penalty_team": "team", "penalty_player_name": "player", "penalty_yards": "yds",
                 "erased_ep_to_penalized": "ep_erased", "flag_epa_to_penalized": "flag_epa",
                 "total_cost_to_penalized": "total_cost", "wpa_to_penalized": "wpa"}),
        dec={"ep_erased": 2, "flag_epa": 2, "total_cost": 2, "wpa": 3}))
    w("\n_ep_erased: what the wiped play was worth to the team that committed the flag. "
      "flag_epa: the flag's own effect. total_cost = ep_erased − flag_epa. "
      "wpa is only credited for pre-snap and wiped plays. All from the penalized team's view._\n")
    wiped_text = g_est.filter(pl.col("kind") == "wiped").select("time", "penalty_team", "erased_text")
    if wiped_text.height:
        w("\n<details><summary>What each wiped play was</summary>\n\n" + md_table(wiped_text) + "\n</details>\n")

    w("\n## 5. Points erased (season)\n")
    w(f"**{erased.headline(totals, team)}**\n\n")
    w(md_table(totals.select("team", "wiped_plays", "wiped_good_plays", "tds_wiped", "ep_erased",
                             "total_ep_cost", "rank_ep_erased").head(10),
               dec={"ep_erased": 1, "total_ep_cost": 1}))
    by_game = erased.team_totals(est.filter(pl.col("penalty_team") == team), by_game=True)
    w(f"\n{team} by game:\n\n" + md_table(by_game.drop("rank_ep_erased", "rank_total_cost"),
                                           dec={"ep_erased": 2, "ep_erased_gains": 2,
                                                "total_ep_cost": 2, "wpa_to_penalized": 3}))

    # --- decisions
    w("\n## 6. Decisions\n")
    fd = decisions.fourth_downs(game, baseline, team)
    w(md_table(fd.drop("desc", "dist_bucket", "field_bucket").rename(
        {"yardline_100": "yds_to_goal", "score_differential": "score_diff"}),
        pct=("league_go_rate",)))
    w("\n_league_go_rate: how often teams went for it in the same distance + field band, "
      f"seasons {config.BASELINE_SEASONS + [config.SEASON]}, excluding the last 5 min and 17+ pt games._\n")
    tp = decisions.two_point_tries(game, team)
    if tp.height:
        w("\n" + md_table(tp.drop("desc")))

    # --- players
    w("\n## 7. Players\n")
    pt = players.player_table(game_id, team)
    off = pt.filter(pl.col("offense_snaps").fill_null(0) > 0).select(
        "player", "position", "offense_snaps", "offense_pct", "dropbacks", "passer_epa", "targets", "catches",
        "rec_yards", "deep_targets", "target_epa", "carries", "rush_yards", "carry_epa", "penalties")
    de = pt.filter(pl.col("defense_snaps").fill_null(0) > 0).select(
        "player", "position", "defense_snaps", "defense_pct", "penalties", "penalty_yards")
    w("**Offense**\n\n" + md_table(off, pct=("offense_pct",), dec={"passer_epa": 2, "target_epa": 2, "carry_epa": 2}))
    w("\n**Defense** (tackles, pressures and coverage come from the paid data below)\n\n"
      + md_table(de, pct=("defense_pct",)))

    # --- paid
    w("\n## 8. Paid data (Sūmer / NFL Pro)\n")
    rep = paid.run_check(week, game, game_id)
    if rep is None:
        w(f"_No extract yet. Run the browser agent (agent/INSTRUCTIONS.md) and save to "
          f"private/paid/{tag}.json + {tag}_raw.txt, then `python -m bbt check {week}`._\n")
    else:
        w("```\n" + rep.render() + "\n```\n")
        ext = paid.load(week)
        w(_paid_section(ext, team))
        xs = paid.cross_source(ext)
        if xs:
            w("\n### Sūmer vs NFL Pro (same thing, two charters)\n\n" + md_table(pl.DataFrame(xs)))
        w("\n<details><summary>Raw extract</summary>\n\n```json\n" + json.dumps(
            {k: ext.get(k) for k in ("sumer", "nfl_pro", "sumerbrain", "missing_fields")}, indent=1)
          + "\n```\n</details>\n")

    # --- notes
    w("\n## 9. Your notes vs the data\n")
    npath = config.NOTES_DIR / f"{tag}.md"
    if not npath.exists():
        w(f"_No notes file. Write private/notes/{tag}.md in the format `who | what | evidence`._\n")
    else:
        claims = notes.check(notes.parse(npath.read_text()), game, team)
        vpath, qpath = notes.write_verdicts(claims, week)
        for c in claims:
            w(f"\n**{c.who}**: {c.what}  _(type: {c.kind})_\n")
            for ev, val in c.evidence_values.items():
                w(f"- {ev}: `{json.dumps(val, default=str)}`\n")
            if c.needs_paid:
                w(f"- needs Sūmer / film: {', '.join(c.needs_paid)}\n")
        w(f"\nVerdicts go in `{vpath}`. SūmerBrain questions: `{qpath}`.\n")
        eye = notes.eye_score()
        if eye.height:
            w("\n**Eye score (season)**\n\n" + md_table(eye, pct=("eye_score",)))

    # --- next opponent
    nxt_week = week + 1
    try:
        nxt = data.opponent_for(nxt_week, team)
    except Exception:  # noqa: BLE001 - bye week / season over
        nxt = None
    if nxt:
        w(f"\n## 10. Next: {nxt} (week {nxt_week}). What stands out\n")
        tend = opponent.tendencies(season, nxt, week)
        def _v(metric, v):
            return f"{v:+.2f}" if metric.endswith("epa") else f"{v * 100:.1f}%"
        tend = tend.head(8).with_columns(
            pl.struct("metric", "value").map_elements(lambda r: _v(r["metric"], r["value"]), return_dtype=pl.Utf8).alias("value"),
            pl.struct("metric", "league").map_elements(lambda r: _v(r["metric"], r["league"]), return_dtype=pl.Utf8).alias("league"),
        )
        w(md_table(tend.select("metric", "label", "side", "value", "league", "z", "rank", "of", "n"), dec={"z": 1}))
        w("\nBy down & distance:\n\n" + md_table(opponent.by_down_distance(season, nxt, week),
                                                 pct=("pass_rate", "league_pass_rate", "success"),
                                                 dec={"epa_play": 2}))
        w(f"\nLog the watch-for: `python -m bbt watchfor {nxt_week} --metric <metric> --over|--under <line> "
          f"--text \"...\"`\n")

    sc = [r for r in opponent.read_scorecard() if r["week"] == str(week) and r["season"] == str(config.SEASON)]
    if sc:
        w(f"\n**Last week's watch-for:** {sc[0]['prediction']} → {sc[0].get('grade') or 'ungraded'} "
          f"(actual {sc[0].get('actual') or '–'}, line {sc[0]['line']} {sc[0]['direction']})\n")

    # --- charts
    if make_charts:
        cdir = config.CHARTS_DIR
        made = [
            charts.wp_chart(swing.wp_timeline(game, team), sw, team, opp, cdir / f"{tag}_wp.png"),
            charts.drive_chart(d, team, opp, cdir / f"{tag}_drives.png"),
            charts.penalty_game_chart(g_est, team, opp, cdir / f"{tag}_penalties.png"),
            charts.erased_league_chart(totals, team, cdir / f"{tag}_erased_league.png"),
        ]
        w("\n## Charts\n\n" + "".join(f"![{p.stem}](../charts/{p.name})\n" for p in made if p.exists()))

    w("\n## Your notes for the post\n\n- \n")

    config.PACKETS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.PACKETS_DIR / f"{tag}.md"
    path.write_text("".join(out))
    return str(path)
