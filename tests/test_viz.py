"""Every chart kind renders from a spec. Synthetic numbers only: this repo is public."""

import json

import pytest

from bbt import viz

SPECS = [
    {"id": "b", "kind": "bars", "title": "A headline", "subtitle": "What's measured", "fmt": "{:.0f}%",
     "highlight": ["C"], "rows": [{"label": "A", "value": 10}, {"label": "B", "value": 20, "note": "n=4"},
                                  {"label": "C", "value": 40}]},
    {"id": "bv", "kind": "bars", "orientation": "v", "title": "Columns", "fmt": "{:.1f}",
     "ref": {"value": 15, "label": "League"},
     "rows": [{"label": "Wk 1", "value": 12.0}, {"label": "Wk 2", "value": -3.0, "note": "x"}]},
    {"id": "t", "kind": "trend", "title": "Trend", "x": ["W1", "W2", "W3"], "highlight_x": "W3",
     "series": [{"name": "One", "values": [1, 2, 3]}, {"name": "Two", "values": [3, None, 2.9]}]},
    {"id": "g", "kind": "grouped", "title": "Grouped", "groups": ["2024", "2025"], "notes": {"2024": "n=9"},
     "series": [{"name": "Man", "values": [5, 6]}, {"name": "Zone", "values": [4, 7]}]},
    {"id": "s", "kind": "split", "title": "Split", "parts": ["Man", "Zone"], "highlight": ["vs B"],
     "note_header": "t-c-y", "rows": [{"label": "vs A", "values": [1, 9], "note": "1-1-1"},
                                       {"label": "vs B", "values": [5, 5]}]},
    {"id": "d", "kind": "diverging", "title": "Diverging", "rows": [{"label": "A", "value": 0.2, "note": "3 runs"},
                                                                    {"label": "B", "value": -0.5}]},
    {"id": "db", "kind": "dumbbell", "title": "Dumbbell", "rows": [{"label": "Rate", "a": 30, "b": 50, "ref": 40},
                                                                   {"label": "Other", "a": None, "b": 10}]},
    {"id": "p", "kind": "panels", "title": "Panels",
     "panels": [{"title": "One", "rows": [{"label": "A", "value": 1.5}, {"label": "B", "value": 2.5}]},
                {"title": "Two", "fmt": "{:+.2f}", "rows": [{"label": "A", "value": -0.1}, {"label": "B", "value": -0.3}]}]},
    {"id": "ti", "kind": "tiles", "title": "Tiles",
     "tiles": [{"value": "12%", "label": "a rate", "context": "up from 6%", "highlight": True},
               {"value": "−0.10", "label": "an EPA", "context": ""}]},
]


@pytest.mark.parametrize("spec", SPECS, ids=[s["id"] for s in SPECS])
def test_every_kind_renders(spec, tmp_path):
    p = viz.render(spec, tmp_path / f"{spec['id']}.png", kicker="Week 1 · AAA vs BBB")
    assert p.exists() and p.stat().st_size > 10_000
    assert p.read_bytes()[:4] == b"\x89PNG"


def test_unknown_kind_is_refused(tmp_path):
    with pytest.raises(ValueError, match="unknown kind"):
        viz.render({"id": "x", "kind": "pie", "title": "no"}, tmp_path / "x.png")


def test_render_week_reads_the_spec_file(tmp_path, monkeypatch):
    from bbt import config
    monkeypatch.setattr(config, "NOTES_DIR", tmp_path)
    monkeypatch.setattr(config, "CHARTS_DIR", tmp_path / "charts")
    (tmp_path / "2026_wk04_charts.json").write_text(json.dumps({"charts": SPECS[:2]}))
    out = viz.render_week(4)
    assert [p.name for _, p in out] == ["2026_wk04_b.png", "2026_wk04_bv.png"]
    assert viz.load_specs(5) == []


def test_wrap_breaks_long_titles():
    card = viz.Card("t")
    lines = card.wrap("word " * 40, 3.0, size=21, weight="bold", head=True)
    assert len(lines) > 2 and all(card.measure(l, 21, "bold", True)[0] <= 3.0 for l in lines)
    viz.plt.close(card.fig)
