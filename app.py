import streamlit as st
import yfinance as yf
import datetime

# --- Titel ---
st.set_page_config(page_title="Daily Market Dashboard", layout="wide")
st.title("📊 Daily Market Dashboard")

# --- Zeitfenster ---
end = datetime.date.today()
start = end - datetime.timedelta(days=90)  # letzte 90 Tage

# --- Ticker-Liste ---
tickers = {
    "VIX": "^VIX",
    "S&P 500": "^GSPC",
    "Nasdaq": "^IXIC",
    "DAX": "^GDAXI",
    "US 10Y Bond Yield": "^TNX",
    "EUR/USD": "EURUSD=X",
    "USD/JPY": "JPY=X",
    "WTI Oil": "CL=F",
    "Gold": "GC=F",
    "Silver": "SI=F",
    "Platinum": "PL=F"
}

# --- Layout mit KPIs ---
cols = st.columns(3)
for i, (name, ticker) in enumerate(tickers.items()):
    data = yf.download(ticker, start=start, end=end, progress=False)
    if not data.empty:
        latest_price = data["Close"].iloc[-1]
        prev_price = data["Close"].iloc[-2]
        change = (latest_price - prev_price) / prev_price * 100
        with cols[i % 3]:
            st.metric(label=name, value=f"{latest_price:.2f}", delta=f"{change:.2f}%")

# --- Charts ---
st.subheader("📈 Charts (letzte 90 Tage)")
for name, ticker in tickers.items():
    data = yf.download(ticker, start=start, end=end, progress=False)
    if not data.empty:
        st.line_chart(data["Close"], use_container_width=True)