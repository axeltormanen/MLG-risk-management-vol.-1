import time
import yfinance as yf
import pandas as pd


def fetch_prices_resilient(ticker: str) -> pd.Series:
    """Get a clean daily close series with at least 10 trading days, robust to Yahoo quirks."""
    # Try progressively longer periods
    periods = ["30d", "60d", "90d"]   # enough to always find 10 trading days
    tries = 3

    for period in periods:
        for attempt in range(tries):
            try:
                t = yf.Ticker(ticker)
                df = t.history(period=period, interval="1d",
                               auto_adjust=True, actions=False, threads=False)
                # Prefer auto_adjusted Close; fall back if needed
                if "Close" in df and not df["Close"].empty:
                    s = df["Close"].copy()
                else:
                    # Fallback path for rare cases
                    raw = yf.download(ticker, period=period,
                                      interval="1d", threads=False)
                    if "Adj Close" in raw and not raw["Adj Close"].empty:
                        s = raw["Adj Close"].copy()
                    else:
                        s = raw.get("Close", pd.Series(dtype="float64"))

                # Clean
                s = s.dropna()
                if len(s) >= 12:  # leave some headroom for pct_change().dropna()
                    return s
            except Exception:
                time.sleep(0.8)  # brief backoff and try again
                continue
        # Next (longer) period

    # Nothing good enough
    return pd.Series(dtype="float64")


# --- use it like this inside your button handler ---
prices = fetch_prices_resilient(ticker_symbol)

if prices.empty or len(prices) < 12:
    st.error("Not enough historical data available (need at least 10 trading days).")
else:
    # Use the LAST 10 TRADING DAYS
    last_10 = prices.tail(10)
    rets = last_10.pct_change().dropna()
    if rets.empty:
        st.error("Could not compute returns from recent data.")
    else:
        avg_move = (rets.abs().mean()) * 100  # %
        # ... continue with your sizing math and outputs ...
