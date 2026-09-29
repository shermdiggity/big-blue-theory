import pytest

from bbt import notes, paid


def test_parse_notes():
    text = """# comment
Nabers | open deep all game, Winston never looked | deep targets, separation, read thrown
OL | lost on 3rd down | sacks; pressure
Daboll | too conservative | 4th downs
Winston | fine | epa | scheme
"""
    claims = notes.parse(text)
    assert [c.who for c in claims] == ["Nabers", "OL", "Daboll", "Winston"]
    assert claims[0].evidence == ["deep targets", "separation", "read thrown"]
    assert [c.kind for c in claims] == ["players", "scheme", "decisions", "scheme"]


def test_parse_notes_rejects_bad_line():
    with pytest.raises(SystemExit):
        notes.parse("just a sentence with no pipes")


def _extract(**over):
    base = {
        "schema_version": "v0", "season": 2026, "week": 3, "game_id": "2026_03_TEN_NYG", "team": "NYG",
        "extracted_at": "2026-09-29T10:00:00", "sources": [{"source": "sumer", "page": "Team > Personnel"}],
        "sumer": {"offense": {"snaps": 64, "personnel": [
            {"label": "11", "count": 40, "pct": 62.5}, {"label": "12", "count": 24, "pct": 37.5}]},
            "defense": {"snaps": 60, "blitz_rate": 25.0}, "players": []},
        "nfl_pro": {"run_scheme": None},
        "missing_fields": ["nfl_pro.run_scheme"], "raw_text_file": "x",
    }
    base.update(over)
    return base


RAW = "Personnel 11 40 62.5% 12 24 37.5% Snaps 64 Defense snaps 60 Blitz 25.0%"


def test_clean_extract_passes():
    r = paid.check(_extract(), RAW, 3, "2026_03_TEN_NYG", 64, 60)
    assert r.ok, r.render()
    assert not r.warnings, r.render()


def test_unlisted_null_fails():
    r = paid.check(_extract(missing_fields=[]), RAW, 3, "2026_03_TEN_NYG", 64, 60)
    assert any("not listed in missing_fields" in e for e in r.errors)


def test_bad_distribution_fails():
    ex = _extract()
    ex["sumer"]["offense"]["personnel"][1]["pct"] = 20.0
    r = paid.check(ex, RAW, 3, "2026_03_TEN_NYG", 64, 60)
    assert any("sum to" in e for e in r.errors)


def test_invented_number_warns():
    ex = _extract()
    ex["sumer"]["defense"]["blitz_rate"] = 88.0  # the impossible SūmerBrain number
    r = paid.check(ex, RAW, 3, "2026_03_TEN_NYG", 64, 60)
    assert any("not found in raw page text" in w for w in r.warnings)


def test_snap_mismatch_warns():
    r = paid.check(_extract(), RAW, 3, "2026_03_TEN_NYG", 50, 60)
    assert any("free play-by-play" in w for w in r.warnings)


def test_wrong_game_fails():
    r = paid.check(_extract(), RAW, 3, "2026_03_NYG_DAL", 64, 60)
    assert not r.ok
