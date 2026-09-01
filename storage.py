"""Small local CSV persistence for watchlists, alerts, and journal entries."""
from __future__ import annotations
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).parent / "user_data"
WATCHLIST = DATA_DIR / "watchlist.csv"
JOURNAL = DATA_DIR / "journal.csv"

def _read(path: Path, columns: list[str]) -> pd.DataFrame:
    DATA_DIR.mkdir(exist_ok=True)
    try: return pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError): return pd.DataFrame(columns=columns)

def _append(path: Path, row: dict, columns: list[str]) -> None:
    df = _read(path, columns); pd.concat([df, pd.DataFrame([row])], ignore_index=True).to_csv(path, index=False)

def watchlist() -> pd.DataFrame: return _read(WATCHLIST, ["Symbol", "Signal", "Entry", "Stop", "Target 1", "Target 2", "Alert"])
def add_watch(row: dict) -> None:
    current = watchlist(); current = current[current.Symbol != row["Symbol"]] if not current.empty else current
    pd.concat([current, pd.DataFrame([row])], ignore_index=True).to_csv(WATCHLIST, index=False)
def journal() -> pd.DataFrame: return _read(JOURNAL, ["Date", "Symbol", "Side", "Entry", "Exit", "Shares", "Notes"])
def add_journal(row: dict) -> None: _append(JOURNAL, row, ["Date", "Symbol", "Side", "Entry", "Exit", "Shares", "Notes"])
