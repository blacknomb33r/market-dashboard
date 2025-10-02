import streamlit as st
import yfinance as yf
from datetime import date, timedelta
import pandas as pd
import math
from typing import Optional, Tuple

# ================== PAGE ==================
st.set_page_config(page_title="Daily Market Dashboard", layout="wide")
st.title("Daily Market Dashboard")

# ================== SIDEBAR ==================
st.sidebar.header("Zeitraum & Performance")
period_choice = st.sidebar.selectbox(
    "Zeitraum",
    ["Live", "30 Tage", "90 Tage", "1 Jahr"],   # Live als Default
    index=0
)
# Speed Mode: schaltet Intraday in der Overview aus und spart FRED, wenn True
speed_mode = st.sidebar.toggle("⚡ Speed Mode (schneller laden)", value=True)

# Manuelles Refresh
if st.sidebar.button("↻ Aktualisieren"):
    st.cache_data.clear()
    st.rerun()

days_map = {"30 Tage": 30, "90 Tage": 90, "1 Jahr": 365}
today = date.today()
start = today - timedelta(days=days_map.get(period_choice, 30))

# ================== GROUPS ==================
GROUPS = {
    "🇺🇸 USA": {
        "S&P 500": {"ticker": "^GSPC", "fmt": "idx"},
        "Nasdaq": {"ticker": "^IXIC", "fmt": "idx"},
        "US 10Y Yield": {"ticker": "^TNX", "fmt": "pct_rate"},  # echte %
        "USD/JPY": {"ticker": "JPY=X", "fmt": "fx"},
    },
    "🇪🇺 Europa": {
        "DAX": {"ticker": "^GDAXI", "fmt": "idx"},
        "MDAX": {"ticker": "^MDAXI", "fmt": "idx"},
        "EuroStoxx50": {"ticker": "^STOXX50E", "fmt": "idx"},
        "FTSE100": {"ticker": "^FTSE", "fmt": "idx"},
        "EUR/USD": {"ticker": "EURUSD=X", "fmt": "fx"},
        "DE 10Y Yield": {"ticker": "FRED:DE10Y", "fmt": "pct_rate"},  # via FRED
    },
    "⛽ Rohstoffe": {
        "WTI Oil": {"ticker": "CL=F", "fmt": "px"},
        "Gold": {"ticker": "GC=F", "fmt": "px"},
        "Silver": {"ticker": "SI=F", "fmt": "px"},
        "Platinum": {"ticker": "PL=F", "fmt": "px"},
    },
    "₿ Krypto": {
        "Bitcoin": {"ticker": "BTC-USD", "fmt": "px"},
        "Ethereum": {"ticker": "ETH-USD", "fmt": "px"},
    },
    "📉 Volalität": {
        "VIX": {"ticker": "^VIX", "fmt": "idx"},
    },
}

# Quick Overview – genau diese 6 Kacheln oben
OVERVIEW = [
    ("S&P 500", "🇺🇸 USA"),
    ("DAX", "🇪🇺 Europa"),
    ("WTI Oil", "⛽ Rohstoffe"),
    ("Gold", "⛽ Rohstoffe"),
    ("Bitcoin", "₿ Krypto"),
    ("VIX", "📉 Volalität"),
]

# 1-Satz Erklärungen (für ℹ️ Info)
DESCRIPTIONS = {
    "S&P 500": "US-Blue-Chip-Index: 500 größte börsennotierte US-Unternehmen.",
    "Nasdaq": "Technologielastiger US-Index mit über 100 großen Firmen.",
    "US 10Y Yield": "Rendite 10-jähriger US-Staatsanleihen – wichtigster Zins-Benchmark.",
    "USD/JPY": "Wechselkurs US-Dollar gegen Japanischen Yen.",
    "DAX": "40 größte börsennotierte Unternehmen in Deutschland.",
    "MDAX": "50 mittelgroße börsennotierte Unternehmen in Deutschland.",
    "EuroStoxx50": "50 größte Unternehmen aus der Eurozone.",
    "STOXX Europe 600": "Breitester Europa-Index mit 600 Aktien.",
    "CAC 40": "40 größte börsennotierte Unternehmen in Frankreich.",
    "FTSE100": "100 größte börsennotierte Unternehmen im Vereinigten Königreich.",
    "SMI": "20 größte börsennotierte Unternehmen in der Schweiz.",
    "IBEX 35": "35 wichtigste börsennotierte Unternehmen in Spanien.",
    "EUR/USD": "Wechselkurs Euro gegen US-Dollar.",
    "DE 10Y Yield": "Rendite 10-jähriger deutscher Bundesanleihen.",
    "WTI Oil": "US-Rohöl (West Texas Intermediate) in USD pro Barrel.",
    "Gold": "Goldpreis in USD pro Feinunze.",
    "Silver": "Silberpreis in USD pro Feinunze.",
    "Platinum": "Platinpreis in USD pro Feinunze.",
    "Bitcoin": "Größte Kryptowährung nach Marktkapitalisierung.",
    "Ethereum": "Zweitgrößte Kryptowährung; Plattform für Smart Contracts.",
    "VIX": "Volatilitätsindex (S&P 500); misst erwartete Schwankungen.",
}

