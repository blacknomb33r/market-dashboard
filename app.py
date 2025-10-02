import streamlit as st
import yfinance as yf
from datetime import date, timedelta
import pandas as pd
import math
from typing import Optional

# ================== PAGE ==================
st.set_page_config(page_title="Daily Market Dashboard", layout="wide")
st.title("Daily Market Dashboard")

# ================== SIDEBAR ==================
st.sidebar.header("Zeitraum")
period_choice = st.sidebar.selectbox(
    "Zeitraum",
    ["Live", "30 Tage", "90 Tage", "1 Jahr"],   # Live als Default
    index=0
)
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

# 1-Satz-Erklärungen (für ℹ️ Info)
DESCRIPTIONS = {
    # USA
    "S&P 500": "US-Blue-Chip-Index: 500 größte börsennotierte US-Unternehmen.",
    "Nasdaq": "Technologielastiger US-Index mit über 100 großen Firmen.",
    "US 10Y Yield": "Rendite 10-jähriger US-Staatsanleihen – wichtigster Zins-Benchmark.",
    "USD/JPY": "Wechselkurs US-Dollar gegen Japanischen Yen.",
    # Europa
    "DAX": "40 größte börsennotierte Unternehmen in Deutschland.",
    "EUR/USD": "Wechselkurs Euro gegen US-Dollar.",
    "DE 10Y Yield": "Rendite 10-jähriger deutscher Bundesanleihen.",
    "EuroStoxx50": "50 größte Unternehmen aus der Eurozone", 
    "FTSE100": "100 größte börsennotierte Unternehmen im Vereinigten Königreich.",
    # Rohstoffe
    "WTI Oil": "US-Rohöl (West Texas Intermediate) in USD pro Barrel.",
    "Gold": "Goldpreis in USD pro Feinunze.",
    "Silver": "Silberpreis in USD pro Feinunze.",
    "Platinum": "Platinpreis in USD pro Feinunze.",
    # Krypto
    "Bitcoin": "Größte Kryptowährung nach Marktkapitalisierung.",
    "Ethereum": "Zweitgrößte Kryptowährung; Plattform für Smart Contracts.",
    # Sentiment / Risiko
    "VIX": "Volatilitätsindex (S&P 500); misst erwartete Schwankungen.",
    "Put/Call Ratio": "Verhältnis Put- zu Call-Optionen (Sentiment-Indikator).",
}

# ================== HELPERS ==================
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
    # Prozentpunkte (für Renditen)
    if cur is None or prev is None:
        return "–"
    diff = cur - prev
    return f"{diff:+.2f} pp"

@st.cache_data(ttl=90)
def fetch_intraday_last(yfticker: str) -> Optional[float]:
    try:
        df = yf.Ticker(yfticker).history(period="1d", interval="1m")
        if df is None or df.empty or "Close" not in df.columns:
            return None
        return float(df["Close"].dropna().iloc[-1])
    except Exception:
        return None

@st.cache_data(ttl=1800)
def fetch_prev_daily_close(yfticker: str) -> Optional[float]:
    try:
        df = yf.Ticker(yfticker).history(period="7d", interval="1d")
        if df is None or df.empty or "Close" not in df.columns:
            return None
        closes = df["Close"].dropna()
        if len(closes) < 1:
            return None
        return float(closes.iloc[-1])   # letzter abgeschlossener Tages-Close
    except Exception:
        return None

@st.cache_data(ttl=3600)
def fetch_daily_series_range(yfticker: str, start_date: date, end_date: date) -> Optional[pd.Series]:
    try:
        df = yf.download(yfticker, start=start_date, end=end_date, auto_adjust=True, progress=False)
        if df is None or df.empty or "Close" not in df.columns:
            return None
        s = df["Close"].dropna()
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0].dropna()
        if len(s) < 1:
            return None
        return s.astype(float)
    except Exception:
        return None

def series_first_value(s: Optional[pd.Series]) -> Optional[float]:
    if s is None or s.empty:
        return None
    try:
        return float(s.iloc[0])
    except Exception:
        return None

def series_last_value(s: Optional[pd.Series]) -> Optional[float]:
    if s is None or s.empty:
        return None
    try:
        return float(s.iloc[-1])
    except Exception:
        return None

def get_prev_by_sessions(series: pd.Series, sessions_back: int) -> Optional[float]:
    idx = len(series) - (sessions_back + 1)
    if idx < 0:
        return None
    try:
        return float(series.iloc[idx])
    except Exception:
        return None

# ---- YTD / MTD (Daily-Basis) ----
@st.cache_data(ttl=1800)
def get_ytd_series(yfticker: str) -> Optional[pd.Series]:
    ystart = date(today.year, 1, 1)
    return fetch_daily_series_range(yfticker, ystart, today + timedelta(days=1))

@st.cache_data(ttl=1800)
def get_mtd_series(yfticker: str) -> Optional[pd.Series]:
    mstart = date(today.year, today.month, 1)
    return fetch_daily_series_range(yfticker, mstart, today + timedelta(days=1))

# ---- FRED: DE 10Y ----
from fredapi import Fred
fred_key = st.secrets.get("FRED_API_KEY", None)
fred = Fred(api_key=fred_key) if fred_key else None

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
    # Häufig genutzt: IRLTLT01DEM156N (langfr. 10y, oft Monatsfrequenz)
    return fred_series("IRLTLT01DEM156N", start_date, end_date)

def latest_de10y() -> Optional[float]:
    s = get_de10y_series(today - timedelta(days=400), today + timedelta(days=1))
    return series_last_value(s)

