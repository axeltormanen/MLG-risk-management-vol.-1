import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# Title of the app
st.title("Stock Position Sizer App")

# Input fields
ticker_symbol = st.text_input("Ticker Symbol (e.g., AAPL)", "TSLA")
portfolio_size = st.number_input(
    "Portfolio Size (€)", value=5000.00, step=100.00)

# Volatility sliders
general_volatility = st.slider(
    "Expected General Volatility (0-5)", 0.0, 5.0, 2.0)
company_volatility = st.slider(
    "Expected Company Volatility (0-5)", 0.0, 5.0, 2.0)

# Calculate button
if st.button("Calculate Position Size"):
    st.write("Pulling price data for", ticker_symbol, "and QQQ...")

    # Fetch historical data for the ticker and QQQ
    try:
        # Download 5 years of daily data up to today (September 10, 2025)
        data = yf.download(ticker_symbol, start="2020-09-10", end="2025-09-10")
        qqq_data = yf.download("QQQ", start="2020-09-10", end="2025-09-10")

        # Check if enough data is available (e.g., at least 252 trading days ≈ 1 year)
        if len(data) < 252 or len(qqq_data) < 252:
            st.error("Not enough historical data available for calculations.")
        else:
            # Calculate daily returns
            data['Daily_Return'] = data['Adj Close'].pct_change()
            qqq_data['Daily_Return'] = qqq_data['Adj Close'].pct_change()

            # Drop NA values
            data = data.dropna()
            qqq_data = qqq_data.dropna()

            # Calculate beta (covariance with QQQ divided by variance of QQQ)
            covariance = data['Daily_Return'].cov(qqq_data['Daily_Return'])
            variance = qqq_data['Daily_Return'].var()
            beta = covariance / variance

            # 20-day beta (using last 20 days)
            beta_20 = data['Daily_Return'].tail(20).cov(
                qqq_data['Daily_Return'].tail(20)) / variance

            # 200-day beta (using last 200 days)
            beta_200 = data['Daily_Return'].tail(200).cov(
                qqq_data['Daily_Return'].tail(200)) / variance

            # Average beta
            avg_beta = (beta + beta_20 + beta_200) / 3

            # Position sizing based on risk factors
            if avg_beta > 0:
                position_size = (portfolio_size * (1 / avg_beta)) * \
                    (general_volatility / 5) * (company_volatility / 5)
            else:
                # Default to 10% if beta is zero or negative
                position_size = portfolio_size * 0.1

            # Adjust position size to avoid negative or zero values
            position_size = max(0, min(position_size, portfolio_size))

            # Get the latest price
            latest_price = data['Adj Close'].iloc[-1]

            # Calculate number of shares
            num_shares = position_size / latest_price

            # Display results
            st.write(f"### Calculated Position Size")
            st.write(f"Latest Price: €{latest_price:.2f}")
            st.write(f"Number of Shares: {num_shares:.2f}")
            st.write(f"Position Value: €{position_size:.2f}")

    except Exception as e:
        st.error(f"Error fetching data: {e}")

# Note about data
st.write("Note: Enough historical data is required for calculations.")
