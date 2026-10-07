# Charts

Every chart is a 1600 × 900 PNG card (taller when it has many rows) in one house style:
navy rule, a plain title that says what the chart shows, a subtitle
with the sample or caveat, the plot, and a footer with the source. No watermark. Fonts are Barlow / Barlow
Condensed (SIL Open Font License, bundled in `bbt/fonts/`). Colors were checked with a palette
validator: Giants blue `#2a78d6` is the accent, orange `#eb6834` the second series, gray for
everything de-emphasised, red `#e34948` for the bad side of a diverging chart.

## What a chart is for

A chart earns its place by showing **why or how**, not by restating a number that's already in
the notes. Put the cause next to the effect (Brian Burns' snaps falling next to the blitz rate
rising), put one game against a player's history (every Winston game 2024–26, not just this one),
or show where something happened (runs by direction over the linemen who were graded poorly).
Keep words to a minimum: a plain title, at most one short subtitle line, labels only where needed.

## Two kinds of charts

**Every week, automatically (free data):** win probability, gameplan vs usual vs league, every
drive, the flags, points erased league-wide. `bbt week N` / `bbt brief N` draw them.

**Story charts (one per point worth making):** the session writes
`private/notes/<tag>_charts.json` while checking the notes, then `bbt charts N` draws them
(`bbt brief N` does too, and puts each one under the note it backs up).

```json
{"charts": [
  {"id": "pass_rush", "kind": "bars", "orientation": "v", "claim": "Player A: stud",
   "title": "Player A: pass-rush win rate by week", "subtitle": "Pressures above each bar",
   "source": "Sūmer charting via SūmerBrain", "fmt": "{:.0f}%", "highlight": ["Wk 3"],
   "rows": [{"label": "Wk 1", "value": 12, "note": "2 pressures"},
            {"label": "Wk 2", "value": 10, "note": "1 pressure"},
            {"label": "Wk 3", "value": 30, "note": "7 pressures"}]}
]}
```

(Numbers above are made up. Real paid numbers only ever go in `private/`.)

Common fields: `id` (file name), `kind`, `title` (what the chart shows: "Abdul Carter: pass-rush win rate by week", no spin), `subtitle`
(what's measured, sample, caveat), `source` (say SūmerBrain when it's SūmerBrain), `claim`
(start of `who: what` to place it under that note), optional `height`, `kicker`.

| kind | use it for | data |
|---|---|---|
| `bars` | one measure across a few things; highlight the one that matters | `rows: [{label, value, note?}]`, `highlight`, `fmt`, `orientation` `h`/`v`, `ref: {value, label}` |
| `trend` | a measure by week; the highlighted week gets a band | `x`, `series: [{name, values, muted?}]`, `highlight_x`, `ylim`, `yticks` |
| `grouped` | two series side by side per group (man vs zone by season) | `groups`, `series: [{name, values}]`, `notes: {group: text}`, `highlight` |
| `split` | shares that add to 100% per row (man/zone mix by opponent) | `parts`, `rows: [{label, values, note?}]`, `note_header`, `highlight` |
| `diverging` | good vs bad around zero (EPA by concept) | `rows: [{label, value, note?}]`, `poles: [neg, pos]` |
| `dumbbell` | this game vs usual vs league, same scale | `rows: [{label, a, b, ref}]`, `names: [a, b, ref]`, `xlim`, `xticks` |
| `panels` | two or three measures with different scales (never a dual axis) | `panels: [{title, fmt, rows, highlight}]` |
| `tiles` | a few headline numbers | `tiles: [{value, label, context, highlight?}]` |
| `slopes` | cause next to effect over weeks/seasons, one measure per panel | `x`, `panels: [{title, fmt, values \| series \| ranges, ref, ylim}]`, `highlight_x`, `event: {at, label}` |
| `stack` | one game against a player's history (sacks on the QB vs not, per game) | `x`, `parts`, `values: [[...] per part]`, `highlight`, `groups: [{label, from, to}]` |
| `pairs` | actual vs expected per game (YAC vs xYAC) | `x`, `actual`, `expected`, `highlight`, `groups`, `names` |
| `gapmap` | where runs went, over the line, with per-lineman flags | `linemen: [{pos, name, flags}]`, `runs: [{at, n, epa}]`, `flag_label` |

Rules the code already follows (don't fight them): one accent per chart and gray for the rest;
values labeled directly, so there's no value axis on bar charts; a legend whenever there are two or
more series; text in ink colors, never the series color; rounded data-ends; no dual axes.
