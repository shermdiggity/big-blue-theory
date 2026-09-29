"""Penalty classification and erased-play parsing, on real play text from 2026."""

import polars as pl
import pytest

from bbt.penalties import classify, ledger, parse_erased, pre_penalty_text

HOLDING_RUN = ("(13:33) 44-C.Skattebo left end to TEN 16 for 11 yards (18-C.Flott; 33-C.Gray). "
               "PENALTY on NYG-61-J.Schmitz, Offensive Holding, 10 yards, enforced at TEN 27 - No Play.")
FALSE_START = "(12:21) (Shotgun) PENALTY on NYG-76-J.Runyan, False Start, 5 yards, enforced at TEN 43 - No Play."
DELAY = "(3:12) (Run formation) PENALTY on NYG, Delay of Game, 5 yards, enforced at TEN 41 - No Play."
OFFSIDE_SACK = ("(15:00) (Shotgun) 19-J.Winston sacked at NYG 13 for -7 yards (sack split by 91-J.Franklin-Myers "
                "and 53-A.Hill). PENALTY on TEN-57-J.Martin, Defensive Offside, 5 yards, enforced at NYG 20 - No Play.")
TD_NULLIFIED = ("(13:00) 8-L.Jackson pass short right to 6-J.Lane for 4 yards, TOUCHDOWN NULLIFIED by Penalty. "
                "PENALTY on BAL-54-J.Gwyn, Offensive Holding, 10 yards, enforced at IND 4 - No Play.")
ADDED = ("6-J.Slye kicks 65 yards from TEN 35 to NYG 0. 87-B.Berrios pushed ob at NYG 27 for 27 yards "
         "(29-T.Adams). PENALTY on TEN-52-J.Williams, Face Mask, 15 yards, enforced at NYG 27.")
ELIGIBLE = ("(:50) (Run formation) 79-L.Borom reported in as eligible. PENALTY on CHI-79-L.Borom, "
            "False Start, 5 yards, enforced at CHI 30 - No Play.")
INT_WIPED = ("(4:00) 4-D.Prescott pass deep right intended for 19-R.Flournoy INTERCEPTED by 24-X.Y at DAL 40. "
             "PENALTY on NYG-24-X.Y, Defensive Holding, 5 yards, enforced at DAL 25 - No Play.")
OFFSETTING = ("(8:18) (No Huddle) 38-J.McLaughlin left tackle to CLE 46 for 2 yards (56-R.Nunez-Roches). "
              "Penalty on CLE-77-Z.Johnson, Offensive Holding, offsetting, enforced at CLE 44 - No Play. "
              "Penalty on TB, Defensive Too Many Men on Field, offsetting.")


@pytest.mark.parametrize("desc,play_type,kind", [
    (HOLDING_RUN, "no_play", "wiped"),
    (FALSE_START, "no_play", "pre_snap"),
    (DELAY, "no_play", "pre_snap"),
    (OFFSIDE_SACK, "no_play", "wiped"),   # a play happened, then got erased
    (TD_NULLIFIED, "no_play", "wiped"),
    (ADDED, "kickoff", "added"),
    (ELIGIBLE, "no_play", "pre_snap"),    # "reported in as eligible" isn't a play
    (OFFSETTING, "no_play", "offsetting"),
])
def test_classify(desc, play_type, kind):
    assert classify(desc, play_type) == kind


def test_pre_text_strips_clock_and_formation():
    assert pre_penalty_text(FALSE_START) == ""
    assert pre_penalty_text(HOLDING_RUN).startswith("44-C.Skattebo left end")


def test_parse_run_gain():
    p = parse_erased(pre_penalty_text(HOLDING_RUN))
    assert p["erased_kind"] == "run" and p["erased_gain"] == 11 and not p["erased_td"]


def test_parse_sack():
    p = parse_erased(pre_penalty_text(OFFSIDE_SACK))
    assert p["erased_kind"] == "pass" and p["erased_gain"] == -7 and p["erased_sack"]


def test_parse_td():
    p = parse_erased(pre_penalty_text(TD_NULLIFIED))
    assert p["erased_td"] and p["erased_gain"] == 4


def test_parse_interception():
    p = parse_erased(pre_penalty_text(INT_WIPED))
    assert p["erased_int"] and p["erased_kind"] == "pass"


def test_ledger_credits_wpa_only_for_pre_snap_and_wiped():
    df = pl.DataFrame({
        "game_id": ["g"] * 3, "week": [3] * 3, "play_id": [1.0, 2.0, 3.0], "qtr": [1.0] * 3,
        "time": ["10:00"] * 3, "posteam": ["NYG"] * 3, "defteam": ["TEN"] * 3, "down": [1.0] * 3,
        "ydstogo": [10.0] * 3, "yardline_100": [60.0] * 3, "penalty": [1.0] * 3,
        "penalty_team": ["NYG", "NYG", "TEN"], "penalty_player_name": ["a", "b", "c"],
        "penalty_type": ["Offensive Holding", "False Start", "Face Mask"], "penalty_yards": [10.0, 5.0, 15.0],
        "desc": [HOLDING_RUN, FALSE_START, ADDED], "play_type": ["no_play", "no_play", "kickoff"],
        "ep": [2.0] * 3, "epa": [-1.0, -0.5, 1.0], "wpa": [-0.02, -0.01, 0.03],
    })
    led = ledger(df).sort("play_id")
    assert led["kind"].to_list() == ["wiped", "pre_snap", "added"]
    assert led["wpa_to_penalized"].to_list()[:2] == [-0.02, -0.01]
    assert led["wpa_to_penalized"][2] is None
    # defense penalty: the flag's value is flipped to the defense's view
    assert led["pen_side"].to_list() == ["offense", "offense", "defense"]
