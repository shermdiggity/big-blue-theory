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


# Synthetic numbers only: this repo is public, real Sūmer values never go in it.
def _extract(**over):
    base = {
        "schema_version": "v1", "season": 2026, "week": 3, "game_id": "2026_03_TEN_NYG", "team": "NYG",
        "opponent": "TEN", "extracted_at": "2026-09-30T20:00:00",
        "sources": [{"source": "sumer", "page": "SumerLive > Week 3 > View Stats"}],
        "sumer": {
            "game_page": {
                "nyg": {
                    "tendencies": {"offensive_personnel": [{"label": "11", "pct": 60.0}, {"label": "12", "pct": 40.0}]},
                    "passing": {
                        "by_coverage": [{"label": "Cover 1", "share_pct": 40.0, "att": 8, "sacks": 1},
                                        {"label": "Cover 3", "share_pct": 60.0, "att": 12, "sacks": 1}],
                        "pressure": [{"label": "Pressured", "share_pct": 30.0, "att": 6, "sacks": 2},
                                     {"label": "Clean", "share_pct": 70.0, "att": 14, "sacks": 0}],
                    },
                },
                "opp": None,
            },
            "teams_offense": {"Plays": 50, "Pressure %": 31.5},
            "teams_defense": {"Blitz %": 22.2},
            "players": {"offensive_line": [{"Player": "A Guard", "Pressure": 2}]},
        },
        "missing_fields": ["sumer.game_page.opp"], "raw_text_file": "x",
    }
    base.update(over)
    return base


RAW = ("Personnel 11 60.0 12 40.0 Cover 1 40.0% 8 att 1 sack Cover 3 60.0% 12 att 1 "
       "Pressured 30.0% 6 2 Clean 70.0% 14 0 Plays 50 Pressure % 31.5 Blitz % 22.2 A Guard Pressure 2")
FREE = paid.FreeCounts(off_plays=50, pass_att=20, sacks_taken=2, rushes=28, opp_pass_att=30,
                       opp_rushes=20, sacks_made=1)


def test_clean_extract_passes():
    r = paid.check(_extract(), RAW, 3, "2026_03_TEN_NYG", FREE)
    assert r.ok, r.render()
    assert not r.warnings, r.render()


def test_unlisted_null_fails():
    r = paid.check(_extract(missing_fields=[]), RAW, 3, "2026_03_TEN_NYG", FREE)
    assert any("not listed in missing_fields" in e for e in r.errors)


def test_bad_distribution_fails():
    ex = _extract()
    ex["sumer"]["game_page"]["nyg"]["tendencies"]["offensive_personnel"][1]["pct"] = 20.0
    r = paid.check(ex, RAW, 3, "2026_03_TEN_NYG", FREE)
    assert any("sums to" in e for e in r.errors)


def test_share_not_matching_counts_warns():
    ex = _extract()
    ex["sumer"]["game_page"]["nyg"]["passing"]["pressure"][0]["att"] = 9  # 9/23 != 30%
    r = paid.check(ex, RAW + " 9", 3, "2026_03_TEN_NYG", FREE)
    assert any("att =" in w for w in r.warnings)
    assert any("disagree on total" in w for w in r.warnings)


def test_invented_number_warns():
    ex = _extract()
    ex["sumer"]["teams_defense"]["Blitz %"] = 88.0  # the impossible SūmerBrain number
    r = paid.check(ex, RAW, 3, "2026_03_TEN_NYG", FREE)
    assert any("not found in raw page text" in w for w in r.warnings)


def test_screenshot_values_skip_trace():
    ex = _extract(screenshot_fields=["sumer.teams_defense.Blitz %"])
    ex["sumer"]["teams_defense"]["Blitz %"] = 23.0
    r = paid.check(ex, RAW, 3, "2026_03_TEN_NYG", FREE)
    assert r.screenshot_numbers == 1 and not r.warnings, r.render()


def test_free_data_mismatch_warns():
    free = paid.FreeCounts(off_plays=58, pass_att=20, sacks_taken=3, rushes=28, opp_pass_att=30,
                           opp_rushes=20, sacks_made=1)
    r = paid.check(_extract(), RAW, 3, "2026_03_TEN_NYG", free)
    assert any("offensive plays" in w for w in r.warnings)
    assert any("sacks taken" in w for w in r.warnings)


def test_wrong_game_fails():
    r = paid.check(_extract(), RAW, 3, "2026_03_NYG_DAL", FREE)
    assert not r.ok
