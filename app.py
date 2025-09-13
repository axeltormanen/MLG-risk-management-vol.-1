import datetime as dt
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

# --- optional fallback if Investing.com fails
import yfinance as yf

# Investing.com via investpy
# investpy often needs dd/mm/yyyy dates and a symbol + country lookup
try:
    import investpy
    HAS_INVESTPY = True
except Exception:
    HAS_INVESTPY = False


# --------------------------
# Data fetchers
# --------------------------
def fetch_prices_investing(
    ticker: str,
    country: str = "united states",
    lookback_days: int = 365,
) -> Optional[pd.Series]:
    """
    Try to resolve a stock on Investing.com and fetch daily Close prices.
    Returns a pandas Series indexed by datetime, or None if anything fails.
    """
    if not HAS_INVESTPY:
        return None

    try:
        # investpy needs a search; take the first US stock match
        results = investpy.search_quotes(
            text=ticker,
            products=["stocks"],
            countries=[country],
        )
        if not results:
            return None

        # pick the best match (first)
        q = results[0]

        # date range must be dd/mm/yyyy
        end = dt.date.today()
        start = end - dt.timedelta(days=lookback_days)
        df = q.retrieve_historical_data(
            from_date=start.strftime("%d/%m/%Y"),
            to_date=end.strftime("%d/%m/%Y"),
        )

        # Expect columns: Open High Low Close Volume; index is Date
        if df is None or df.empty or "Close" not in df.columns:
            return None

        s = df["Close"].copy()
        s.index = pd.to_datetime(s.index)
        s = s.sort_index()
        return s
    except Exception:
        # Any error (network, Cloudflare, format) -> return None
        return None


def fetch_prices_yf(ticker: str, period: str = "2y") -> Optional[pd.Series]:
    """
    Yahoo fallback: Adj Close series, sorted ascending.
    """
    try:
        data = yf.download(ticker, period=period,
                           auto_adjust=False, progress=False)
        if data is None or data.empty:
            return None
        if "Adj Close" in data.columns:
            s = data["Adj Close"].copy()
        else:
            s = data["Close"].copy()
        s.index = pd.to_datetime(s.index)
        s = s.sort_index()
        return s
    except Exception:
        return None


def fetch_prices_resilient(
    ticker: str, country: str = "united states", lookback_days: int = 365
) -> Tuple[Optional[pd.Series], str]:
    """
    Try Investing.com first, then Yahoo. Return (series, source_used).
    """
    s = fetch_prices_investing(
        ticker, country=country, lookback_days=lookback_days)
    if s is not None and len(s) >= 12:
        return s, "Investing.com"

    s = fetch_prices_yf(ticker)
    if s is not None and len(s) >= 12:
        return s, "Yahoo Finance"

    return None, "None"


# --------------------------
# Calculations
# --------------------------
def avg_abs_move_pct(closes: pd.Series, window: int = 10) -> Optional[float]:
    """
    10-day average absolute daily % move.
    Needs at least window+1 closes (i.e., 11).
    """
    if closes is None or len(closes) < window + 1:
        return None
    recent = closes.tail(window + 1).pct_change().dropna() * 100.0
    return float(recent.abs().mean())


def position_pct_from_rule(
    avg_move_pct: float,
    general_vol: int,
    company_vol: int,
    base_pct: float = 30.0,
    per_step_reduce: float = 1.5,
    step_pct: float = 0.10,
    vol_penalty_per_point: float = 3.0,
) -> Tuple[float, float, float]:
    """
    Rule:
      - Start at 30% of portfolio
      - For every 0.10% of the 10-day average absolute move, reduce by 1.5%
      - Apply sliders: each point (0..5) reduces an additional 3%
      - Floor at 0%, then clamp [0, 100]
    Returns: (final_pct, reduction_from_move, reduction_from_sliders)
    """
    # reduction due to 10-day average absolute move
    reduction_from_move = per_step_reduce * (avg_move_pct / step_pct)

    # sliders total penalty
    reduction_from_sliders = vol_penalty_per_point * \
        (general_vol + company_vol)

    final_pct = base_pct - reduction_from_move - reduction_from_sliders
    final_pct = max(0.0, min(100.0, final_pct))
    return final_pct, reduction_from_move, reduction_from_sliders


# --------------------------
# Streamlit UI
# --------------------------
st.set_page_config(page_title="Stock Position Sizer App",
                   page_icon="📊", layout="centered")
st.title("📊 Stock Position Sizer App")

with st.expander("How this works", expanded=False):
    st.write(
        """
**Sizing rule:**
- Start at **30%** of portfolio  
- For **every 0.10%** of the 10-day **average absolute daily move**, **reduce by 1.5%**  
- Apply the sliders (0–5): each point reduces the position by **3%**  
- Final position is floored at **0%**  
        """
    )
    st.caption(
        "The app first tries **Investing.com** (via `investpy`). If that fails (e.g., blocked on Streamlit Cloud), it "
        "falls back to **Yahoo Finance** automatically."
    )

colA, colB = st.columns([1.2, 1])
ticker_symbol = colA.text_input("Ticker Symbol (e.g., MSFT)", value="MSFT")
portfolio_size = colB.number_input(
    "Portfolio Size (€)", min_value=0.0, value=5000.0, step=100.0, format="%.2f")

# Integer sliders 0..5 only
general_vol = st.slider("Expected General Volatility (0–5)",
                        min_value=0, max_value=5, value=2, step=1)
company_vol = st.slider("Expected Company Volatility (0–5)",
                        min_value=0, max_value=5, value=2, step=1)

if st.button("Calculate Position Size"):
    st.write(f"Pulling price data for **{ticker_symbol}**…")

    prices, used_source = fetch_prices_resilient(ticker_symbol.strip().upper())
    if prices is None or len(prices) < 11:
        st.error("Not enough historical data available (need at least 11 closes).")
        st.caption(
            "Tip: For US stocks, try the plain ticker (e.g., AAPL, MSFT). If Investing.com is blocked, the app will try Yahoo automatically. "
            "If a regional suffix is needed on Yahoo (e.g., `.L`, `.MX`), include it."
        )
    else:
        avg_move = avg_abs_move_pct(prices, window=10)
        if avg_move is None:
            st.error("Could not compute 10-day average absolute move.")
        else:
            final_pct, red_move, red_sliders = position_pct_from_rule(
                avg_move_pct=avg_move,
                general_vol=general_vol,
                company_vol=company_vol,
            )

            st.success(
                f"**Source:** {used_source}  \n"
                f"**10-day average absolute move:** {avg_move:.2f}%  \n"
                f"**Position size:** **{final_pct:.2f}%** of portfolio  \n"
            )

            # Convert to currency
            pos_eur = portfolio_size * (final_pct / 100.0)
            st.write(f"**Position €:** {pos_eur:,.2f}")

            with st.expander("Calculation details"):
                st.write(
                    f"- Base: 30.00%  \n"
                    f"- Reduction from average move: −{red_move:.2f}%  \n"
                    f"- Reduction from sliders (3% × (general + company)): −{red_sliders:.2f}%  \n"
                    f"- **Final:** {final_pct:.2f}%"
                )

st.caption(
    "Note: If you consistently see data errors on Streamlit Cloud, it’s likely Investing.com is blocked. "
    "The app already falls back to Yahoo; if your ticker needs a suffix on Yahoo (e.g., `VOD.L`), please include it."
)
