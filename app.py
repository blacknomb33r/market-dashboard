import streamlit as st
import yfinance as yf
from datetime import date, timedelta
import pandas as pd
import math
import requests

st.set_page_config(page_title="Daily Market Dashboard", layout="wide")
st.title("📊 Daily Market Dashboard (KPI only)")

# ---- Zeitraum (Sidebar) ----
st.sidebar.header("Zeitraum")
period_choice = st.sidebar.selectbox(
    "Zeitraum",
    ["Live", "30 Tage", "90 Tage", "1 Jahr"],   # <-- ersetzt "Aktuell"
    index=1
)
days_map = {"30 Tage": 30, "90 Tage": 90, "1 Jahr": 365}
end = date.today()
start = end - timedelta(days=days_map.get(period_choice, 30))

# ---- Gruppen-Definition ----
GROUPS = {
    "USA": {
        "S&P 500": {"ticker": "^GSPC", "fmt": "idx"},
        "Nasdaq": {"ticker": "^IXIC", "fmt": "idx"},
        "US 10Y Yield": {"ticker": "^TNX", "fmt": "pct_tnx"},
        "USD/JPY": {"ticker": "JPY=X", "fmt": "fx"},
    },
    "EU": {
        "DAX": {"ticker": "^GDAXI", "fmt": "idx"},
        "EUR/USD": {"ticker": "EURUSD=X", "fmt": "fx"},
    },
    "Rohstoffe": {
        "WTI Oil": {"ticker": "CL=F", "fmt": "px"},
        "Gold": {"ticker": "GC=F", "fmt": "px"},
        "Silver": {"ticker": "SI=F", "fmt": "px"},
        "Platinum": {"ticker": "PL=F", "fmt": "px"},
    },
    "Index": {
        "VIX": {"ticker": "^VIX", "fmt": "idx"},
    },
}

# -------- Helpers --------
def fmt_value(x: float, kind: str) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "–"
    if kind == "pct_tnx":
        return f"{(x/10):.2f}%"
    if kind == "fx":
        return f"{x:.4f}"
    return f"{x:.2f}"

def fmt_delta_pct(cur: float, prev: float) -> str:
    if prev == 0 or prev is None or cur is None:
        return "–"
    chg = (cur - prev) / prev * 100
    return f"{chg:+.2f}%"

def fmt_delta_pp_tnx(cur: float, prev: float) -> str:
    if prev is None or cur is None:
        return "–"
    diff_pp = (cur/10) - (prev/10)
    return f"{diff_pp:+.2f} pp"

@st.cache_data(ttl=90)
def fetch_intraday_last(yfticker: str) -> float | None:
    try:
        df = yf.Ticker(yfticker).history(period="1d", interval="1m")
        if df is None or df.empty or "Close" not in df.columns:
            return None
        return float(df["Close"].dropna().iloc[-1])
    except Exception:
        return None

@st.cache_data(ttl=1800)
def fetch_prev_daily_close(yfticker: str) -> float | None:
    try:
        df = yf.Ticker(yfticker).history(period="5d", interval="1d")
        if df is None or df.empty or "Close" not in df.columns:
            return None
        closes = df["Close"].dropna()
        if len(closes) < 2:
            return None
        return float(closes.iloc[-1])
    except Exception:
        return None

@st.cache_data(ttl=3600)
def fetch_daily_series(yfticker: str, start, end) -> pd.Series | None:
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

def get_prev(series: pd.Series, sessions_back: int) -> float | None:
    idx = len(series) - (sessions_back + 1)
    if idx < 0:
        return None
    try:
        return float(series.iloc[idx])
    except Exception:
        return None


# -------- KPI Anzeige --------
for group_name, tickers in GROUPS.items():
    st.subheader(group_name)
    cols = st.columns(3)

    for i, (name, meta) in enumerate(tickers.items()):
        yft = meta["ticker"]; kind = meta["fmt"]

        with cols[i % 3]:
            if period_choice == "Live":
                cur = fetch_intraday_last(yft)
                prev_close = fetch_prev_daily_close(yft)
                value_str = fmt_value(cur, kind)

                if kind == "pct_tnx":
                    delta_str = fmt_delta_pp_tnx(cur, prev_close)
                else:
                    delta_str = fmt_delta_pct(cur, prev_close)

                st.metric(label=name, value=value_str, delta=f"{delta_str} (vs. Vortag)")
            else:
                s = fetch_daily_series(yft, start, end)
                if s is None or s.empty:
                    st.metric(label=name, value="–", delta="–")
                    continue

                latest = float(s.iloc[-1])
                prev1d = get_prev(s, 1)
                prev5d = get_prev(s, 5)
                value_str = fmt_value(latest, kind)

                if kind == "pct_tnx":
                    delta1d = fmt_delta_pp_tnx(latest, prev1d) if prev1d else "–"
                else:
                    delta1d = fmt_delta_pct(latest, prev1d) if prev1d else "–"

                st.metric(label=name, value=value_str, delta=f"{delta1d} (1d)")

                if prev5d is not None:
                    if kind == "pct_tnx":
                        d5 = fmt_delta_pp_tnx(latest, prev5d)
                    else:
                        d5 = fmt_delta_pct(latest, prev5d)
                    st.caption(f"Δ vs. 5d: {d5}")
                else:
                    st.caption("Δ vs. 5d: –")

st.caption("Hinweis: 'Live' nutzt Intraday-Daten (~15 Min Verzögerung bei Yahoo).")