# ================== HELPERS (Format/Delta/UI) ==================
def fmt_value(x: Optional[float], kind: str) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "–"
    if kind == "pct_rate":   # Renditen in %
        return f"{x:.2f}%"
    if kind == "fx":         # Devisen
        return f"{x:.4f}"
    return f"{x:.2f}"        # Indizes/Preise

def delta_pct(cur: Optional[float], prev: Optional[float]) -> Optional[float]:
    if cur is None or prev is None or prev == 0:
        return None
    return (cur - prev) / prev * 100

def fmt_delta_pct(cur: Optional[float], prev: Optional[float]) -> str:
    chg = delta_pct(cur, prev)
    if chg is None or math.isnan(chg):
        return "–"
    return f"{chg:+.2f}%"

def fmt_delta_pp_rate(cur: Optional[float], prev: Optional[float]) -> str:
    if cur is None or prev is None:
        return "–"
    diff = cur - prev
    return f"{diff:+.2f} pp"

def render_metric(name: str, value: str, delta: str, extra_caption: str = ""):
    st.metric(label=name, value=value, delta=delta)
    if extra_caption:
        st.caption(extra_caption)
    desc = DESCRIPTIONS.get(name)
    if desc:
        with st.expander("ℹ️ Info", expanded=False):
            st.write(desc)

# ================== DATA FETCH (schnell & frisch) ==================

# Intraday nur für Overview (5m = schneller/stabiler; 15 min Cache-Delay passend zur Yahoo-Verzögerung)
@st.cache_data(ttl=900)
def fetch_intraday_last(ticker: str) -> Optional[float]:
    try:
        df = yf.Ticker(ticker).history(period="1d", interval="5m")
        if df is None or df.empty:
            return None
        return float(df["Close"].dropna().iloc[-1])
    except Exception:
        return None

# Daily-BATCH: holt Close-Serien für eine gegebene Tickerliste in EINEM Request
@st.cache_data(ttl=1800)  # 30 min – reicht für Daily
def bulk_daily(tickers: list[str], start_date: date, end_date: date) -> dict[str, pd.Series]:
    if not tickers:
        return {}
    df = yf.download(
        tickers=tickers,
        start=start_date,
        end=end_date,
        auto_adjust=True,
        group_by="ticker",
        threads=True,
        progress=False
    )
    out: dict[str, pd.Series] = {}
    if isinstance(df.columns, pd.MultiIndex):
        for t in tickers:
            try:
                s = df[t]["Close"].dropna().astype(float)
                out[t] = s
            except Exception:
                out[t] = pd.Series(dtype=float)
    else:
        # Einzelner Ticker-Fall
        s = df["Close"].dropna().astype(float)
        out[tickers[0]] = s
    return out

def series_first_value(s: Optional[pd.Series]) -> Optional[float]:
    if s is None or s.empty: return None
    return float(s.iloc[0])

def series_last_value(s: Optional[pd.Series]) -> Optional[float]:
    if s is None or s.empty: return None
    return float(s.iloc[-1])

def get_prev_by_sessions(s: Optional[pd.Series], n: int) -> Optional[float]:
    if s is None or s.empty or len(s) <= n: return None
    return float(s.iloc[-(n+1)])

# --------- FRED (DE10Y) nur bei Bedarf laden ----------
from fredapi import Fred
fred_key = st.secrets.get("FRED_API_KEY", None)
fred = Fred(api_key=fred_key) if (fred_key and not speed_mode) else None

@st.cache_data(ttl=3600)
def fred_series(series_id: str, start_date: date, end_date: date) -> Optional[pd.Series]:
    if fred is None:
        return None
    try:
        s = fred.get_series(series_id, observation_start=start_date, observation_end=end_date)
        if s is None or s.empty:
            return None
        s = s.dropna().astype(float)
        s.index = pd.to_datetime(s.index)
        return s
    except Exception:
        return None

def get_de10y_series(start_date: date, end_date: date) -> Optional[pd.Series]:
    return fred_series("IRLTLT01DEM156N", start_date, end_date)

# ================== QUICK OVERVIEW ==================
st.subheader("Quick Overview")
cols = st.columns(6)

# Sammle die Overview-Ticker (ohne FRED)
overview_tickers = []
for label, gkey in OVERVIEW:
    meta = GROUPS[gkey][label]
    tk = meta["ticker"]
    if not tk.startswith("FRED:"):
        overview_tickers.append(tk)
overview_tickers = sorted(set(overview_tickers))

# Für schnelle Overview: Daily-Serien (1 Batch)
OV_hist = bulk_daily(overview_tickers, start, today + timedelta(days=1))
OV_ytd  = bulk_daily(overview_tickers, date(today.year,1,1), today + timedelta(days=1))
OV_mtd  = bulk_daily(overview_tickers, date(today.year,today.month,1), today + timedelta(days=1))

