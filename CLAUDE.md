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
   - **Nothing gets dropped for being unverifiable: it goes to SūmerBrain.** Every claim still
     can't-check / mixed after free data gets a SūmerBrain question automatically. Also write one
     (in `<tag>_sumerbrain_questions.json`, keyed by `"claim": "who: what"`) for every question the user
     asks inside their notes ("why is X trending", "who's to blame", "what changed"). Questions demand
     definitions, raw counts and the specific plays, and get asked twice.
   - `python -m bbt prompts N` and give the user the files in `private/prompts/`. That's all they paste.
     After the table runs, claims still open → `python -m bbt prompts N --sumerbrain-only`.
   - SūmerBrain answers are kept and shown as SūmerBrain's charting (🧠), labeled unreliable if the two
     asks disagree. Cross-check them against the tables where possible; never silently promote them to fact.
2. **User pastes the two extension replies.** Save each to the scratchpad, `python -m bbt ingest N <file>`,
   then `python -m bbt check N`. If they pasted page text with no JSON block, save the text as
   `private/paid/<tag>_raw.txt` (Sūmer first, then a `##### nfl_pro #####` line, then NFL Pro) and run
   `python -m bbt ingest-raw N private/paid/<tag>_raw.txt`. Update the verdicts that were waiting on paid data.
   Sūmer conventions: split "comp/att" excludes sacks, share % is of dropbacks (att + sacks).
3. `python -m bbt brief N` → `private/briefs/<tag>.md`, the doc they write from (it also builds the
   packet and charts). Send it with SendUserFile.
4. Ask for next week's watch-for and log it: `python -m bbt watchfor N+1 --metric … --over|--under …`.

## Non-negotiables
- **The repo is public.** Paid numbers, notes, briefs, prompts and packets live only in `private/`
  (gitignored). Never put real Sūmer/NFL Pro values in code, tests, docs or commit messages.
  Run `python -m bbt audit` before every push.
- Browser-extension prompts stay read-only, slow and capped (see `bbt/prompts.py`). Never loosen that.
- Don't invent takes or quotes for real people.
- Writing rules for the post: keep what happened / what was probably supposed to happen / opinion
  separate; every claim gets its number; say what can't be known from outside.
