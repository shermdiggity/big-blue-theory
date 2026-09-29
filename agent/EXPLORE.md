# Ticket 8 mission: explore SūmerPass + NFL Pro (for Claude in Chrome)

Paste everything below the line into Claude in Chrome, with the user already logged into
sumersports.com (SūmerPass) and pro.nfl.com (NFL+ Premium) in the same Chrome profile.

**Run it once per site, back to back is fine** (the sites don't share anything, so the caps are
per site). Separate runs just keep each report focused. Replace `SITE FOR THIS RUN` below with
`SūmerPass` or `NFL Pro`. Watch the first run so you can stop it.
Paste Claude's final reply back into the Claude Code session. It turns that into
`docs/paid_fields.md` and the final `agent/paid_extract.schema.json`.

---

You are doing reconnaissance for a weekly, data-backed New York Giants blog. The user is logged
into two paid football-data sites in this browser. Your job: **map what per-game data each site
has, where it lives, and how reliably it can be read**, so that a later weekly run can extract
one game's numbers into a fixed schema. The reference game is **Week 3, 2026: Tennessee Titans
at New York Giants (NYG won 12–7).**

**SITE FOR THIS RUN: `SITE FOR THIS RUN`.** Only explore that site in this run.

## Rules (non-negotiable)
The goal is to use the site the way one careful person reading it would. Nothing about
this session should look or behave like a scraper.
- **Read only.** Never click export, download, share, account, settings, billing, subscribe or
  upgrade, and never change profile or preferences. Never log in, log out, or type credentials.
  If a page asks you to sign in, stop and tell the user.
- **Pace like a person reading.** One tab only. Wait until the page has fully loaded, then
  spend time reading it. Leave **at least 10 seconds between navigations**, and at least 5
  seconds between filter or dropdown changes on the same page. Never fire actions back to back.
- **Hard caps for this run: 25 page loads, 60 filter/tab/dropdown changes, about 30 minutes.**
  Keep a running count. When you hit any cap, stop and report what you have. Partial is fine.
- **No bulk behavior.** Don't cycle through every team, week or player. Stick to NYG, Week 3,
  plus at most one other game for comparison. Don't paginate through whole league tables:
  read the first page and note that more pages exist. Don't scroll-to-load endlessly.
- **Only the normal page.** No developer tools, console, network tab, page source, API
  endpoints, URL editing to jump around, or bookmarklets. Navigate only by clicking visible
  links and controls, the way a person would.
- **Video:** in the Film Room, play at most 2 clips, briefly, just to confirm what a clip is
  linked to. Don't download or queue up playlists.
- **SūmerBrain:** only the 6 questions listed below, no more. Wait for each answer to finish
  before doing anything else.
- Filters, dropdowns, tabs and sorting are fine: they only change the view.
- If you see a CAPTCHA, "unusual activity", a rate-limit or "too many requests" message, a
  forced logout, or anything that looks like it's flagging automation, **stop immediately**,
  don't retry, and report exactly where you were.
- Don't copy URLs that contain tokens or session ids. Describe pages by breadcrumb
  ("SūmerPass > Teams > Offense > Personnel Tendency").

## What the blog already gets free (skip these unless paid is clearly better)
Play-by-play for every play (down, distance, yards, EPA, win probability, penalties, shotgun,
no-huddle, air yards, pass location), and FTN charting: motion, play action, RPO, screen, men in
box, number of blitzers and pass rushers, which read the QB threw to, drops, catchable and
contested balls. Also snap counts per player.

## What the blog needs from paid sources (look hardest for these)
1. Offensive **personnel** usage (11/12/13/21…) and **formation** usage, for this game only.
2. **Coverage**: what NYG's defense played (Cover 0/1/2/3/4/6, man vs zone) and what NYG's
   offense faced. Results by coverage if shown.
3. **Pressure**: pressure rate, pressures allowed per OL, pressures per pass rusher, time to
   pressure, time to throw.
4. **Routes**: routes run per receiver, targets per route, route types.
5. **Run game** (NFL Pro / Next Gen Stats): run scheme or concept (zone, gap, man; the 16-label
   run concepts), designed gap vs actual gap, rush yards over expected, yards before contact,
   8+ box rate.
6. **Receiving** (NGS): separation, cushion, YAC over expected.
7. **Passing** (NGS): time to throw, air yards, CPOE, aggressiveness, completion probability.
8. Anything per-player for the Giants' defense: coverage snaps, targets allowed, run stops,
   missed tackles.
9. NFL Pro **Game Page** insights and the **Film Room** (All-22): what filters exist, and can
   you filter to one game plus a concept (e.g. "NYG offense, Week 3, pressure plays")?

## How to explore
**SūmerPass** (sumersports.com, logged in):
- Find the NYG team page, and the team stat tables (offense, defense, personnel tendency,
  formation tendency, coverage…). For each table: can you filter to **a single game / week**?
  (critical: season totals are much less useful)
- Find player tables (QB, WR/TE, RB, OL, pass rush, coverage). Same question.
- Find any **game-level page** for Week 3 TEN @ NYG (box score, charting, SūmerLive recap).
- **SūmerBrain** (their AI): ask these three, each **twice in two separate new chats**:
  a. "In the 2026 Week 3 game TEN at NYG, what was the Giants' defensive blitz rate? Define
     blitz rate as blitzes divided by opponent dropbacks, this game only, and give the raw counts."
  b. "In the 2026 Week 3 game TEN at NYG, what share of Giants offensive snaps were in 11
     personnel? Give snaps and total offensive snaps, this game only."
  c. "In the 2026 Week 3 game TEN at NYG, how many pressures did the Giants' offensive line
     allow, broken down by player? Give counts, this game only."
  Then look for the same numbers in SūmerPass's own tables and compare.

**NFL Pro** (pro.nfl.com, logged in):
- The **Game Page** for Week 3 TEN @ NYG: every section and tab.
- Team stats and player stats pages. Which ones filter to a single game?
- Next Gen Stats categories for passing, rushing (run concept / gap), receiving, pass rush,
  and coverage.
- **Film Room**: list every filter. Try "NYG, 2026 Week 3" and note whether clips link to
  specific plays (quarter, clock, down and distance), which would let clips be joined to the
  play-by-play.

## What to send back (exactly this format)

### A. Field map
One row per useful per-game number. **No actual values in this table**, just where the
number lives.

| Source | Breadcrumb / page | Field label as shown | Unit (count / % / avg / yds) | Single-game filter? (Y/N/how) | Team or player | Useful for blog? (H/M/L) | Also in free data? |

### B. Sample values for spot-checking (Week 3 only)
10–15 values copied **exactly** as shown, e.g. `SūmerPass > Teams > Defense > Coverage | Cover 3 | xx.x%`.
Mix of both sites. (These stay private and are used to test the extractor.)

### C. SūmerBrain test
For each question a/b/c: answer 1, answer 2 (verbatim, trimmed), whether it gave counts,
whether the two agreed, and whether it matched SūmerPass's own table.

### D. Recommended weekly extraction route
The shortest ordered list of pages (with the filter clicks on each) that captures every
H-rated field for one game. Estimate page views and minutes.

### E. Gaps and gotchas
Anything season-only, anything that needs hovering or expanding, lazy-loaded tables,
things visible only in charts (not text), paywalls within the paywall, and anything that
looked like it discouraged automated access.
