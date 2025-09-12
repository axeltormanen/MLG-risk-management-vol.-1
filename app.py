import streamlit as st
import yfinance as yf
import pandas as pd

# Title
st.title("📊 Stock Position Sizer App")

# User inputs
ticker_symbol = st.text_input("Ticker Symbol (e.g., TSLA)", "TSLA")
portfolio_size = st.number_input(
    "Portfolio Size (€)", min_value=100.0, value=5000.0, step=100.0)

general_volatility = st.slider(
    "Expected General Volatility (0–5)", 0, 5, 2, step=1)
company_volatility = st.slider(
    "Expected Company Volatility (0–5)", 0, 5, 2, step=1)

if st.button("Calculate Position Size"):
    st.write(f"Pulling price data for {ticker_symbol.upper()}...")

    try:
        # Fetch 1 month of data to ensure at least 10 trading days
        data = yf.download(ticker_symbol, period="1mo",
                           interval="1d")['Adj Close']

        if len(data) < 10:
            st.error(
                "Not enough historical data available (need at least 10 trading days).")
        else:
            # Use the last 10 trading days
            last_10 = data.tail(10)
            returns = last_10.pct_change().dropna()
            avg_move = (returns.abs().mean()) * 100  # in %

            # --- Sizing Rule ---
            base_position = 30.0  # start at 30%
            reduction_from_moves = (avg_move / 0.10) * \
                1.5  # each 0.10% reduces by 1.5%
            reduction_from_vol = (general_volatility +
                                  company_volatility) * 3.0  # sliders

            final_position_pct = base_position - reduction_from_moves - reduction_from_vol
            final_position_pct = max(0, final_position_pct)  # floor at 0%

            # Position in €
            position_value = (final_position_pct / 100) * portfolio_size

            # --- Results ---
            st.success(
                f"✅ Recommended Position Size: **{final_position_pct:.2f}%** of portfolio")
            st.info(f"💰 Position Value: **€{position_value:,.2f}**")
            st.write(f"📈 10-Day Average Absolute Move: **{avg_move:.2f}%**")

            # Explanation
            st.caption(
                "Sizing rule: Start at 30% and reduce by 1.5% for each 0.10% of the 10-day average "
                "absolute daily move. Then subtract 3 percentage points for each point of expected "
                "General and Company Volatility (0–5). Position is floored at 0%."
            )

    except Exception as e:
        st.error(f"⚠️ Error fetching data: {e}")
