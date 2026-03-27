import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, date

st.set_page_config(page_title="NSE Insider Radar", layout="wide")

# ─────────────────────────────────────────────
# NSE SESSION HANDLER
# ─────────────────────────────────────────────
def get_nse_session():
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9"
    }
    session.get("https://www.nseindia.com", headers=headers)
    return session

# ─────────────────────────────────────────────
# BULK DEALS
# ─────────────────────────────────────────────
def fetch_bulk(session, from_date, to_date):
    url = f"https://www.nseindia.com/api/historicalOR/bulk-deals?from={from_date}&to={to_date}"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.nseindia.com"}

    r = session.get(url, headers=headers)
    data = r.json()

    result = []
    for row in data.get("data", []):
        try:
            result.append({
                "source": "Bulk",
                "symbol": row["symbol"],
                "insider": row["clientName"],
                "type": row["buySell"],
                "shares": float(row["quantity"]),
                "price": float(row["price"]),
                "value_cr": (float(row["quantity"]) * float(row["price"])) / 1e7,
                "date": row["date"]
            })
        except:
            continue
    return result

# ─────────────────────────────────────────────
# BLOCK DEALS
# ─────────────────────────────────────────────
def fetch_block(session, from_date, to_date):
    url = f"https://www.nseindia.com/api/historicalOR/block-deals?from={from_date}&to={to_date}"
    headers = {"User-Agent": "Mozilla/5.0"}

    r = session.get(url, headers=headers)
    data = r.json()

    result = []
    for row in data.get("data", []):
        try:
            result.append({
                "source": "Block",
                "symbol": row["symbol"],
                "insider": row["clientName"],
                "type": row["buySell"],
                "shares": float(row["quantity"]),
                "price": float(row["price"]),
                "value_cr": (float(row["quantity"]) * float(row["price"])) / 1e7,
                "date": row["date"]
            })
        except:
            continue
    return result

# ─────────────────────────────────────────────
# SAST (INSIDER)
# ─────────────────────────────────────────────
def fetch_sast(session):
    url = "https://www.nseindia.com/api/corporates-pit"
    headers = {"User-Agent": "Mozilla/5.0"}

    r = session.get(url, headers=headers)
    data = r.json()

    result = []
    for row in data.get("data", []):
        try:
            result.append({
                "source": "SAST",
                "symbol": row["symbol"],
                "insider": row["personCategory"],
                "type": "BUY" if "Buy" in str(row.get("acqMode")) else "SELL",
                "shares": float(row.get("secAcq", 0)),
                "price": 0,
                "value_cr": 0,
                "date": row.get("acqtoDt")
            })
        except:
            continue
    return result

# ─────────────────────────────────────────────
# LIVE PRICE
# ─────────────────────────────────────────────
def get_price(session, symbol):
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = session.get(url, headers=headers)
        return r.json()["priceInfo"]["lastPrice"]
    except:
        return None

# ─────────────────────────────────────────────
# CACHE WRAPPER
# ─────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data(from_date, to_date):
    session = get_nse_session()

    bulk  = fetch_bulk(session, from_date, to_date)
    block = fetch_block(session, from_date, to_date)
    sast  = fetch_sast(session)

    df = pd.DataFrame(bulk + block + sast)

    if df.empty:
        return df

    # Live prices (limited to avoid blocking)
    prices = {}
    for sym in df["symbol"].unique()[:20]:
        prices[sym] = get_price(session, sym)
        time.sleep(0.3)

    df["live_price"] = df["symbol"].map(prices)

    return df

# ─────────────────────────────────────────────
# ALERT ENGINE
# ─────────────────────────────────────────────
def generate_alerts(df):
    alerts = []

    for _, r in df.iterrows():
        if r["type"] == "BUY" and r["value_cr"] > 10:
            alerts.append(f"🚨 BIG BUY: {r['symbol']} ₹{r['value_cr']:.1f} Cr")

        if r["source"] == "SAST":
            alerts.append(f"🧠 INSIDER TRADE: {r['symbol']}")

    return alerts

# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────
st.title("📡 NSE Insider Radar (Real Data)")

col1, col2 = st.columns(2)
with col1:
    from_date = st.date_input("From", value=date.today())
with col2:
    to_date = st.date_input("To", value=date.today())

if st.button("Fetch Data"):
    df = load_data(
        from_date.strftime("%d-%m-%Y"),
        to_date.strftime("%d-%m-%Y")
    )

    if df.empty:
        st.warning("No data found")
        st.stop()

    st.success(f"Loaded {len(df)} records")

    # Alerts
    alerts = generate_alerts(df)
    for a in alerts[:10]:
        st.warning(a)

    # Table
    st.dataframe(df, use_container_width=True)

    # Charts
    st.subheader("Buy vs Sell Value")
    chart = df.groupby(["type"])["value_cr"].sum()
    st.bar_chart(chart)

    st.subheader("Source Distribution")
    chart2 = df.groupby(["source"]).size()
    st.bar_chart(chart2)
