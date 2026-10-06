# Big Blue Theory

**A weekly, honest, data-backed breakdown of the New York Giants, written for any fan.**
*One must imagine the Giants fan happy.*

Every week: what the gameplan was, how well it was executed, who delivered and who didn't, which
decisions mattered, and one thing to watch for next week, graded in public.

This repo is the pipeline behind the posts. It pulls free play-by-play and charting data, joins
it with paid charting that stays private, and builds one game packet to write from.

## What's here

| | |
|---|---|
| `bbt/` | the pipeline (`python -m bbt ...`) |
| `scorecard.csv` | every weekly "watch for" prediction, graded after the game |
| `CORRECTIONS.md` | public corrections log |
| `BUILD_LOG.md` | one line per build session: what I learned or what broke |
| `docs/columns.md` | the ~30 play-by-play columns this uses, in plain English |
| `agent/` | instructions + schema for the browser agent that reads paid pages |

## The stat nobody publishes: points erased by penalties

Free play-by-play measures a penalty from where the play started. It doesn't say what the play it
wiped out was worth. `bbt/penalties.py` sorts every flag into:

- **pre-snap**: nothing happened but the flag
- **wiped**: a play happened and was erased ("No Play")
- **added**: the play stood and yards were added on

For wiped plays it parses the play text before `PENALTY` to find the erased gain, TD, sack or
interception. `bbt/erased.py` then prices the erased play from real plays with the same down and
similar distance, field position and result. Touchdowns and made field goals are exact: in
nflverse a TD is always worth 7 EP and a FG 3, so an erased TD is worth `7 − ep`.

Sanity check: counting snaps as run + pass + *wiped* plays (not pre-snap flags) reproduces the
official offensive and defensive snap counts exactly for every 2026 Giants game so far.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m bbt refresh        # load 2024-2026 nflverse data into data/bbt.duckdb (~20s)
python -m bbt brief 3        # THE notes doc to write from -> private/briefs/2026_wk03.md (+ packet, charts)
python -m bbt prompts 3      # the two Claude in Chrome prompts -> private/prompts/
python -m bbt ingest 3 reply.txt   # merge a pasted extension reply
python -m bbt week 3         # just the full-tables packet -> private/packets/2026_wk03.md + charts
python -m bbt run 3          # refresh + check paid extract + packet, timed
python -m bbt erased         # league table: points erased by penalties
python -m bbt opponent 4     # next opponent's tendencies, most unusual first
python -m bbt watchfor 4 --metric play_action --under 0.18 --text "ARI stays allergic to play action"
python -m bbt grade 4        # grade it after the game
python -m bbt notes 3        # check your Sunday notes against the data
python -m bbt notes 3 --source skinner   # same, for someone else's takes (backtesting)
python -m bbt eye            # season "my eye vs the data" score, per source
python -m bbt audit          # confirm nothing private is tracked (CI runs this too)
pytest -q
```

## Weekly rhythm

| When | You | The pipeline |
|---|---|---|
| Sunday night | Send your notes, any format | Checks every note against the data, writes the two browser prompts |
| Monday/Tuesday | Paste prompt 1 (Sūmer) and prompt 2 (NFL Pro) into Claude in Chrome, paste both replies back | Checks the paid data, fills in the open notes |
| Tuesday | Read the notes doc (`private/briefs/`) | One doc: your notes checked, what the data adds, film list, next week's watch-for |
| Wed/Thu | Write and publish | Grades the watch-for after the next game |

## What stays private

Paid data (SūmerPass, NFL Pro), raw page text, notes, verdicts, packets and charts all live in
`private/`, which is gitignored. So is the local database. `python -m bbt audit` fails if any of it
is ever tracked, and CI runs the audit on every push.

## Data & credit

- Play-by-play, schedules, snap counts: [nflverse](https://github.com/nflverse) via `nflreadpy`
- Charting: **FTN Data via nflverse**
- Paid sources (SūmerPass, NFL Pro) are used for analysis only and never republished here
