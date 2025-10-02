import streamlit as st
import yfinance as yf
from datetime import date, timedelta
import pandas as pd
import math

st.set_page_config(page_title="Daily Market Dashboard", layout="wide")
st.title("📊 Daily Market Dashboard")

# ---- Zeitraum (Sidebar) ----
st.sidebar.header("Zeitraum")
period_choice = st.sidebar.selectbox("Zeitraum", ["30 Tage", "90 Tage", "1 Jahr"], index=1)
days_map = {"30 Tage": 30, "90 Tage": 90, "1 Jahr": 365}
end = date.today()
start = end - timedelta(days=days_map[period_choice])

# ---- Ticker-Definition ----
# Hinweis: ^TNX (CBOE 10Y) liefert den 10-fachen Prozentwert -> teilen durch 10
TICKERS = {
    "VIX": {"ticker": "^VIX", "fmt": "idx"},
    "S&P 500": {"ticker": "^GSPC", "fmt": "idx"},
    "Nasdaq": {"ticker": "^IXIC", "fmt": "idx"},
    "DAX": {"ticker": "^GDAXI", "fmt": "idx"},
    "US 10Y Yield": {"ticker": "^TNX", "fmt": "pct_tnx"},      # geteilt durch 10 -> %
    "EUR/USD": {"ticker": "EURUSD=X", "fmt": "fx"},
    "USD/JPY": {"ticker": "JPY=X", "fmt": "fx"},               # Preis ist USD/JPY
    "WTI Oil": {"ticker": "CL=F", "fmt": "px"},
    "Gold": {"ticker": "GC=F", "fmt": "px"},
    "Silver": {"ticker": "SI=F", "fmt": "px"},
    "Platinum": {"ticker": "PL=F", "fmt": "px"},
}

# ---- Hilfsfunktionen ----
@st.cache_data(ttl=3600)
def fetch_batch(tickers, start, end):
    # yfinance: mehrere Ticker in einem Call
    df = yf.download(
        list(tickers),
        start=start,
        end=end,
        auto_adjust=True,   # künftige Default, hier explizit
        progress=False,
        group_by='ticker',
        threads=True
    )
    return df

def safe_get_close(df, yfticker):
    """Gibt die Close-Serie eines Tickers zurück oder None."""
    try:
        # Bei Multi-Index: (Ticker, 'Close'); bei Single: 'Close'
        if isinstance(df.columns, pd.MultiIndex):
            if (yfticker, 'Close') in df.columns:
                s = df[(yfticker, 'Close')].dropna()
            else:
                return None
        else:
            # Nur ein Ticker
            if 'Close' in df.columns:
                s = df['Close'].dropna()
            else:
                return None

        # Mindestens 2 Werte nötig (für Δ%)
        if s is None or len(s) < 2:
            return None
        return s
    except Exception:
        return None

def format_value(x, fmt):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "–"
    if fmt == "pct_tnx":
        # ^TNX: z.B. 45.12 -> 4.512%
        return f"{(x/10):.2f}%"
    elif fmt == "fx":
        return f"{x:.4f}"
    elif fmt in ("px", "idx"):
        return f"{x:.2f}"
    else:
        return f"{x:.2f}"

def compute_delta(cur, prev, fmt):
    try:
        if fmt == "pct_tnx":
            # Delta in %-Punkten
            cur_pct = cur/10
            prev_pct = prev/10
            change = cur_pct - prev_pct
            return f"{change:.2f} pp"
        else:
            # Prozentuale Veränderung
            change = (cur - prev) / prev * 100
            sign = "+" if change >= 0 else ""
            return f"{sign}{change:.2f}%"
    except Exception:
        return "–"

# ---- Daten holen ----
raw = fetch_batch([v["ticker"] for v in TICKERS.values()], start, end)

# ---- KPI-Karten ----
st.subheader(f"Kern-KPIs ({period_choice})")
cols = st.columns(3)

problems = []  # sammelt Ticker, die leer/kurz waren

for i, (name, meta) in enumerate(TICKERS.items()):
    yft = meta["ticker"]
    fmt = meta["fmt"]
    s = safe_get_close(raw, yft)
    with cols[i % 3]:
        if s is None or s.empty:
            st.metric(label=name, value="–", delta="–")
            problems.append(name)
            continue
        latest = float(s.iloc[-1])
        prev = float(s.iloc[-2])
        value_str = format_value(latest, fmt)
        delta_str = compute_delta(latest, prev, fmt)
        st.metric(label=name, value=value_str, delta=delta_str)

# ---- Warnungen anzeigen, falls nötig ----
if problems:
    st.warning(
        "Für folgende Ticker gab es heute zu wenige/keine Daten und sie wurden übersprungen: "
        + ", ".join(problems)
    )

# ---- Charts ----
st.subheader("📈 Charts")
for name, meta in TICKERS.items():
    yft = meta["ticker"]
    fmt = meta["fmt"]
    s = safe_get_close(raw, yft)
    if s is None:
        continue
    # ggf. ^TNX für Chart in % skalieren
    if fmt == "pct_tnx":
        s = s / 10.0
        s.name = name + " (%)"
    st.line_chart(s, use_container_width=True)