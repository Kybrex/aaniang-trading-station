"""Small local CSV persistence for watchlists, alerts, and journal entries."""
from __future__ import annotations
from pathlib import Path
import re
import pandas as pd

DATA_DIR = Path(__file__).parent / "user_data"
WATCHLIST = DATA_DIR / "watchlist.csv"
JOURNAL = DATA_DIR / "journal.csv"
POSITIONS = DATA_DIR / "positions.csv"
EVENTS = DATA_DIR / "events.csv"
ALERT_STATE = DATA_DIR / "alert_state.csv"

def _read(path: Path, columns: list[str]) -> pd.DataFrame:
    DATA_DIR.mkdir(exist_ok=True)
    try: return pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError): return pd.DataFrame(columns=columns)

def _append(path: Path, row: dict, columns: list[str]) -> None:
    df = _read(path, columns); pd.concat([df, pd.DataFrame([row])], ignore_index=True).to_csv(path, index=False)

def watchlist() -> pd.DataFrame: return _read(WATCHLIST, ["Symbol", "Signal", "Entry", "Stop", "Target 1", "Target 2", "Alert"])
def save_watchlist(frame: pd.DataFrame) -> None:
    """Validate and replace the complete watchlist after an editor save."""
    columns = ["Symbol", "Signal", "Entry", "Stop", "Target 1", "Target 2", "Alert"]
    cleaned = frame.copy()
    for column in columns:
        if column not in cleaned: cleaned[column] = "" if column in ["Symbol", "Signal", "Alert"] else 0.0
    cleaned["Symbol"] = cleaned["Symbol"].fillna("").astype(str).str.strip().str.upper()
    cleaned["Signal"] = cleaned["Signal"].fillna("").astype(str).str.strip().str.upper()
    cleaned["Alert"] = cleaned["Alert"].fillna("").astype(str).str.strip()
    for column in ["Entry", "Stop", "Target 1", "Target 2"]:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce").fillna(0.0)
    cleaned = cleaned[cleaned["Symbol"] != ""].drop_duplicates("Symbol", keep="last")
    DATA_DIR.mkdir(exist_ok=True); cleaned[columns].to_csv(WATCHLIST, index=False)

def add_watch(row: dict) -> None:
    current = watchlist(); current = current[current.Symbol != row["Symbol"]] if not current.empty else current
    save_watchlist(pd.concat([current, pd.DataFrame([row])], ignore_index=True))
def journal() -> pd.DataFrame: return _read(JOURNAL, ["Date", "Symbol", "Side", "Entry", "Exit", "Shares", "Notes"])
def add_journal(row: dict) -> None: _append(JOURNAL, row, ["Date", "Symbol", "Side", "Entry", "Exit", "Shares", "Notes"])

def positions() -> pd.DataFrame:
    columns=["Symbol","Shares","Cost","Stop","Sector","Country","Currency","Purpose","Dividend Yield","Target Weight"]
    frame=_read(POSITIONS,columns)
    for column in columns:
        if column not in frame:frame[column]="" if column in ["Symbol","Sector","Country","Currency","Purpose"] else 0
    return frame[columns]

def save_positions(frame: pd.DataFrame) -> None:
    DATA_DIR.mkdir(exist_ok=True); frame.to_csv(POSITIONS,index=False)

def add_position(row: dict) -> None:
    current=positions(); key=(current.Symbol.astype(str)==str(row["Symbol"])) & (current.Purpose.astype(str)==str(row["Purpose"])) if not current.empty else pd.Series(dtype=bool)
    if not current.empty: current=current.loc[~key]
    save_positions(pd.concat([current,pd.DataFrame([row])],ignore_index=True))

def events() -> pd.DataFrame:
    return _read(EVENTS,["Date","Type","Symbol","Event","Notes"])

def add_event(row: dict) -> None:
    _append(EVENTS,row,["Date","Type","Symbol","Event","Notes"])

def save_attachment(filename: str, content: bytes) -> str:
    folder=DATA_DIR/"screenshots";folder.mkdir(parents=True,exist_ok=True)
    safe=re.sub(r"[^A-Za-z0-9_.-]","_",Path(filename).name);target=folder/safe;target.write_bytes(content);return str(target.relative_to(DATA_DIR))

def newly_triggered(evaluated: pd.DataFrame) -> pd.DataFrame:
    """Return only Waiting->TRIGGERED transitions and persist the latest state."""
    if evaluated.empty:return evaluated
    previous=_read(ALERT_STATE,["Symbol","Alert","Status"]);old={(str(row.Symbol),str(row.Alert)):str(row.Status) for _,row in previous.iterrows()}
    mask=[str(row.Status)=="TRIGGERED" and old.get((str(row.Symbol),str(row.Alert)))!="TRIGGERED" for _,row in evaluated.iterrows()]
    evaluated[["Symbol","Alert","Status"]].to_csv(ALERT_STATE,index=False)
    return evaluated.loc[mask].reset_index(drop=True)
