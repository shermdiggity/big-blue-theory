# private/

Everything in this folder except this README is gitignored. Nothing here gets pushed.

```
private/
  paid/       2026_wk03.json         browser-agent extract (Sūmer + NFL Pro), validated by `bbt check`
              2026_wk03_raw.txt      raw page text the agent copied the numbers from
  notes/      2026_wk03.md           your Sunday notes, one claim per line
              2026_wk03_verdicts.csv claims with evidence and verdicts
  packets/    2026_wk03.md           the weekly game packet
  charts/     2026_wk03_*.png        charts (copy the ones you publish into the post)
```

Paid data never leaves this folder. Run `python -m bbt audit` before every push. It fails if
any tracked file looks like paid data or a secret.
