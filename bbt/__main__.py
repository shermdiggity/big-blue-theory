"""Command line: `python -m bbt <command>`.

  brief N              THE NOTES DOC to write from (private/briefs/), builds the packet too
  prompts N            the two Claude in Chrome prompts (Sūmer + SūmerBrain, NFL Pro) for week N
  prompts N --sumerbrain-only   one prompt: SūmerBrain questions for every claim still open
  prompts N --film-only         one prompt: NFL Pro Film Room links for the week's clip list
  ingest N FILE        merge a pasted Claude in Chrome reply into week N's paid data
  ingest-raw N FILE    build week N's paid data from pasted page text (when there's no JSON block)
  refresh              re-download nflverse data into data/bbt.duckdb
  week N               build the game packet for week N (private/packets/)
  run N                refresh + check paid extract + packet, timed (ticket 16)
  check N              validate the paid-data extract for week N
  notes N [--source X] check notes for week N against the data (yours, or e.g. --source skinner)
  eye                  season eye score per source from graded notes
  opponent N           tendencies for the week-N opponent (using games through N-1)
  watchfor N ...       log the week-N prediction in scorecard.csv
  grade N              grade the week-N prediction
  erased               league table: points erased by penalties
  audit                make sure nothing private is tracked by git (run before every push)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

import polars as pl

from bbt import config


def _show(df: pl.DataFrame) -> None:
    with pl.Config(tbl_rows=60, tbl_cols=20, tbl_width_chars=200, fmt_str_lengths=60, float_precision=3):
        print(df)


def cmd_refresh(_):
    from bbt import data
    data.refresh()


def cmd_week(a):
    from bbt import packet
    print(packet.build(a.week, make_charts=not a.no_charts))


def cmd_prompts(a):
    from bbt import prompts
    if a.sumerbrain_only:
        print(prompts.build_sumerbrain(a.week) or "No open claims: nothing to ask SūmerBrain.")
        return
    if a.film_only:
        print(prompts.build_film(a.week) or "No clips to collect.")
        return
    for path in prompts.build(a.week):
        print(path)


def cmd_ingest(a):
    from bbt import prompts
    print(prompts.ingest(a.week, open(a.file).read()))


def cmd_ingest_raw(a):
    from bbt import rawparse
    print(rawparse.ingest_raw(a.week, a.file))


def cmd_brief(a):
    from bbt import brief
    print(brief.build(a.week))


def cmd_check(a):
    from bbt import data, paid
    gid = data.game_id_for(a.week)
    rep = paid.run_check(a.week, data.game_plays(gid), gid)
    if rep is None:
        p, _ = paid.paths(a.week)
        sys.exit(f"No extract at {p}")
    print(rep.render())
    sys.exit(0 if rep.ok else 1)


def cmd_run(a):
    from bbt import data, packet, paid
    t0 = time.time()
    print("1/3 refreshing nflverse data...")
    data.refresh()
    t1 = time.time()
    print("2/3 checking paid extract...")
    gid = data.game_id_for(a.week)
    rep = paid.run_check(a.week, data.game_plays(gid), gid)
    print(rep.render() if rep else "  no paid extract yet (skipped)")
    t2 = time.time()
    print("3/3 building packet...")
    path = packet.build(a.week)
    t3 = time.time()
    print(f"\n{path}")
    print(f"refresh {t1 - t0:.0f}s · check {t2 - t1:.0f}s · packet {t3 - t2:.0f}s · total {t3 - t0:.0f}s")


def cmd_notes(a):
    from bbt import data, notes
    path = notes.notes_path(a.week, a.source)
    if not path.exists():
        sys.exit(f"No notes at {path}. Format: who | what | evidence")
    game = data.game_plays(data.game_id_for(a.week))
    claims = notes.check(notes.parse(path.read_text()), game)
    for c in claims:
        print(f"\n[{c.kind}] {c.who}: {c.what}")
        for ev, val in c.evidence_values.items():
            print(f"   {ev}: {val}")
        if c.needs_paid:
            print(f"   needs Sūmer/film: {', '.join(c.needs_paid)}")
    v, _ = notes.write_verdicts(claims, a.week, a.source)
    print(f"\nFill in verdicts: {v}\nOpen claims go to SūmerBrain via `bbt prompts {a.week}`.")


def cmd_eye(_):
    from bbt import notes
    df = notes.eye_score()
    print("No graded notes yet." if df.is_empty() else "")
    if not df.is_empty():
        _show(df)


def cmd_opponent(a):
    from bbt import data, opponent
    opp = data.opponent_for(a.week)
    season = data.season_plays()
    print(f"Week {a.week} opponent: {opp} (games through week {a.week - 1})\n")
    _show(opponent.tendencies(season, opp, a.week - 1))
    _show(opponent.by_down_distance(season, opp, a.week - 1))


def cmd_watchfor(a):
    from bbt import data, opponent
    direction = "over" if a.over is not None else "under"
    line = a.over if a.over is not None else a.under
    row = opponent.log_prediction(a.week, data.opponent_for(a.week), a.text, a.metric, direction, line)
    print(f"logged: {row}")


def cmd_grade(a):
    from bbt import data, opponent
    gid = data.game_id_for(a.week)
    r = opponent.grade(a.week, data.game_plays(gid))
    print(r if r else f"No prediction logged for week {a.week}")


def cmd_erased(_):
    from bbt import data, erased, penalties
    est = erased.estimate(penalties.ledger(data.season_plays()), data.baseline_plays())
    t = erased.team_totals(est)
    print(erased.headline(t, config.TEAM) + "\n")
    _show(t)


FORBIDDEN_PREFIXES = ("private/", "data/", ".env")
FORBIDDEN_SUFFIXES = (".duckdb", ".parquet", ".har", ".cookies")
SECRET_PATTERNS = ["password", "passwd", "api_key", "apikey", "secret_key", "access_token",
                   "refresh_token", "authorization: bearer", "set-cookie", "sessionid"]


def cmd_audit(_):
    """Fail if anything private or secret-looking is tracked (or staged) by git."""
    files = subprocess.run(["git", "ls-files", "--cached"], capture_output=True, text=True,
                           cwd=config.ROOT, check=True).stdout.split()
    problems = []
    for f in files:
        if f == "private/README.md":
            continue
        if f.startswith(FORBIDDEN_PREFIXES) or f.endswith(FORBIDDEN_SUFFIXES):
            problems.append(f"{f}: private path/file type")
            continue
        if f.startswith("bbt/__main__.py"):
            continue  # this file lists the patterns themselves
        try:
            text = (config.ROOT / f).read_text(errors="ignore").lower()
        except (IsADirectoryError, FileNotFoundError):
            continue
        for pat in SECRET_PATTERNS:
            if pat in text:
                problems.append(f"{f}: contains '{pat}'")
        if '"schema_version": "v0"' in text and '"sumer": {' in text and f.endswith(".json") \
                and not f.startswith("agent/"):
            problems.append(f"{f}: looks like a paid-data extract")
    if problems:
        print("AUDIT FAILED. Don't push:\n  " + "\n  ".join(problems))
        sys.exit(1)
    print(f"audit ok: {len(files)} tracked files, nothing private")


def main(argv=None):
    p = argparse.ArgumentParser(prog="bbt", description="Big Blue Theory pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("refresh").set_defaults(fn=cmd_refresh)
    s = sub.add_parser("week"); s.add_argument("week", type=int)
    s.add_argument("--no-charts", action="store_true"); s.set_defaults(fn=cmd_week)
    s = sub.add_parser("notes"); s.add_argument("week", type=int)
    s.add_argument("--source", default="me", help="whose notes: me (default) or e.g. skinner")
    s.set_defaults(fn=cmd_notes)
    s = sub.add_parser("prompts"); s.add_argument("week", type=int)
    s.add_argument("--sumerbrain-only", action="store_true",
                   help="just the SūmerBrain prompt for claims still open (after the table runs)")
    s.add_argument("--film-only", action="store_true", help="just the NFL Pro Film Room links for the clip list")
    s.set_defaults(fn=cmd_prompts)
    for name, fn in [("run", cmd_run), ("check", cmd_check),
                     ("brief", cmd_brief), ("opponent", cmd_opponent), ("grade", cmd_grade)]:
        s = sub.add_parser(name); s.add_argument("week", type=int); s.set_defaults(fn=fn)
    s = sub.add_parser("watchfor"); s.add_argument("week", type=int)
    s.add_argument("--metric", required=True); s.add_argument("--text", required=True)
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--over", type=float); g.add_argument("--under", type=float)
    s.set_defaults(fn=cmd_watchfor)
    s = sub.add_parser("ingest"); s.add_argument("week", type=int); s.add_argument("file")
    s.set_defaults(fn=cmd_ingest)
    s = sub.add_parser("ingest-raw"); s.add_argument("week", type=int); s.add_argument("file")
    s.set_defaults(fn=cmd_ingest_raw)
    sub.add_parser("eye").set_defaults(fn=cmd_eye)
    sub.add_parser("erased").set_defaults(fn=cmd_erased)
    sub.add_parser("audit").set_defaults(fn=cmd_audit)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
