# Weekly extraction (Claude in Chrome)

> **You don't paste this file anymore.** `python -m bbt prompts N` builds the two self-contained
> prompts from `bbt/prompts.py`. This file is the longer reference for why each rule exists.

You are copying paid charting data for **one** Giants game from pages the user is already
logged into. Output: a JSON file following `agent/paid_extract.schema.json` (**v1**) plus the
raw page text. Do **one site per run** (the task says which). Put `null` for the other site's
section and list it in `missing_fields`.

## Hard rules
1. **Read only.** Never click export, download, share, settings, account, billing, "upgrade",
   or anything that changes state. Never log in or out, and never type credentials.
2. **One game only**: the game named in the task. Don't browse other games or seasons.
3. **Human pace.** One tab. Wait for each page to load fully, then read it. At least 10 seconds
   between page loads and 5 seconds between clicks on the same page. Cap per run: **8 page
   loads and 40 clicks** (SūmerPass), **10 page loads and 45 clicks** (NFL Pro). Only the normal page: no dev tools, console, page source, API
   calls or URL editing. Move around by clicking visible links and controls. Don't loop
   through teams, weeks or players.
4. **Copy numbers exactly** as shown: same rounding, same units. Percentages stay 0–100
   (`38.5`, not `0.385`). Don't calculate, estimate, or "fix" anything.
5. **If a number isn't on the page**, put `null` and add its dotted path to `missing_fields`.
   Never fill a gap from memory or another source.
6. **Read the plain page text first.** Some panels drop single-digit numbers when read as page
   structure. If a number is missing from the text but visible on screen, take a screenshot,
   read it from there, and add its dotted path to `screenshot_fields`.
7. **Return the raw page text** of every page and panel you read, with a
   `=== <page / tab / panel> ===` header before each.
8. Describe pages as breadcrumbs, **not** URLs. URLs can carry session tokens.
9. If you hit a login wall, CAPTCHA, "unusual activity" or rate-limit message, or a forced
   logout, **stop**, don't retry, and report where you were. For a generic app error ("Something
   went wrong"), wait 30 seconds and try once more. If it happens again, skip that item and
   note it in `agent_notes`.

## SūmerPass route (about 4 page loads, 25–30 clicks, 10–12 minutes)
Dropdowns fade in slowly: wait until a menu is fully visible before clicking an option.

1. **SūmerLive** → the game → **View Stats** (1 page load).
   - **Giants tab** → `sumer.game_page.nyg`
     - Team Tendencies: offensive personnel, run concepts, the defense block (defensive
       personnel, man/zone, blitz, pressure, TFL, missed tackles). Personnel and concept rates
       are shown without a % sign: copy the number.
     - Pass Game and Run Game blocks. **The value comes before its label** here.
     - Passing Performance tabs: **By Personnel, By Coverage, By Route, Pressure, Blitz**.
       For each row: label, share %, EPA, comp %, comp, att, yds, sacks.
     - Rushing Performance tabs: **By Concept, By Gap, By Box, By Personnel**. For each row:
       label, share %, EPA, YACo, att, yds.
   - **Opponent tab** → `sumer.game_page.opp`, same panels. This is what NYG's defense faced.
     Its "defense block" is the *opponent's* defense: copy it anyway, it's labeled by tab.
2. **Teams** → Week: Regular Season → this week (1–2 page loads).
   - Side = Offense: copy the **NYG row**, every column, as `{column label: value}` →
     `sumer.teams_offense`.
   - Side = Defense: the week filter carries over. NYG row → `sumer.teams_defense`.
3. **Players** → set Week = this week and Team = NYG once (both stick when you change
   position). Step through **Offensive Line, Cornerback, Safety, Linebacker, Edge Rusher,
   Defensive Interior** (1 page load). Copy every NYG row as `{column label: value}`,
   including the `Player` column. If a table has pages, read page 1 only; with Team = NYG it
   should all fit.
4. Skip the Game Matchups modal and the play-by-play cards for now.

## NFL Pro route (about 7 page loads, 30–40 clicks, 15–20 minutes)
Work in the tab the user is looking at: background tabs don't take clicks. Dropdowns often need
the list fully open before a pick registers. If a pick doesn't take, wait and try once more.
The scoreboard strip sits just above the game tabs. Make sure a click lands on the tab, not
on a different game.

1. **Games** → Week dropdown → this week → the NYG game card (2 page loads).
2. **Stats** tab → `nfl_pro.game_stats`. It first says "Sorry, no results!" and fills in
   **20–30 seconds** later (the "available the day after" banner stays; ignore it). Read Passing,
   Rushing and Receiving in **Overview**, then toggle **Advanced** (tables blank for about 10s)
   and add those columns to the same player rows. Both teams' players.
3. **Play By Play** tab → `nfl_pro.personnel`. If the Play Type filter allows it, limit it to
   offensive plays (pass + run) and record that in `play_type_filter`. Set Team = NYG and note
   "Number of plays" as personnel `ALL`. Then pick each Personnel option (only the groupings
   used in this game appear) and note the count. Repeat with Team = opponent.
4. **Watch Film → Film Room**, Game = this game → `nfl_pro.film_room`: note "N plays matching
   your criteria" with no filters, then with **Pressure** ticked, then with **Blitz** instead
   (untick Pressure). Don't play clips.
5. **Next Gen Stats → Team Defense**, Week = this week → NYG row of **Pass Defense** and
   **Run Defense** → `nfl_pro.ngs_team_defense`. Then **Team Offense** (Passing, Rushing,
   Receiving) → `nfl_pro.ngs_team_offense` (about 2 page loads).
6. Game → **Insights**: copy the cards' text verbatim → `nfl_pro.insights`.

## SūmerBrain (only if the task includes questions)
Ask each question exactly as written in a **new chat**, and a second time in another new chat.
Record both answers verbatim in `sumerbrain[]`, with `counts_given` and `consistent` set.
Don't interpret or average them.

## Output
Reply with two fenced blocks: the JSON extract, then the raw page text. They get saved as
- `private/paid/<season>_wk<NN>.json`
- `private/paid/<season>_wk<NN>_raw.txt`

and checked with `python -m bbt check <week>`.

## Task template (paste into Claude in Chrome)
```
Follow agent/INSTRUCTIONS.md from the big-blue-theory repo (paste the file below).
Game: <GAME_ID> (Week <N>, <season>), NYG vs <OPP>. Schema: agent/paid_extract.schema.json v1 (pasted below).
SūmerBrain questions: <paste private/notes/<tag>_sumerbrain_questions.json, or "none">
<paste INSTRUCTIONS.md>
<paste paid_extract.schema.json>
```
