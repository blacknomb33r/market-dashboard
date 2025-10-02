import streamlit as st
import yfinance as yf
from datetime import date, timedelta
import pandas as pd
import math

st.set_page_config(page_title="Daily Market Dashboard", layout="wide")
st.title("📊 Daily Market Dashboard (KPI only)")

# ---- Zeitraum (Sidebar) ----
st.sidebar.header("Zeitraum")
period_choice = st.sidebar.selectbox("Zeitraum", ["30 Tage", "90 Tage", "1 Jahr"], index=1)
days_map = {"30 Tage": 30, "90 Tage": 90, "1 Jahr": 365}
end = date.today()
start = end - timedelta(days=days_map[period_choice])

# ---- Ticker-Definition ----
TICKERS = {
    "VIX": {"ticker": "^VIX", "fmt": "idx"},
    "S&P 500": {"ticker": "^GSPC", "fmt": "idx"},
    "Nasdaq": {"ticker": "^IXIC", "fmt": "idx"},
    "DAX": {"ticker": "^GDAXI", "fmt": "idx"},
    "US 10Y Yield": {"ticker": "^TNX", "fmt": "pct_tnx"},  # 10x -> % durch /10
    "EUR/USD": {"ticker": "EURUSD=X", "fmt": "fx"},
    "USD/JPY": {"ticker": "JPY=X", "fmt": "fx"},
    "WTI Oil": {"ticker": "CL=F", "fmt": "px"},
    "Gold": {"ticker": "GC=F", "fmt": "px"},
    "Silver": {"ticker": "SI=F", "fmt": "px"},
    "Platinum": {"ticker": "PL=F", "fmt": "px"},
}

@st.cache_data(ttl=3600)
def fetch_close_series(yfticker: str, start, end) -> pd.Series | None:
    """Gibt Close-Serie (float) zurück oder None."""
    try:
        df = yf.download(yfticker, start=start, end=end, auto_adjust=True, progress=False)
        if df is None or df.empty or "Close" not in df.columns:
            return None
        s = df["Close"].dropna()
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0].dropna()
        if len(s) < 2:  # für 1d Delta brauchen wir mind. 2 Werte
            return None
        return s.astype(float)
    except Exception:
        return None

def fmt_value(x: float, kind: str) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "–"
    if kind == "pct_tnx":
        return f"{(x/10):.2f}%"
    if kind == "fx":
        return f"{x:.4f}"
    return f"{x:.2f}"

def pct_change(cur: float, prev: float) -> float:
    return (cur - prev) / prev * 100 if prev != 0 else float("nan")

def fmt_delta(cur: float, prev: float, kind: str, days_label: str) -> str:
    try:
        if kind == "pct_tnx":
            cur_pct, prev_pct = cur/10, prev/10
            diff = cur_pct - prev_pct
            sign = "+" if diff >= 0 else ""
            return f"{sign}{diff:.2f} pp ({days_label})"
        change = pct_change(cur, prev)
        sign = "+" if change >= 0 else ""
        return f"{sign}{change:.2f}% ({days_label})"
    except Exception:
        return "–"

def get_prev(series: pd.Series, sessions_back: int) -> float | None:
    """Nimmt N Handelssitzungen zurück (z. B. 1d=1, 5d=5). Gibt None, wenn zu kurz."""
    idx = len(series) - (sessions_back + 1)
    if idx < 0:
        return None
    try:
        return float(series.iloc[idx])
    except Exception:
        return None

st.subheader(f"Kern-KPIs ({period_choice})")
cols = st.columns(3)

tickers_with_no_data = []
tickers_missing_5d = []

for i, (name, meta) in enumerate(TICKERS.items()):
    yft = meta["ticker"]; kind = meta["fmt"]
    s = fetch_close_series(yft, start, end)

    with cols[i % 3]:
        if s is None or s.empty:
            st.metric(label=name, value="–", delta="–")
            tickers_with_no_data.append(name)
            continue

        latest = float(s.iloc[-1])
        prev1d = get_prev(s, 1)    # 1 Handelstag zurück
        prev5d = get_prev(s, 5)    # 5 Handelstage zurück (falls vorhanden)

        # 1d muss klappen (sonst skippen wir den Ticker wirklich)
        if prev1d is None:
            st.metric(label=name, value=fmt_value(latest, kind), delta="–")
            tickers_with_no_data.append(name + " (kein 1d)")
            continue

        value_str = fmt_value(latest, kind)
        delta1d = fmt_delta(latest, prev1d, kind, "1d")
        st.metric(label=name, value=value_str, delta=delta1d)

        # 5d optional
        if prev5d is not None:
            delta5d = fmt_delta(latest, prev5d, kind, "5d")
            st.caption(f"Δ vs. 5d: {delta5d}")
        else:
            tickers_missing_5d.append(name)

# Hinweise
if tickers_with_no_data:
    st.warning("Keine/zu wenig Daten für: " + ", ".join(tickers_with_no_data))
if tickers_missing_5d:
    st.info("Für 5d fehlte Historie bei: " + ", ".join(tickers_missing_5d))

st.caption("Charts sind vorübergehend deaktiviert.")