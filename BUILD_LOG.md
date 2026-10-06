# Build log

One line per session: what I learned or what broke, then the next step.

| Date | Ticket | Learned / broke | Next step |
|---|---|---|---|
| 2026-09-29 | 1 | `play_id` is a float in pbp and an int in FTN. `posteam` on a kickoff is the *receiving* team. | — |
| 2026-09-29 | 2 | FTN for Week 3 not published yet (Weeks 1–2 are in). Participation for 2026 isn't available at all, so personnel has to come from Sūmer. | — |
| 2026-09-29 | 3 | `fixed_drive` sometimes folds the opening kickoff into the first drive. Drop kickoffs before grouping. | Check the drive table against the official box score. |
| 2026-09-29 | 4 | The biggest swing of Week 3 (+46 pts) was the late INT, and #2 (−12.5) was a 4th-and-1 encroachment. | Confirm the top 10 against memory. |
| 2026-09-29 | 5 | Week 3 early-down pass rate 34% vs 51% usual: the run-first plan is the headline. | — |
| 2026-09-29 | 6 | Offside that wipes a sack is a "wiped" play, not pre-snap. Classify on the text, not the penalty name. Strip "reported in as eligible" / injury notes before deciding. | Eyeball the Week 3 ledger. |
| 2026-09-29 | 6 | Run + pass + wiped plays = official snap counts, exactly, in all 3 games. Good sign the classifier is right. | — |
| 2026-09-29 | 7 | In nflverse a TD is always exactly 7 EP and a made FG exactly 3, so an erased TD = `7 − ep`, no comparables needed. My count: 150 wiped gains / 11 wiped TDs league-wide vs the spec's 143 / 14. Worth checking the definitions. | — |
| 2026-09-30 | 8 | Sūmer explored (Claude in Chrome, 9 page loads, no bot flags). Every view filters to one game. Sūmer "Plays" = run + pass + kneels (no penalty snaps) and matches free data exactly. Its two pressure rates use different denominators (pass attempts vs dropbacks). SūmerBrain matched the tables 2/2 but crashed once. | Explore NFL Pro. |
| 2026-09-30 | 9 | Schema v1: Sūmer tables stored as verbatim `{label: value}` rows. The checker now cross-checks split shares vs counts, split totals vs each other, and plays/attempts/sacks vs free data. Values read from screenshots are tracked separately. | First real Week 3 extract. |
| 2026-09-30 | 8 | NFL Pro run 1: every data table empty. Run 2: they load, just 20–30s late. NFL Pro = tracking (TTT, separation, RYOE, routes) + film. Sūmer = scheme (coverage, concepts, gaps, per-OL pressures). The two chart independently and differ by a play or three on blitzes and pressures. | First real extracts. |
| 2026-10-06 | 11 | First real notes week (Week 4). FTN landed within 2 days. Free data settled about half the claims; FTN's QB-fault-sack and backfield-count flags were the most useful. Auto-generated SūmerBrain questions were too vague and duplicated what free data already answered, so I wrote targeted ones by hand. | Make `notes.py` handle more evidence types (field goals, punt returns, run direction) and only generate SūmerBrain questions for things the paid tables can't answer. |
| 2026-10-06 | 10/16 | Too many steps for the user. Now: notes in → `bbt prompts N` (two self-contained extension prompts) → paste replies → `bbt ingest` → `bbt brief N` (one notes doc). Bug caught: verdicts keyed by line number shifted when the notes file had a header line; verdicts are now matched by claim text (`notes.record_verdicts`). | Real Week 4 extension replies. |
