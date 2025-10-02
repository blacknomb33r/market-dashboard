import streamlit as st
import yfinance as yf
from datetime import date, timedelta
import pandas as pd
import math

st.set_page_config(page_title="Daily Market Dashboard", layout="wide")
st.title("📊 Daily Market Dashboard (KPI only)")

# ---- Zeitraum (Sidebar) ----
st.sidebar.header("Zeitraum")
period_choice = st.sidebar.selectbox(
    "Zeitraum",
    ["Aktuell", "30 Tage", "90 Tage", "1 Jahr"],
    index=1
)
days_map = {"30 Tage": 30, "90 Tage": 90, "1 Jahr": 365}
end = date.today()
if period_choice == "Aktuell":
    start = end   # dummy
else:
    start = end - timedelta(days=days_map[period_choice])

# ---- Ticker-Definition ----
TICKERS = {
    "VIX": {"ticker": "^VIX", "fmt": "idx"},
    "S&P 500": {"ticker": "^GSPC", "fmt": "idx"},
    "Nasdaq": {"ticker": "^IXIC", "fmt": "idx"},
    "DAX": {"ticker": "^GDAXI", "fmt": "idx"},
    "US 10Y Yield": {"ticker": "^TNX", "fmt": "pct_tnx"},
    "EUR/USD": {"ticker": "EURUSD=X", "fmt": "fx"},
    "USD/JPY": {"ticker": "JPY=X", "fmt": "fx"},
    "WTI Oil": {"ticker": "CL=F", "fmt": "px"},
    "Gold": {"ticker": "GC=F", "fmt": "px"},
    "Silver": {"ticker": "SI=F", "fmt": "px"},
    "Platinum": {"ticker": "PL=F", "fmt": "px"},
}

def fmt_value(x: float, kind: str) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "–"
    if kind == "pct_tnx":
        return f"{(x/10):.2f}%"
    if kind == "fx":
        return f"{x:.4f}"
    return f"{x:.2f}"

def fetch_intraday(yfticker: str):
    """Lädt den letzten Wert aus 1m-Intervallen"""
    try:
        df = yf.Ticker(yfticker).history(period="1d", interval="1m")
        if df is None or df.empty:
            return None
        return float(df["Close"].iloc[-1])
    except Exception:
        return None

@st.cache_data(ttl=3600)
def fetch_daily(yfticker: str, start, end) -> pd.Series | None:
    try:
        df = yf.download(yfticker, start=start, end=end, auto_adjust=True, progress=False)
        if df is None or df.empty or "Close" not in df.columns:
            return None
        s = df["Close"].dropna()
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0].dropna()
        if len(s) < 2:
            return None
        return s.astype(float)
    except Exception:
        return None

# ---- KPI-Anzeige ----
st.subheader(f"Kern-KPIs ({period_choice})")
cols = st.columns(3)

for i, (name, meta) in enumerate(TICKERS.items()):
    yft = meta["ticker"]; kind = meta["fmt"]

    with cols[i % 3]:
        if period_choice == "Aktuell":
            val = fetch_intraday(yft)
            st.metric(label=name, value=fmt_value(val, kind), delta="–")
        else:
            s = fetch_daily(yft, start, end)
            if s is None or s.empty:
                st.metric(label=name, value="–", delta="–")
                continue

            latest = float(s.iloc[-1])
            prev1d = float(s.iloc[-2]) if len(s) >= 2 else None
            prev5d = float(s.iloc[-6]) if len(s) >= 6 else None

            value_str = fmt_value(latest, kind)

            if prev1d is not None:
                delta1d = (latest - prev1d) / prev1d * 100 if prev1d != 0 else 0
                st.metric(label=name, value=value_str, delta=f"{delta1d:+.2f}% (1d)")
            else:
                st.metric(label=name, value=value_str, delta="–")

            if prev5d is not None:
                delta5d = (latest - prev5d) / prev5d * 100 if prev5d != 0 else 0
                st.caption(f"Δ vs. 5d: {delta5d:+.2f}%")