def prev_close_de10y() -> Optional[float]:
    s = get_de10y_series(today - timedelta(days=400), today + timedelta(days=1))
    if s is None or s.empty or len(s) < 2:
        return None
    return float(s.iloc[-2])

def ytd_mtd_de10y():
    yser = get_de10y_series(date(today.year,1,1), today + timedelta(days=1))
    mser = get_de10y_series(date(today.year, today.month,1), today + timedelta(days=1))
    return yser, mser

# ---- Info-Wrapper ----
def render_metric(name: str, value: str, delta: str, extra_caption: str = ""):
    st.metric(label=name, value=value, delta=delta)
    if extra_caption:
        st.caption(extra_caption)
    # Info-Expander (ℹ️)
    desc = DESCRIPTIONS.get(name)
    if desc:
        with st.expander("ℹ️ Info", expanded=False):
            st.write(desc)

# ================== RENDER ==================
for gi, (group_name, tickers) in enumerate(GROUPS.items()):
    st.subheader(group_name)
    cols = st.columns(3)

    for i, (name, meta) in enumerate(tickers.items()):
        yft = meta["ticker"]; kind = meta["fmt"]

        with cols[i % 3]:

            # ---- DE10Y via FRED ----
            if yft.startswith("FRED:"):
                if fred is None:
                    render_metric(name, "–", "FRED Key fehlt", "YTD: – | MTD: –")
                    continue

                cur = latest_de10y()
                prev = prev_close_de10y()
                val_str = fmt_value(cur, "pct_rate")
                d_live = fmt_delta_pp_rate(cur, prev)
                if period_choice == "Live":
                    delta_main = f"{d_live} (vs. Vortag)"
                else:
                    delta_main = d_live

                # YTD/MTD
                yser, mser = ytd_mtd_de10y()
                y_base = series_first_value(yser)
                m_base = series_first_value(mser)
                ytd = delta_pct(cur, y_base)
                mtd = delta_pct(cur, m_base)
                ytxt = "–" if (ytd is None or math.isnan(ytd)) else f"{ytd:+.2f}%"
                mtxt = "–" if (mtd is None or math.isnan(mtd)) else f"{mtd:+.2f}%"
                caption = f"YTD: {ytxt} | MTD: {mtxt}"

                render_metric(name, val_str, delta_main, caption)
                continue

            # ---- Normale Yahoo-Ticker ----
            if period_choice == "Live":
                cur = fetch_intraday_last(yft)
                prev_close = fetch_prev_daily_close(yft)
                val_str = fmt_value(cur, kind)
                # Delta: Renditen in pp, sonst %
                if kind == "pct_rate":
                    d_live = fmt_delta_pp_rate(cur, prev_close)
                else:
                    d_live = fmt_delta_pct(cur, prev_close)
                delta_main = f"{d_live} (vs. Vortag)"

                # YTD/MTD
                yser = get_ytd_series(yft)
                mser = get_mtd_series(yft)
                y_base = series_first_value(yser)
                m_base = series_first_value(mser)
                ytd = delta_pct(cur, y_base)
                mtd = delta_pct(cur, m_base)
                ytxt = "–" if (ytd is None or math.isnan(ytd)) else f"{ytd:+.2f}%"
                mtxt = "–" if (mtd is None or math.isnan(mtd)) else f"{mtd:+.2f}%"
                caption = f"YTD: {ytxt} | MTD: {mtxt}"

                render_metric(name, val_str, delta_main, caption)

            else:
                s = fetch_daily_series_range(yft, start, today + timedelta(days=1))
                if s is None or s.empty:
                    render_metric(name, "–", "–", "YTD: – | MTD: –")
                    continue

                latest = series_last_value(s)
                prev1d = get_prev_by_sessions(s, 1)
                prev5d = get_prev_by_sessions(s, 5)
                val_str = fmt_value(latest, kind)

                # 1d-Delta
                if kind == "pct_rate":
                    d1 = fmt_delta_pp_rate(latest, prev1d) if prev1d is not None else "–"
                else:
                    d1 = fmt_delta_pct(latest, prev1d) if prev1d is not None else "–"
                delta_main = f"{d1} (1d)"

                # 5d optional
                if prev5d is not None:
                    if kind == "pct_rate":
                        d5 = fmt_delta_pp_rate(latest, prev5d)
                    else:
                        d5 = fmt_delta_pct(latest, prev5d)
                    five_d_text = f"Δ vs. 5d: {d5}"
                else:
                    five_d_text = "Δ vs. 5d: –"

                # YTD / MTD
                yser = get_ytd_series(yft)
                mser = get_mtd_series(yft)
                y_base = series_first_value(yser)
                m_base = series_first_value(mser)
                ytd = delta_pct(latest, y_base)
                mtd = delta_pct(latest, m_base)
                ytxt = "–" if (ytd is None or math.isnan(ytd)) else f"{ytd:+.2f}%"
                mtxt = "–" if (mtd is None or math.isnan(mtd)) else f"{mtd:+.2f}%"

                caption = f"{five_d_text} | YTD: {ytxt} | MTD: {mtxt}"
                render_metric(name, val_str, delta_main, caption)

    # Trennlinie zwischen Gruppen (außer nach letzter)
    if gi < len(GROUPS) - 1:
        st.divider()

st.caption("Hinweis: 'Live' nutzt Intraday-Daten (Yahoo ~15 Min Verzögerung). DE10Y via FRED (Serie IRLTLT01DEM156N; häufig Monatsdaten).")