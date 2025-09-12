import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Stock Position Sizer App", layout="centered")

st.title("📊 Stock Position Sizer App")

# --- Inputs ---
ticker_symbol = st.text_input("Ticker Symbol (e.g., AAPL)", "TSLA")
portfolio_size = st.number_input(
    "Portfolio Size (€)", value=5000.00, step=100.00)

# Integer-only sliders (0–5)
general_volatility = st.slider(
    "Expected General Volatility (0–5)", min_value=0, max_value=5, value=2, step=1)
company_volatility = st.slider(
    "Expected Company Volatility (0–5)", min_value=0, max_value=5, value=2, step=1)

if st.button("Calculate Position Size"):
    st.write(f"Pulling price data for {ticker_symbol}...")

    try:
        # Pull enough daily history to safely compute 10 most recent returns
        px = yf.download(ticker_symbol, period="30d",
                         interval="1d")["Adj Close"]

        if px is None or len(px) < 11:
            st.error(
                "Not enough historical data available (need at least 10 trading days).")
        else:
            # 10-day average absolute daily move (%)
            rets = px.pct_change().dropna() * 100
            last10 = rets.tail(10)
            avg_abs_move = float(np.mean(np.abs(last10)))

            # --- Base rule (#3) ---
            # Start 30%, reduce 1.5% per 0.10% of avg move
            reduction_steps = avg_abs_move / 0.10
            base_position_pct = max(30.0 - 1.5 * reduction_steps, 0.0)

            # --- Slider adjustments (#4) ---
            # Each point on either slider reduces position by 3 percentage points
            slider_reduction_pp = 3.0 * \
                (general_volatility + company_volatility)
            final_position_pct = max(
                base_position_pct - slider_reduction_pp, 0.0)

            # € position
            position_eur = portfolio_size * (final_position_pct / 100.0)

            # --- Display ---
            st.subheader("📈 Results")
            st.write(f"Average 10-day daily move: **{avg_abs_move:.2f}%**")
            st.write(
                f"Base position (from avg move): **{base_position_pct:.2f}%**")
            st.write(f"Slider reduction: **{slider_reduction_pp:.2f} pp** "
                     f"(3 pp × ({general_volatility} + {company_volatility}))")
            st.write(
                f"**Final position: {final_position_pct:.2f}% of portfolio**")
            st.write(f"≈ **€{position_eur:,.2f}**")

            with st.expander("Details"):
                st.write("Last 10 daily returns (%)")
                st.dataframe(pd.DataFrame({"return_%": last10.round(3)}).T)

    except Exception as e:
        st.error(f"Error fetching data: {e}")

st.caption(
    "Sizing rule: start at 30% and reduce by 1.5% for each 0.10% of the 10-day average absolute daily move. "
    "Then subtract 3 percentage points for each point of expected General and Company Volatility (0–5). "
    "Position is floored at 0%."
)
