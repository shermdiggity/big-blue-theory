# Browser agent instructions (Claude in Chrome)

You are extracting paid charting data for **one** Giants game from pages the user is already
logged into (SūmerPass / SūmerBrain, NFL+ Premium / NFL Pro). Your output is a JSON file that
follows `agent/paid_extract.schema.json`, plus a raw text file.

## Hard rules
1. **Read only.** Never click export, download, share, settings, account, billing, "upgrade",
   or anything that changes state. Never log in or out, and never type credentials.
2. **One game only**: the game named in the task. Don't browse other games or seasons.
3. **Human pace.** One tab. Wait for each page to load fully, then read it. At least 10 seconds
   between navigations and 5 seconds between filter changes. Cap: 20 page loads per weekly run.
   Only the normal page: no dev tools, console, page source, API calls or URL editing.
   Navigate by clicking visible links and controls. Don't loop through teams, weeks or players.
4. **Copy numbers exactly** as shown: same rounding, same units. Percentages stay 0–100
   (`38.5`, not `0.385`). Don't calculate, estimate, or "fix" anything.
5. **If a number isn't on the page**, put `null` and add its dotted path to `missing_fields`
   (for example `sumer.offense.time_to_throw`). Never fill a gap from memory or another source.
6. **Return the raw page text** you read (the visible text of each page, with a
   `=== <source> / <page name> ===` header before each). It gets saved as
   `private/paid/<season>_wk<NN>_raw.txt`, and the checker looks up every number you
   report in it.
7. Page names in `sources` are breadcrumbs ("Sūmer > Team > NYG > Week 3 > Personnel"), **not**
   URLs. URLs can carry session tokens.
8. If you hit a login wall, paywall, CAPTCHA, "unusual activity" or rate-limit message, a forced
   logout, or anything unexpected, **stop** and report it. Don't retry, and don't work around it.

## SūmerBrain questions (only if `private/notes/<tag>_sumerbrain_questions.json` exists)
SūmerBrain is useful but not reliable on its own: it has given different answers to the same
question on different days. For each question in the file:
- Ask it exactly as written. It already includes an explicit definition and asks for counts.
- Start a **new chat** and ask it a second time.
- Record both answers verbatim in `sumerbrain[]`. Set `counts_given` if it gave raw counts,
  and `consistent` if both answers give the same numbers.
- Don't interpret or average the answers.

## Output
Reply with two fenced blocks: the JSON extract, then the raw page text. The user saves them as
- `private/paid/<season>_wk<NN>.json`
- `private/paid/<season>_wk<NN>_raw.txt`

and runs `python -m bbt check <week>`.

## Task template (paste into Claude in Chrome)
```
Follow the instructions in agent/INSTRUCTIONS.md from the big-blue-theory repo.
Game: <GAME_ID> (Week <N>, <season>). Team: NYG.
Fill agent/paid_extract.schema.json (v0). Pages to visit:
  Sūmer: <list the exact pages from docs/paid_fields.md>
  NFL Pro: <list the exact pages from docs/paid_fields.md>
SūmerBrain questions: <paste private/notes/<tag>_sumerbrain_questions.json or "none">
Return the JSON and the raw page text.
```
