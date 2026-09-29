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

## NFL Pro: mapped (run 2)

Run 1 hit empty data tables. Run 2 found the data: the game's Stats tab fills in 20–30 seconds
after it first says "no results". Every view below filters to the single game or week.

| Page | What's there | Useful | Schema path |
|---|---|---|---|
| Game > **Stats** > Passing (Overview/Advanced) | TTT, CPOE, QB pressures (QBP, QBP %), sacks, dropbacks, EPA; AY/Att, deep %, PA %, tight-window %, avg separation, **Blitz % faced** | **High** (TTT, pressures, blitz) | `nfl_pro.game_stats.passing` |
| Game > Stats > Rushing | **RYOE**, RYOE/Att, **YACo**, 10+ yds, 15+/20+ MPH; xRY, xYPC, success %, inside %, **Stacked %** (≈ 8+ box), UC % | **High** | `nfl_pro.game_stats.rushing` |
| Game > Stats > Receiving | **Routes**, CROE, YAC, **YACOE**, AY/Tgt, **Avg. Sep**; target %, **yds/route**, EPA/tgt, deep %, tight-window % | **High** | `nfl_pro.game_stats.receiving` |
| Game > **Play By Play** | Filters Team + **Personnel** / Off Formation / Pass Rush Count / Box Count → "Number of plays" | **High** (personnel, second source to Sūmer) | `nfl_pro.personnel` |
| **Film Room** (Game preset) | "N plays matching": Pressure, Blitz, PA, Motion, QB alignment, air yards, TTT, rush direction, run stuff, receiver alignment, separation, def personnel, box, coverage type (press/off). Each play lists all 22 players on the field | High for pressure/blitz counts and film | `nfl_pro.film_room` |
| NGS > **Team Defense** (Week) > Pass / Run Defense | Blitz %, QBP, QBP %, TTP, get-off, sack %, TTT, YACOE, avg sep… | **High** | `nfl_pro.ngs_team_defense` |
| NGS > **Team Offense** (Week) | Same layout, offense side (not opened yet) | likely High | `nfl_pro.ngs_team_offense` |
| Game > **Insights** | Prose cards (run stops, yards after contact, air yards/target…) | Medium: story hooks | `nfl_pro.insights` |
| Game > Box Score / Team Stats | Standard box score | Low: free data has it | — |

### Not on NFL Pro
Coverage shells (only press/off), run concepts and designed vs actual gap, route *types*,
pressures allowed per OL. **Sūmer covers all four**, so the two sources complement each other:
Sūmer = scheme (coverage, concepts, gaps, per-OL pressures), NFL Pro = tracking (time to throw,
separation, RYOE, routes and yards per route per receiver) + film.

### Cross-checks found
- NFL Pro's numbers agree with each other: Film Room pressure plays equal the sum of both QBs'
  QBP, and team Blitz % equals the opposing QB's Blitz % faced.
- **Sūmer and NFL Pro chart independently and don't always agree** (e.g. Week 3 NYG blitz count
  and NYG QB pressures differ by 1–3 plays). The packet shows them side by side. Where they
  disagree, say so in the post rather than picking one.
- NFL Pro "Number of plays" counts every play (special teams and penalties too), so it's
  bigger than Sūmer's "Plays". Filter to offensive play types, or use the free data's count.

### Free participation data?
nflverse's participation data (personnel, man/zone) stops at 2025: `load_participation(2026)`
returns "Season must be between 2016 and 2025". So 2026 personnel and coverage have to come
from the paid sources, at least until nflverse catches up.
