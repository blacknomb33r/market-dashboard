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
# ^TNX liefert 10x den Prozentwert (z.B. 45.12 == 4.512%), deshalb später /10
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

@st.cache_data(ttl=3600)
def fetch_close_series(yfticker: str, start, end) -> pd.Series | None:
    """
    Holt Close-Serie für einen Ticker und gibt eine 1D-Serie zurück
    (Float-Werte), oder None wenn zu wenig/keine Daten.
    """
    try:
        df = yf.download(yfticker, start=start, end=end, auto_adjust=True, progress=False)
        if df is None or df.empty: 
            return None
        # Manche Builds liefern hier ein DataFrame; wir holen explizit die Close-Spalte
        if "Close" not in df.columns:
            return None
        s = df["Close"].dropna()
        # In sehr seltenen Fällen kommt ein DataFrame mit 1 Spalte zurück – absichern:
        if isinstance(s, pd.DataFrame):
            # auf Series reduzieren
            if "Close" in s.columns:
                s = s["Close"].dropna()
            else:
                # auf erste Spalte zurückfallen
                s = s.iloc[:, 0].dropna()
        # Mindestens 2 Werte nötig (für Δ)
        if s is None or len(s) < 2:
            return None
        # Sicherheit: auf float casten (manchmal sind es Decimal/np types)
        s = s.astype(float)
        return s
    except Exception:
        return None

def fmt_value(x: float, kind: str) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "–"
    if kind == "pct_tnx":
        return f"{(x/10):.2f}%"
    if kind == "fx":
        return f"{x:.4f}"
    # px/idx:
    return f"{x:.2f}"

def fmt_delta(cur: float, prev: float, kind: str) -> str:
    try:
        if kind == "pct_tnx":
            # Δ in Prozentpunkten
            cur_pct = cur/10
            prev_pct = prev/10
            diff = cur_pct - prev_pct
            sign = "+" if diff >= 0 else ""
            return f"{sign}{diff:.2f} pp"
        # sonst: prozentuale Veränderung
        change = (cur - prev) / prev * 100
        sign = "+" if change >= 0 else ""
        return f"{sign}{change:.2f}%"
    except Exception:
        return "–"

st.subheader(f"Kern-KPIs ({period_choice})")
cols = st.columns(3)
problems: list[str] = []

for i, (name, meta) in enumerate(TICKERS.items()):
    yft = meta["ticker"]; kind = meta["fmt"]
    s = fetch_close_series(yft, start, end)
    with cols[i % 3]:
        if s is None or s.empty:
            st.metric(label=name, value="–", delta="–")
            problems.append(name)
            continue
        # letzte zwei Werte als floats
        latest = float(s.iloc[-1])
        prev   = float(s.iloc[-2])
        st.metric(label=name, value=fmt_value(latest, kind), delta=fmt_delta(latest, prev, kind))

if problems:
    st.warning(
        "Keine/zu wenig Daten für: " + ", ".join(problems)
        + " — sie wurden übersprungen."
    )

st.caption("Charts sind vorübergehend deaktiviert, um Stabilität sicherzustellen.")