for i, (label, gkey) in enumerate(OVERVIEW):
    meta = GROUPS[gkey][label]
    tk = meta["ticker"]; kind = meta["fmt"]

    # Wert & Delta
    if (period_choice == "Live") and (not speed_mode) and (not tk.startswith("FRED:")):
        cur = fetch_intraday_last(tk)
        prev = get_prev_by_sessions(OV_hist.get(tk), 1)
        val = fmt_value(cur, kind)
        delta = (fmt_delta_pp_rate(cur, prev) if kind=="pct_rate" else fmt_delta_pct(cur, prev)) + " (vs. Vortag)"
    else:
        cur = series_last_value(OV_hist.get(tk))
        prev = get_prev_by_sessions(OV_hist.get(tk), 1)
        val = fmt_value(cur, kind)
        delta = (fmt_delta_pp_rate(cur, prev) if kind=="pct_rate" else fmt_delta_pct(cur, prev)) + " (1d)"

    # YTD / MTD
    y_base = series_first_value(OV_ytd.get(tk))
    m_base = series_first_value(OV_mtd.get(tk))
    ytd = delta_pct(cur, y_base)
    mtd = delta_pct(cur, m_base)
    caption = f"YTD: {'–' if (ytd is None or math.isnan(ytd)) else f'{ytd:+.2f}%'} | MTD: {'–' if (mtd is None or math.isnan(mtd)) else f'{mtd:+.2f}%'}"

    with cols[i % 6]:
        render_metric(label, val, delta, caption)

st.caption("Hinweis: 'Live' nutzt Intraday-Daten (Yahoo ~15 Min Verzögerung).")
st.divider()

# ================== GROUPS (Lazy-Load pro Gruppe) ==================
for group_name, tickers in GROUPS.items():
    with st.expander(group_name, expanded=False):
        # Tickerliste der Gruppe (ohne FRED)
        grp_tickers = [m["ticker"] for m in tickers.values() if not m["ticker"].startswith("FRED:")]
        grp_tickers = sorted(set(grp_tickers))

        # Ladehinweis und Button (so laden wir nur, wenn geöffnet)
        load_clicked = st.button("Daten laden", key=f"load_{group_name}")
        if not load_clicked:
            st.caption("Zum Laden klicken (schneller Start, besonders auf dem Handy).")
            continue

        with st.spinner("Lade Daten..."):
            GRP_hist = bulk_daily(grp_tickers, start, today + timedelta(days=1))
            GRP_ytd  = bulk_daily(grp_tickers, date(today.year,1,1), today + timedelta(days=1))
            GRP_mtd  = bulk_daily(grp_tickers, date(today.year,today.month,1), today + timedelta(days=1))

        cols = st.columns(3)
        for i, (name, meta) in enumerate(tickers.items()):
            tk = meta["ticker"]; kind = meta["fmt"]
            with cols[i % 3]:
                # DE10Y (FRED) nur, wenn Speed Mode aus und Key vorhanden
                if tk.startswith("FRED:"):
                    if speed_mode or fred is None:
                        render_metric(name, "–", "aus Performance-Gründen ausgelassen", "YTD: – | MTD: –")
                        continue
                    s = get_de10y_series(date(today.year,1,1), today + timedelta(days=1))
                    if s is None or s.empty:
                        render_metric(name, "–", "–", "YTD: – | MTD: –")
                        continue
                    latest = series_last_value(s)
                    prev1d = get_prev_by_sessions(s, 1)
                    val = fmt_value(latest, "pct_rate")
                    d1 = fmt_delta_pp_rate(latest, prev1d) if prev1d is not None else "–"
                    # YTD/MTD
                    y_base = series_first_value(s)
                    mser = get_de10y_series(date(today.year, today.month,1), today + timedelta(days=1))
                    m_base = series_first_value(mser)
                    ytd = delta_pct(latest, y_base)
                    mtd = delta_pct(latest, m_base)
                    caption = f"YTD: {'–' if ytd is None else f'{ytd:+.2f}%'} | MTD: {'–' if mtd is None else f'{mtd:+.2f}%'}"
                    render_metric(name, val, f"{d1} (1d)", caption)
                    continue

                # Normale Yahoo-Ticker aus Gruppen-Batches
                s_hist = GRP_hist.get(tk)
                latest = series_last_value(s_hist)
                prev1d = get_prev_by_sessions(s_hist, 1)
                prev5d = get_prev_by_sessions(s_hist, 5)
                val = fmt_value(latest, kind)
                d1 = fmt_delta_pp_rate(latest, prev1d) if kind=="pct_rate" else fmt_delta_pct(latest, prev1d)
                d5 = (fmt_delta_pp_rate(latest, prev5d) if kind=="pct_rate" else fmt_delta_pct(latest, prev5d)) if prev5d is not None else "–"

                y_base = series_first_value(GRP_ytd.get(tk))
                m_base = series_first_value(GRP_mtd.get(tk))
                ytd = delta_pct(latest, y_base)
                mtd = delta_pct(latest, m_base)
                caption = f"Δ vs. 5d: {d5} | YTD: {'–' if (ytd is None or math.isnan(ytd)) else f'{ytd:+.2f}%'} | MTD: {'–' if (mtd is None or math.isnan(mtd)) else f'{mtd:+.2f}%'}"

                render_metric(name, val, f"{d1} (1d)", caption)