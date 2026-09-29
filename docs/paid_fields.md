# Paid data field map (ticket 8)

Where each per-game number lives. **No values here.** This file is public; real numbers live
only in `private/paid/`. Filled in from a read-only Claude in Chrome exploration of the Week 3
game (TEN @ NYG). NFL Pro isn't mapped yet.

## SūmerPass: every view filters to a single game ✅

| Page | What's there | Useful | Schema path |
|---|---|---|---|
| **SūmerLive > game > View Stats** (game page), each team tab | | | `sumer.game_page.nyg` / `.opp` |
| · Team Tendencies | Offensive personnel rate (11/12/13/21/22/Other) | **High** | `tendencies.offensive_personnel` |
| · Team Tendencies | Run concept rate (Inside Zone, Outside Zone, Man, Power, Pull Lead, Counter, Draw, Trap, Other) | **High** | `tendencies.run_concepts` |
| · Team Tendencies | Run/pass, play action, screen rate | Low (free data has these) | `tendencies.*_rate` |
| · Team Tendencies, defense block | Defensive personnel (Base/Nickel/Dime…), Man/Zone, Blitz, Pressure, TFL, Missed tackle rate | **High** | `tendencies.*` |
| · Pass Game | Pass yards, EPA/play, avg time to pressure, avg time to throw, aDOT | **High** (TTT, TTP) | `pass_game` |
| · Passing Performance | By Personnel, **By Coverage** (Cover 0/1/2/2 Man/3/4/6), By Route (team-level), **Pressure** (pressured/clean), **Blitz** (blitz/no blitz): share %, EPA, comp %, comp/att/yds/sacks | **High** | `passing.*` |
| · Run Game | Attempts, yards, yards after contact, EPA/play | Medium | `run_game` |
| · Rushing Performance | **By Concept**, **By Gap**, By Box, By Personnel: share %, EPA, YACo, att/yds | **High** | `rushing.*` |
| · Game Matchups (View All) | Blocker vs rusher and defender vs receiver pairs | Medium, optional | not in schema yet |
| · Play-by-play cards | Per-play personnel, box, man/zone, coverage, concept, gap, blitz, stunt, pressure, RPO, PA | High later (joins to free play-by-play by quarter + clock + down) | not in schema yet |
| **Teams > Offense** (Week = this week) | NYG row: Plays, EPA, sack %, aDOT, PA %, screen %, pressure %, blitzed %, YaCo, YBC, zone/gap runs, run concepts, 11/12/13/21 personnel, light/heavy box | **High** | `sumer.teams_offense` |
| **Teams > Defense** (Week = this week) | NYG row: pressure %, blitz %, rush 3/4/5/6+, time to pressure, time to throw, man/zone, 1-high/2-high, safety rotation, base/nickel/dime, missed tackles, TFL, PBU, contested target %, DPI | **High** | `sumer.teams_defense` |
| **Players > <position>** (Week + Team = NYG) | OL: snaps, pass-block snaps, sacks, pressures, pressure %, false starts, holds. CB/S/LB: coverage snaps, targets, catches, yards, INT, PBU, missed tackles, run stops, pressures | **High** | `sumer.players.*` |
| SūmerBrain | Free-text answers with counts | Backup only | `sumerbrain` |

### What we learned
- **Denominators:** Sūmer's "Plays" = run + pass + kneels, with no penalty snaps. That matches free
  play-by-play exactly. Game-page passing splits divide by pass attempts incl. sacks. The Teams
  table's pressure % divides by dropbacks incl. scrambles, so the two pressure rates differ a
  little. The checker compares both against the free data.
- **Coverage shells (Cover 0/1/2/3/4/6)** are only on the game page. Teams has man/zone and 1-/2-high only.
- **22 personnel** is only on the game page.
- **Routes** are team-level on the game page. Per-receiver routes are unconfirmed (WR/TE tables not opened yet).
- **Reading gotchas:** in the page structure, single-digit numbers sometimes drop out (game-page
  panels, matchup modal). Plain page text works for Teams/Players tables. On the game page, the
  value comes *before* its label. Dropdowns fade in slowly.
- **Small inconsistencies inside Sūmer** (a matchup row with more yards than the player's game
  total; a player shown with an old team's logo). Prefer the Players tables over the matchup modal.
- **SūmerBrain** matched Sūmer's own tables on both questions it answered, with counts. It crashed
  once opening a new chat. Since the tables already have these numbers, SūmerBrain is only a
  backup for questions the tables can't answer.

## NFL Pro
Not explored yet. Run `agent/EXPLORE.md` with `SITE FOR THIS RUN` = `NFL Pro`.
