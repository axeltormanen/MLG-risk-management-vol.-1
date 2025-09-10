import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np


def calculate_position_size(
    ticker: str,
    portfolio_eur: float,
    exp_vol_general: int,
    exp_vol_company: int,
):
    st.write(f"Pulling price data for {ticker} and QQQ...")
    # 2 years to ensure >=201 daily returns for 200-day calc
    data = yf.download([ticker, "QQQ"], period="2y")["Adj Close"]

    if data.isna().any().any():
        data = data.dropna()

    if len(data) < 201 or ticker not in data.columns or "QQQ" not in data.columns:
        st.error("Not enough historical data available for calculations.")
        return None

    returns = data.pct_change().dropna()

    # 10-day beta (use last 11 rows → 10 returns)
    recent = returns.tail(11)
    cov10 = np.cov(recent[ticker], recent["QQQ"])[0][1]
    var10 = np.var(recent["QQQ"])
    beta10 = cov10 / var10 if var10 != 0 else 0.0
    st.write(f"10-day Beta: {beta10:.2f}")

    # 200-day beta (use last 201 rows → 200 returns)
    long = returns.tail(201)
    cov200 = np.cov(long[ticker], long["QQQ"])[0][1]
    var200 = np.var(long["QQQ"])
    beta200 = cov200 / var200 if var200 != 0 else 0.0
    st.write(f"200-day Beta: {beta200:.2f}")

    # Average beta
    avg_beta = (beta10 + beta200) / 2
    st.write(f"Average Beta: {avg_beta:.2f}")

    # Beta adjustment (simple tiers)
    if avg_beta < 1:
        beta_adj = 0.0
    elif 1 <= avg_beta < 1.3:
        beta_adj = 0.5
    else:
        beta_adj = 1.0

    # Volatility adjustment from sliders (0–5 → 0–1 scale)
    vol_adj = (exp_vol_general + exp_vol_company) / 10

    # Position sizing: base * (1 – blended risk)
    risk_factor = 1 - (0.5 * beta_adj + 0.5 * vol_adj)
    risk_factor = max(0.0, min(1.0, risk_factor))  # clamp 0..1
    position_eur = portfolio_eur * risk_factor
    final_pct = 100 * position_eur / portfolio_eur if portfolio_eur > 0 else 0

    st.success(
        f"Recommended Position Size: €{position_eur:,.2f} ({final_pct:.1f}% of portfolio)")
    return position_eur


# =========================
# Streamlit UI
# =========================
st.title("📊 Stock Position Sizer App")

col1, col2 = st.columns([3, 2])
with col1:
    ticker = st.text_input("Ticker Symbol (e.g., AAPL)",
                           "TSLA").upper().strip()
with col2:
    portfolio_eur = st.number_input(
        "Portfolio Size (€)", min_value=0.0, value=5000.0, step=100.0)

exp_vol_general = st.slider("Expected General Volatility (0–5)", 0, 5, 2)
exp_vol_company = st.slider("Expected Company Volatility (0–5)", 0, 5, 2)

if st.button("Calculate Position Size", type="primary"):
    calculate_position_size(
        ticker=ticker,
        portfolio_eur=portfolio_eur,
        exp_vol_general=exp_vol_general,
        exp_vol_company=exp_vol_company,
    )
