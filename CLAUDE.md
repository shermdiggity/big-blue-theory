# Big Blue Theory: how a week runs

The user watches the Giants, sends notes, pastes two browser-extension replies, and writes the
post from one notes doc. Everything else is this session's job. Keep it that simple for them.

## The weekly loop
1. **User sends notes** (any format: bullets, rants, the `who | what | evidence` style).
   - `python -m bbt refresh` (nflverse lands the morning after; FTN within ~2 days).
   - Save the notes as claims in `private/notes/<tag>.md` (`who | what | evidence | type`), one per line.
     Someone else's takes go in `<tag>_<source>.md`.
   - `python -m bbt notes N`, then investigate each claim with real queries (`bbt.data`, polars).
     Free data first: pbp, FTN flags (`is_qb_fault_sack`, `n_offense_backfield`, `n_blitzers`, `read_thrown`…),
     snap counts, prior seasons in `baseline_plays()`.
   - Record each verdict with `notes.record_verdicts(N, {"who: start of claim": (verdict, comment)})`.
     **Never key verdicts by line number.** The comment must hold the numbers behind the verdict.
   - Write game-specific paid asks to `private/notes/<tag>_asks.md` (`## sumer` / `## nflpro`).
   - **Nothing gets dropped for being unverifiable: it goes to SūmerBrain.** Claims still can't-check /
     mixed after free data get a question automatically; also hand-write one (in
     `<tag>_sumerbrain_questions.json`, keyed `"claim": "who: what"`) for every question the user asks inside
     their notes. Max 6 a week, hand-written first. It's part of prompt 1 (Sūmer).
   - `python -m bbt prompts N` and give the user the files in `private/prompts/`. That's all they paste.
     After the table runs, claims still open → `python -m bbt prompts N --sumerbrain-only`.
   - SūmerBrain answers are shown as SūmerBrain's charting (🧠). Cross-check them against the tables
     and free data where you can, and say so in the verdict; never silently promote them to fact.

## How to ask SūmerBrain (learned the hard way)
It's a stats chatbot over Sūmer's charting, not a film room. Ask like a fan, not a film analyst.
- **Works:** say what you saw, ask if it's true, ask for a split it can compute and a comparison.
  "I've noticed the Giants running away from their fullback a lot lately. Is that true? How do runs
  behind him compare with runs away from him?" → counts, rates, week-by-week, caveats.
- **Gets refused ("needs film-level analysis"):** per-play lists, quarter + clock, alignments,
  "who lost the edge on each run", "the primary defender on every target", demands for definitions.
- Ask each question **once**, in a new chat. On a refusal, send **one** reworded follow-up asking
  for its charting stats at the team/player level. Never resend the same wording.
- It often answers more than asked (e.g. it used per-play run-block grades for "who lost blocks").
  Watch for swapped player positions/sides and check names and counts against the Players tables.

2. **User pastes the two extension replies.** Save each to the scratchpad, `python -m bbt ingest N <file>`,
   then `python -m bbt check N`. If they pasted page text with no JSON block, save the text as
   `private/paid/<tag>_raw.txt` (Sūmer first, then a `##### nfl_pro #####` line, then NFL Pro) and run
   `python -m bbt ingest-raw N private/paid/<tag>_raw.txt`. Update the verdicts that were waiting on paid data.
   Sūmer conventions: split "comp/att" excludes sacks, share % is of dropbacks (att + sacks).
3. **Charts.** For each point worth a picture, add a spec to `private/notes/<tag>_charts.json`
   (kinds and fields in `docs/charts.md`). Title = the takeaway; subtitle = what's measured + sample;
   source names SūmerBrain when it's SūmerBrain; `claim` = the note it backs. `python -m bbt charts N`,
   then open every PNG and look at it before sending. The five free-data charts build themselves.
4. `python -m bbt brief N` → `private/briefs/<tag>.md`, the doc they write from (it also builds the
   packet and all charts, each story chart under its note). Send it and the chart PNGs with SendUserFile.
   - **Clips:** the doc's "Clips to watch" list builds itself from the top swing plays plus every
     "Q3 2:30"-style play cited in verdicts and SūmerBrain answers, so cite plays that way. Prompt 2
     (NFL Pro) collects a Film Room link for each; `bbt prompts N --film-only` does just that step.
     Links play only for NFL+ Premium accounts. NFL video can't be re-uploaded to a public post.
5. Ask for next week's watch-for and log it: `python -m bbt watchfor N+1 --metric … --over|--under …`.

## Non-negotiables
- **The repo is public.** Paid numbers, notes, briefs, prompts and packets live only in `private/`
  (gitignored). Never put real Sūmer/NFL Pro values in code, tests, docs or commit messages.
  Run `python -m bbt audit` before every push.
- Browser-extension prompts stay read-only, slow and capped (see `bbt/prompts.py`). Never loosen that.
- Don't invent takes or quotes for real people.
- Writing rules for the post: keep what happened / what was probably supposed to happen / opinion
  separate; every claim gets its number; say what can't be known from outside.
