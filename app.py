import streamlit as st
import yfinance as yf
from datetime import date, timedelta, datetime
import pandas as pd
import math
from typing import Optional

# ========== PAGE ==========
st.set_page_config(page_title="Daily Market Dashboard", layout="wide")
st.title("📊 Daily Market Dashboard (KPI only)")

# ========== SIDEBAR ==========
st.sidebar.header("Zeitraum")
period_choice = st.sidebar.selectbox(
    "Zeitraum",
    ["Live", "30 Tage", "90 Tage", "1 Jahr"],
    index=0
)
days_map = {"30 Tage": 30, "90 Tage": 90, "1 Jahr": 365}
today = date.today()
start = today - timedelta(days=days_map.get(period_choice, 30))

# ========== GROUPS ==========
GROUPS = {
    "🇺🇸 USA": {
        "S&P 500": {"ticker": "^GSPC", "fmt": "idx"},
        "Nasdaq": {"ticker": "^IXIC", "fmt": "idx"},
        "US 10Y Yield": {"ticker": "^TNX", "fmt": "pct_tnx"},  # *10 skaliert
        "USD/JPY": {"ticker": "JPY=X", "fmt": "fx"},
    },
    "🇪🇺 Europa": {
        "DAX": {"ticker": "^GDAXI", "fmt": "idx"},
        "EUR/USD": {"ticker": "EURUSD=X", "fmt": "fx"},
        # DE10Y via FRED (separat, ohne yfinance)
        "DE 10Y Yield": {"ticker": "FRED:DE10Y", "fmt": "pct_yield"}, 
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
    "📉 Index": {
        "VIX": {"ticker": "^VIX", "fmt": "idx"},
        "Put/Call Ratio": {"ticker": "^CPC", "fmt": "idx"},
    },
}

# ========== HELPERS ==========
def fmt_value(x: Optional[float], kind: str) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "–"
    if kind in ["pct_tnx", "pct_yield"]:   # beide normal in %
        return f"{x:.2f}%"
    if kind == "fx":
        return f"{x:.4f}"
    return f"{x:.2f}"

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

def fmt_delta_pp_yield(cur: Optional[float], prev: Optional[float]) -> str:
    # normale Prozentwerte (z. B. DE10Y)
    if cur is None or prev is None:
        return "–"
    diff_pp = cur - prev
    return f"{diff_pp:+.2f} pp"

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
    """Letzter abgeschlossener Tages-Close (gestern/letzte Sitzung)."""
    try:
        df = yf.Ticker(yfticker).history(period="7d", interval="1d")
        if df is None or df.empty or "Close" not in df.columns:
            return None
        closes = df["Close"].dropna()
        if len(closes) < 1:
            return None
        # letzter Eintrag = letzter abgeschlossener Close
        return float(closes.iloc[-1])
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

# ---- YTD / MTD series fetchers (yfinance) ----
@st.cache_data(ttl=1800)
def get_ytd_series(yfticker: str) -> Optional[pd.Series]:
    ystart = date(today.year, 1, 1)
    return fetch_daily_series_range(yfticker, ystart, today + timedelta(days=1))

@st.cache_data(ttl=1800)
def get_mtd_series(yfticker: str) -> Optional[pd.Series]:
    mstart = date(today.year, today.month, 1)
    return fetch_daily_series_range(yfticker, mstart, today + timedelta(days=1))

# ---- FRED: DE10Y ----
# Du brauchst einen FRED API Key in Streamlit Secrets: FRED_API_KEY = "..."
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
    """
    DE 10Y Rendite. Häufige FRED-Serien:
      - IRLTLT01DEM156N (Long-Term Government Bond Yields: 10-year: Main series for Germany)
      - DGS10 (US) – nur als Referenz
    """
    # Primär versuchen wir IRLTLT01DEM156N (Monatswerte). Alternativ kannst du andere IDs testen.
    s = fred_series("IRLTLT01DEM156N", start_date, end_date)
    return s

def latest_de10y() -> Optional[float]:
    s = get_de10y_series(today - timedelta(days=400), today + timedelta(days=1))
    return series_last_value(s)

def prev_close_de10y() -> Optional[float]:
    s = get_de10y_series(today - timedelta(days=400), today + timedelta(days=1))
    if s is None or s.empty:
        return None
    if len(s) < 2:
        return None
    return float(s.iloc[-2])

def ytd_mtd_de10y():
    yser = get_de10y_series(date(today.year,1,1), today + timedelta(days=1))
    mser = get_de10y_series(date(today.year, today.month,1), today + timedelta(days=1))
    return yser, mser

# ========== RENDER ==========
for gi, (group_name, tickers) in enumerate(GROUPS.items()):
    st.subheader(group_name)
    cols = st.columns(3)

    for i, (name, meta) in enumerate(tickers.items()):
        yft = meta["ticker"]; kind = meta["fmt"]
        with cols[i % 3]:

            # ----- Spezialfall: DE10Y via FRED -----
            if yft.startswith("FRED:"):
                if fred is None:
                    st.metric(label=name, value="–", delta="FRED API Key fehlt")
                    st.caption("YTD: – | MTD: –")
                    continue

                cur = latest_de10y()
                prev = prev_close_de10y()
                # Live vs Vortag (monthly series -> oft letzte verfügbare Periode)
                value_str = fmt_value(cur, "pct_yield")
                delta_str = fmt_delta_pp_yield(cur, prev)
                if period_choice == "Live":
                    st.metric(label=name, value=value_str, delta=f"{delta_str} (vs. Vortag)")
                else:
                    # 1d im historischen Sinn gibt es hier nicht fein aufgelöst -> zeige einfach Δ vs. Prev
                    st.metric(label=name, value=value_str, delta=f"{delta_str}")

                # YTD / MTD
                yser, mser = ytd_mtd_de10y()
                y_base = series_first_value(yser)
                m_base = series_first_value(mser)
                ytd = (cur - y_base) / y_base * 100 if cur is not None and y_base not in (None, 0) else None
                mtd = (cur - m_base) / m_base * 100 if cur is not None and m_base not in (None, 0) else None
                ytxt = "–" if ytd is None or math.isnan(ytd) else f"{ytd:+.2f}%"
                mtxt = "–" if mtd is None or math.isnan(mtd) else f"{mtd:+.2f}%"
                st.caption(f"YTD: {ytxt} | MTD: {mtxt}")
                continue

            # ----- normale yfinance Ticker -----
            if period_choice == "Live":
                cur = fetch_intraday_last(yft)
                prev_close = fetch_prev_daily_close(yft)
                value_str = fmt_value(cur, kind)

                if kind == "pct_tnx":
                    delta_live = fmt_delta_pp_tnx(cur, prev_close)
                elif kind == "pct_yield":
                    delta_live = fmt_delta_pp_yield(cur, prev_close)
                else:
                    delta_live = fmt_delta_pct(cur, prev_close)

                st.metric(label=name, value=value_str, delta=f"{delta_live} (vs. Vortag)")

                # YTD / MTD mit Daily-Serien
                yser = get_ytd_series(yft)
                mser = get_mtd_series(yft)
                y_base = series_first_value(yser)
                m_base = series_first_value(mser)

                # Für ^TNX / Yields: YTD/MTD als % Veränderung gegenüber Basis (nicht pp)
                if kind == "pct_tnx":
                    cur_pct = (cur/10) if cur is not None else None
                    y_base_val = (y_base/10) if y_base is not None else None
                    m_base_val = (m_base/10) if m_base is not None else None
                    ytd = delta_pct(cur_pct, y_base_val)
                    mtd = delta_pct(cur_pct, m_base_val)
                else:
                    ytd = delta_pct(cur, y_base)
                    mtd = delta_pct(cur, m_base)

                ytxt = "–" if (ytd is None or math.isnan(ytd)) else f"{ytd:+.2f}%"
                mtxt = "–" if (mtd is None or math.isnan(mtd)) else f"{mtd:+.2f}%"
                st.caption(f"YTD: {ytxt} | MTD: {mtxt}")

            else:
                # Historisch: 1d-Metric + 5d in Caption
                s = fetch_daily_series_range(yft, start, today + timedelta(days=1))
                if s is None or s.empty:
                    st.metric(label=name, value="–", delta="–")
                    st.caption("YTD: – | MTD: –")
                    continue

                latest = series_last_value(s)
                prev1d = get_prev_by_sessions(s, 1)
                prev5d = get_prev_by_sessions(s, 5)
                value_str = fmt_value(latest, kind)

                if kind == "pct_tnx":
                    delta1d = fmt_delta_pp_tnx(latest, prev1d) if prev1d is not None else "–"
                elif kind == "pct_yield":
                    delta1d = fmt_delta_pp_yield(latest, prev1d) if prev1d is not None else "–"
                else:
                    delta1d = fmt_delta_pct(latest, prev1d) if prev1d is not None else "–"

                st.metric(label=name, value=value_str, delta=f"{delta1d} (1d)")

                # 5d optional
                if prev5d is not None:
                    if kind == "pct_tnx":
                        d5 = fmt_delta_pp_tnx(latest, prev5d)
                    elif kind == "pct_yield":
                        d5 = fmt_delta_pp_yield(latest, prev5d)
                    else:
                        d5 = fmt_delta_pct(latest, prev5d)
                    st.caption(f"Δ vs. 5d: {d5}")
                else:
                    st.caption("Δ vs. 5d: –")

                # YTD / MTD (auf Daily-Basis)
                yser = get_ytd_series(yft)
                mser = get_mtd_series(yft)
                y_base = series_first_value(yser)
                m_base = series_first_value(mser)

                if kind == "pct_tnx":
                    latest_pct = (latest/10) if latest is not None else None
                    y_base_val = (y_base/10) if y_base is not None else None
                    m_base_val = (m_base/10) if m_base is not None else None
                    ytd = delta_pct(latest_pct, y_base_val)
                    mtd = delta_pct(latest_pct, m_base_val)
                else:
                    ytd = delta_pct(latest, y_base)
                    mtd = delta_pct(latest, m_base)

                ytxt = "–" if (ytd is None or math.isnan(ytd)) else f"{ytd:+.2f}%"
                mtxt = "–" if (mtd is None or math.isnan(mtd)) else f"{mtd:+.2f}%"
                st.caption(f"YTD: {ytxt} | MTD: {mtxt}")

    # Divider zwischen Gruppen (nicht nach letzter)
    if gi < len(GROUPS) - 1:
        st.divider()

st.caption("Hinweis: 'Live' nutzt Intraday-Daten (Yahoo ~15 Min Verzögerung). DE10Y via FRED.")