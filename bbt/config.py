"""Project-wide settings and paths."""

from pathlib import Path

TEAM = "NYG"
SEASON = 2026

# Extra seasons loaded only as a baseline: comparable plays for "points erased"
# and league 4th-down go rates. Three weeks of 2026 alone is too thin a sample.
BASELINE_SEASONS = [2024, 2025]

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "bbt.duckdb"

PRIVATE_DIR = ROOT / "private"
PAID_DIR = PRIVATE_DIR / "paid"
NOTES_DIR = PRIVATE_DIR / "notes"
PACKETS_DIR = PRIVATE_DIR / "packets"
CHARTS_DIR = PRIVATE_DIR / "charts"

SCORECARD_PATH = ROOT / "scorecard.csv"

FTN_CREDIT = "FTN Data via nflverse"


def week_tag(week: int, season: int = SEASON) -> str:
    return f"{season}_wk{week:02d}"
