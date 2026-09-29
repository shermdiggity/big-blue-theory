# Ticket 8 worksheet: which paid numbers do we actually use?

**How this gets filled:** Claude in Chrome runs the mission in `agent/EXPLORE.md` against the
logged-in sites, and its field map (section A) replaces the tables below. The sample values
(section B) go to `private/`, never here. Until then, `agent/paid_extract.schema.json` is a
**draft v0**.

What public info says to expect (to be confirmed by the exploration):
- **SūmerPass**: team offense/defense tables, personnel- and formation-tendency tables, player
  tables, all filterable by coverage, personnel, formation and game state. Charted in-house
  (pressure, routes, coverage), updated about 2 hours after each slate. SūmerLive charts games
  live. Open question: can every table filter to a **single game**?
- **NFL Pro (NFL+ Premium)**: 95+ Next Gen Stats metrics, Game Pages (preview and recap
  insights), Film Room with All-22 plus filters and saved playlists. NGS run-concept model
  (16 labels, grouped into man/zone/gap).

Don't paste any actual numbers here. This file is public. Just write down *where* each number lives.

## SūmerPass
| Field (schema path) | Page / breadcrumb | Shown as (count, %, avg) | Would I use it? | Notes |
|---|---|---|---|---|
| sumer.offense.personnel | | | | 11/12/13/21… |
| sumer.offense.formations | | | | |
| sumer.offense.coverage_faced | | | | |
| sumer.offense.pressure_rate_allowed | | | | |
| sumer.offense.time_to_throw | | | | |
| sumer.defense.coverage | | | | Cover 0/1/2/3/4/6 |
| sumer.defense.man_rate / zone_rate | | | | |
| sumer.defense.blitz_rate | | | | cross-check vs FTN `n_blitzers` |
| sumer.defense.pressure_rate | | | | |
| sumer.players[].routes | | | | |
| sumer.players[].pressures_allowed | | | | OL |
| sumer.players[].pressures | | | | pass rushers |
| sumer.players[].targets_allowed | | | | DBs |
| _(add anything else you find)_ | | | | |

## NFL Pro (Next Gen Stats)
| Field (schema path) | Page / breadcrumb | Shown as | Would I use it? | Notes |
|---|---|---|---|---|
| nfl_pro.run_scheme | | | | zone / gap / power… |
| nfl_pro.designed_vs_actual_gap | | | | |
| nfl_pro.passer.time_to_throw | | | | |
| nfl_pro.passer.aggressiveness | | | | |
| nfl_pro.receivers[].avg_separation | | | | |
| nfl_pro.rushers[].rush_yards_over_expected | | | | |
| run-blocking assignments | | | | may be film-only |
| _(add anything else you find)_ | | | | |

## SūmerBrain
Try 2–3 questions about Week 3 and note: did it give counts? Same answer when asked twice
in a new chat? Did it match Sūmer's own tables?

| Question | Answer 1 | Answer 2 (new chat) | Matches table? |
|---|---|---|---|
| | _(keep actual numbers out of this public file; write "same"/"different")_ | | |

## Decisions
- Fields to drop from the schema:
- Fields to add:
- Which of these can the free data already answer? (skip those)
