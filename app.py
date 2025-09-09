import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np


def calculate_position_size(ticker, portfolio_eur=5000, exp_vol_general=0, exp_vol_company=0):
    # Step 1: Pull data for ticker and QQQ
    st.write("Pulling price data for {} and QQQ...".format(ticker))
    data = yf.download([ticker, 'QQQ'], period='1y')['Adj Close']

    if len(data) < 201:
        st.error("Not enough historical data available for calculations.")
        return None

    returns = data.pct_change().dropna()

    # Step 2: Compute 10-day beta (using last 11 days for 10 returns)
    recent_returns = returns.tail(11)
    cov10 = np.cov(recent_returns[ticker], recent_returns['QQQ'])[0][1]
    var10 = np.var(recent_returns['QQQ'])
    beta10 = cov10 / var10 if var10 != 0 else 0
    st.write("10-day Beta: {:.2f}".format(beta10))

    # Step 3: Compute 200-day beta (using last 201 days for 200 returns)
    long_returns = returns.tail(201)
    cov200 = np.cov(long_returns[ticker], long_returns['QQQ'])[0][1]
    var200 = np.var(long_returns['QQQ'])
    beta200 = cov200 / var200 if var200 != 0 else 0
    st.write("200-day Beta: {:.2f}".format(beta200))

    # Step 4: Average beta
    avg_beta = (beta10 + beta200) / 2
    st.write("Average Beta: {:.2f}".format(avg_beta))

    # Step 5: Beta adjustment
    if avg_beta < 1:
        beta_adj = 0
    elif 1 <= avg_beta < 1.3:
        beta_adj = 20
    elif 1.3 <= avg_beta <= 1.6:
        beta_adj = 0
    elif 1.6 < avg_beta <= 2:
        beta_adj = -15
    else:
        beta_adj = -25
    st.write("Beta Adjustment: {}%".format(beta_adj))

    # Step 6: Volatility adjustments (news rules)
    vol_map = {0: 30, 1: 22, 2: 13, 3: 0, 4: -12, 5: -28}
    gen_adj = vol_map.get(exp_vol_general, 0)
    com_adj = vol_map.get(exp_vol_company, 0)
    st.write("General Volatility Adjustment: {}%".format(gen_adj))
    st.write("Company Volatility Adjustment: {}%".format(com_adj))

    # Step 7: Base size
    base_size = 0.0105 * portfolio_eur
    st.write("Base Size: {:.2f} EUR (1.05% of portfolio)".format(base_size))

    # Step 8: Calculate factors
    beta_factor = 1 + beta_adj / 100
    vol_gen_factor = 1 + gen_adj / 100
    vol_com_factor = 1 + com_adj / 100
    combined_vol_factor = vol_gen_factor * vol_com_factor
    st.write("Beta Factor: {:.2f}".format(beta_factor))
    st.write("Combined Volatility Factor: {:.2f}".format(combined_vol_factor))

    # Step 9: Adjusted size before caps
    adjusted_size = base_size * beta_factor * combined_vol_factor
    st.write("Adjusted Size (before caps): {:.2f} EUR".format(adjusted_size))

    # Step 10: Apply caps (+40% max up, -30% max down from base)
    max_size = base_size * 1.4
    min_size = base_size * 0.7
    final_size = max(min_size, min(max_size, adjusted_size))
    final_pct = (final_size / portfolio_eur) * 100
    st.write("Final Size (after caps): {:.2f} EUR ({:.2f}% of portfolio)".format(
        final_size, final_pct))

    return final_size


# Streamlit app interface
st.title("Stock Position Sizer App")
st.write("Enter the details below to calculate the recommended position size.")

ticker = st.text_input("Ticker Symbol (e.g., AAPL)", value="AAPL")
exp_vol_general = st.slider(
    "Expected General Volatility (0-5)", min_value=0, max_value=5, value=0)
exp_vol_company = st.slider(
    "Expected Company Volatility (0-5)", min_value=0, max_value=5, value=0)

if st.button("Calculate Position Size"):
    calculate_position_size(ticker, 5000, exp_vol_general, exp_vol_company)
