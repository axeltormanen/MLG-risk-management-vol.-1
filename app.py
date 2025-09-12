# app.py
import time
import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st

# ---------- Robust price fetch ----------


def fetch_prices_resilient(ticker: str) -> pd.Series:
    periods = ["30d", "60d", "90d"]      # try progressively longer windows
    tries = 3
    for period in periods:
        for _ in range(tries):
            try:
                t = yf.Ticker(ticker)
                df = t.history(period=period, interval="1d",
                               auto_adjust=True, actions=False, threads=False)
                if "Close" in df and not df["Close"].empty:
                    s = df["Close"].dropna()
                else:
                    raw = yf.download(ticker, period=period,
                                      interval="1d", threads=False)
                    s = (raw.get("Adj Close") or raw.get("Close")
                         or pd.Series(dtype="float64")).dropna()
                if len(s) >= 12:         # enough to compute 10d returns
                    return s
            except Exception:
                time.sleep(0.8)
                continue
    return pd.Series(dtype="float64")

# 10-day average absolute daily move (%)


def ten_day_avg_abs_move(prices: pd.Series) -> float:
    last_10 = prices.tail(10)
    rets = last_10.pct_change().dropna()
    if rets.empty:
        return np.nan
    return float(rets.abs().mean() * 100.0)

# All-time beta vs QQQ (daily)


def all_time_beta(ticker: str, index: str = "QQQ") -> float:
    # fetch full histories (max) and align
    s = yf.download(ticker, period="max", interval="1d",
                    auto_adjust=True, threads=False)["Close"].dropna()
    m = yf.download(index,  period="max", interval="1d",
                    auto_adjust=True, threads=False)["Close"].dropna()
    df = pd.concat([s.pct_change(), m.pct_change()], axis=1).dropna()
    if df.shape[0] < 50:
        return np.nan
    cov = np.cov(df.iloc[:, 0], df.iloc[:, 1])[0, 1]
    var_m = np.var(df.iloc[:, 1])
    return float(cov / var_m) if var_m != 0 else np.nan


# ---------- UI ----------
st.set_page_config(page_title="Position Sizer", layout="centered")
st.title("📈 Stock Position Sizer App")

col1, col2 = st.columns([2, 1])
with col1:
    ticker_symbol = st.text_input(
        "Ticker Symbol (e.g., TSLA)", value="MSFT").strip().upper()
with col2:
    portfolio_eur = st.number_input(
        "Portfolio Size (€)", min_value=0.0, value=5000.0, step=100.0, format="%.2f")

method = st.selectbox(
    "Volatility method",
    ["10-day average absolute move (%)",
     "All-time beta vs QQQ (excess over 1.0)"],
    index=0
)

general_vol = st.slider("Expected General Volatility (0–5)", 0, 5, 0)
company_vol = st.slider("Expected Company Volatility (0–5)", 0, 5, 0)

if st.button("Calculate Position Size"):
    if not ticker_symbol:
        st.error("Please enter a ticker.")
        st.stop()

    st.info(f"Pulling price data for **{ticker_symbol}**…")
    prices = fetch_prices_resilient(ticker_symbol)

    if prices.empty or len(prices) < 12:
        st.error(
            "Not enough historical data available (need at least 10 trading days).")
        st.caption(
            "Tip: use the proper exchange suffix (e.g., SHOP.TO, AIR.PA, INFY.NS) or try another symbol.")
        st.stop()

    # --- compute driving metric
    logs = []
    if method.startswith("10-day"):
        avg_move_pct = ten_day_avg_abs_move(prices)  # % per day
        if np.isnan(avg_move_pct):
            st.error("Could not compute 10-day average move.")
            st.stop()
        vol_metric = avg_move_pct
        logs.append(f"10-day average absolute move: **{avg_move_pct:.2f}%**")
    else:
        beta = all_time_beta(ticker_symbol, "QQQ")
        if np.isnan(beta):
            st.error("Could not compute all-time beta.")
            st.stop()
        excess_beta = max(0.0, beta - 1.0)
        # Use the same 0.10 “step” rule but on **excess beta** (keeps result reasonable)
        vol_metric = excess_beta  # in beta units
        logs.append(
            f"All-time beta vs QQQ: **{beta:.2f}** (excess over 1.0 = {excess_beta:.2f})")

    # --- sizing rule
    base_pct = 30.0  # start at 30% of portfolio

    if method.startswith("10-day"):
        # per your spec: every 0.10% avg move reduces by 1.5%
        reduction_from_metric = 1.5 * (vol_metric / 0.10)
    else:
        # alternate: every 0.10 of **excess beta** reduces by 1.5%
        reduction_from_metric = 1.5 * (vol_metric / 0.10)

    # news adjustments: each point 0–5 subtracts 3%
    news_adjust = 3.0 * (general_vol + company_vol)

    final_pct = max(0.0, base_pct - reduction_from_metric - news_adjust)
    final_eur = final_pct/100.0 * portfolio_eur

    st.subheader("Result")
    st.write(
        f"**Recommended position:** **€{final_eur:,.2f}**  (_{final_pct:.2f}% of portfolio_)")

    with st.expander("Details"):
        st.markdown(
            f"""
- Base: **{base_pct:.1f}%**
- Reduction from {'10-day move' if method.startswith('10-day') else 'excess beta'}: **{reduction_from_metric:.2f}%**
- News adjustments (general + company = {general_vol}+{company_vol}): **{news_adjust:.2f}%**
- Final: **{final_pct:.2f}%**
            """
        )
        for L in logs:
            st.write("•", L)

st.caption("Sizing rule: start at 30%. Reduce 1.5% per 0.10 step (either 0.10% of 10-day avg move, or 0.10 excess beta). "
           "Subtract 3% per point of expected General and Company Volatility (0–5). Floor at 0%.")
