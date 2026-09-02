"""Quick live-data smoke test. Run: python self_test.py"""
from advanced import backtest_metrics
from investor import dcf_valuation
from reporting import table_pdf
from scanner import ScanSettings, scan_market

if __name__ == "__main__":
    settings = ScanSettings("Both", 0, 10, 1.0, 1, 25_000.0, 1.0, 3)
    results, skipped = scan_market(["AAPL", "MSFT", "NVDA"], settings, lambda *_: None)
    if results.empty:
        print("No live candidates returned. Yahoo data may be unavailable or all symbols were skipped.")
    else:
        print(results[["Symbol", "Score", "Signal", "Entry", "Stop"]].to_string(index=False))
    print(f"Skipped: {skipped}")
    assert dcf_valuation(1_000_000,100_000,200_000,.08,.025,.10)
    assert table_pdf("Self test",results.head(3) if not results.empty else __import__("pandas").DataFrame([{"Status":"No live candidates"}])).startswith(b"%PDF")
    print("V2 analytics and export smoke tests passed.")
