import streamlit as st
import json
import pandas as pd
import requests
from datetime import datetime

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="NSE Insider Radar", page_icon="📡", layout="wide", initial_sidebar_state="expanded")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;600;700&display=swap');
html,body,[class*="css"]{font-family:'IBM Plex Mono',monospace;}
.stApp{background-color:#0a0d12;color:#e2e8f0;}
[data-testid="stSidebar"]{background-color:#0d1117!important;border-right:1px solid #1e293b;}
.nse-header{display:flex;align-items:center;gap:16px;padding:12px 0 24px 0;border-bottom:1px solid #1e293b;margin-bottom:24px;}
.nse-accent-bar{width:8px;height:40px;background:linear-gradient(180deg,#f6ad55,#ed8936);border-radius:2px;flex-shrink:0;}
.nse-title{font-family:'Space Grotesk',sans-serif;font-size:26px;font-weight:700;color:#f1f5f9;letter-spacing:-0.02em;margin:0;}
.nse-subtitle{font-size:11px;color:#475569;letter-spacing:0.1em;margin-top:2px;}
.metric-card{background:#0d1117;border:1px solid #1e293b;border-radius:6px;padding:18px 20px;}
.metric-label{font-size:9px;color:#475569;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:6px;}
.metric-value{font-family:'Space Grotesk',sans-serif;font-size:24px;font-weight:700;}
.metric-sub{font-size:10px;color:#374151;margin-top:2px;}
.chip-buy{display:inline-block;background:rgba(74,222,128,0.12);color:#4ade80;border:1px solid rgba(74,222,128,0.25);padding:2px 10px;border-radius:3px;font-size:11px;font-weight:600;}
.chip-sell{display:inline-block;background:rgba(248,113,113,0.12);color:#f87171;border:1px solid rgba(248,113,113,0.25);padding:2px 10px;border-radius:3px;font-size:11px;font-weight:600;}
.chip-high{display:inline-block;background:rgba(246,173,85,0.15);color:#f6ad55;border:1px solid rgba(246,173,85,0.3);padding:2px 10px;border-radius:3px;font-size:11px;font-weight:600;}
.chip-medium{display:inline-block;background:rgba(147,197,253,0.1);color:#93c5fd;border:1px solid rgba(147,197,253,0.2);padding:2px 10px;border-radius:3px;font-size:11px;font-weight:600;}
.chip-low{display:inline-block;background:rgba(100,116,139,0.1);color:#64748b;border:1px solid rgba(100,116,139,0.2);padding:2px 10px;border-radius:3px;font-size:11px;font-weight:600;}
.detail-card{background:#0d1117;border:1px solid #1e293b;border-radius:6px;padding:16px 18px;margin-bottom:12px;}
.detail-label{font-size:9px;color:#475569;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:6px;}
.detail-value{font-size:13px;font-weight:600;color:#e2e8f0;}
.ticker-badge{display:inline-block;font-size:10px;background:#1a2235;border:1px solid #2d3748;padding:1px 7px;border-radius:2px;color:#93c5fd;letter-spacing:0.06em;}
.stButton>button{background:#f6ad55!important;color:#0a0d12!important;border:none!important;font-family:'IBM Plex Mono',monospace!important;font-weight:700!important;letter-spacing:0.08em!important;border-radius:3px!important;}
.stButton>button:hover{background:#ed8936!important;}
</style>
""", unsafe_allow_html=True)

# ── Prompt ────────────────────────────────────────────────────────────────────
PROMPT_BASE = """You are a financial data analyst for NSE India.
Return ONLY a valid JSON array, no markdown, no backticks, no explanation whatsoever.
Generate 15 realistic, plausible NSE insider/promoter/bulk deal transaction entries.
Mix BUY and SELL transactions. Use well-known NSE-listed companies across IT, Banking, FMCG, Pharma, Auto, Energy, Metals, Infra.

Each object must have exactly these keys:
company, symbol, sector, insider_name, designation, transaction_type (BUY or SELL),
shares (integer), price_per_share (float), total_value_cr (float),
transaction_date (DD-MMM-YYYY), pre_holding_pct (float), post_holding_pct (float),
significance (HIGH / MEDIUM / LOW), rationale (string)
"""

# ── Gemini API call ───────────────────────────────────────────────────────────
def fetch_data(api_key: str, extra: str = "") -> list:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    full_prompt = PROMPT_BASE + ("\n\nExtra instructions: " + extra if extra.strip() else "")
    payload = {
        "contents": [{"role": "user", "parts": [{"text": full_prompt}]}],
        "generationConfig": {"temperature": 0.8, "maxOutputTokens": 4096}
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)

# ── Session state ─────────────────────────────────────────────────────────────
for k, v in [("data", []), ("last_updated", None), ("selected_row", None)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<div style='font-family:Space Grotesk,sans-serif;font-size:18px;font-weight:700;color:#f1f5f9;padding:8px 0 4px 0;'>⚡ NSE Insider Radar</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:10px;color:#475569;letter-spacing:0.1em;margin-bottom:16px;'>POWERED BY GOOGLE GEMINI (FREE)</div>", unsafe_allow_html=True)

    # Load from secrets if available, else show input
    api_key = ""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        pass
    if api_key:
        st.success("✓ API key loaded from secrets")
    else:
        api_key = st.text_input("Gemini API Key", type="password", placeholder="AIzaSy...")
        st.markdown("""<div style='font-size:10px;color:#475569;line-height:1.8;margin-bottom:4px;'>
        🆓 <b style='color:#4ade80;'>FREE</b> — 1,500 req/day<br>
        Get key → <a href='https://aistudio.google.com/apikey' target='_blank' style='color:#93c5fd;'>aistudio.google.com/apikey</a>
        </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("<div style='font-size:10px;color:#475569;letter-spacing:0.1em;margin-bottom:10px;'>FILTERS</div>", unsafe_allow_html=True)
    txn_filter    = st.selectbox("Type",   ["All","BUY","SELL"])
    sig_filter    = st.selectbox("Signal", ["All","HIGH","MEDIUM","LOW"])
    sector_filter = st.selectbox("Sector", ["All","IT","Banking","FMCG","Pharma","Auto","Energy","Metals","Infra"])
    search_query  = st.text_input("Search", placeholder="Company / Symbol / Insider...")

    st.divider()
    st.markdown("<div style='font-size:10px;color:#475569;letter-spacing:0.1em;margin-bottom:6px;'>CUSTOM QUERY</div>", unsafe_allow_html=True)
    custom_prompt = st.text_area("", placeholder="e.g. Only pharma promoter buys above ₹50 Cr...", height=80, label_visibility="collapsed")
    fetch_btn = st.button("↻  FETCH DATA", use_container_width=True)

    if st.session_state.last_updated:
        st.caption(f"Last updated: {st.session_state.last_updated.strftime('%H:%M:%S')}")

    st.divider()
    st.markdown("<div style='font-size:9px;color:#374151;line-height:1.6;'>⚠️ AI-generated demo data. For production, connect NSE/BSE official SAST disclosure APIs.</div>", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="nse-header">
  <div class="nse-accent-bar"></div>
  <div>
    <div class="nse-title">NSE INSIDER RADAR</div>
    <div class="nse-subtitle">MANAGEMENT TRANSACTIONS · BULK DEALS · PROMOTER ACTIVITY</div>
  </div>
</div>""", unsafe_allow_html=True)

# ── Fetch ─────────────────────────────────────────────────────────────────────
if fetch_btn:
    if not api_key:
        st.error("Please enter your Gemini API key in the sidebar.")
    else:
        with st.spinner("Scanning NSE filings via Gemini..."):
            try:
                st.session_state.data = fetch_data(api_key, custom_prompt)
                st.session_state.last_updated = datetime.now()
                st.session_state.selected_row = None
                st.success(f"✓ Loaded {len(st.session_state.data)} transactions.")
            except Exception as e:
                st.error(f"Error: {e}")

# ── Filter ────────────────────────────────────────────────────────────────────
data = st.session_state.data
raw  = pd.DataFrame(data)
df   = raw.copy()

if not df.empty:
    if txn_filter    != "All": df = df[df["transaction_type"] == txn_filter]
    if sig_filter    != "All": df = df[df["significance"]     == sig_filter]
    if sector_filter != "All": df = df[df["sector"]           == sector_filter]
    if search_query:
        q  = search_query.lower()
        df = df[df["company"].str.lower().str.contains(q, na=False) |
                df["symbol"].str.lower().str.contains(q, na=False)  |
                df["insider_name"].str.lower().str.contains(q, na=False)]

# ── Stats ─────────────────────────────────────────────────────────────────────
total    = len(raw)
buy_val  = raw[raw["transaction_type"]=="BUY"]["total_value_cr"].sum()  if not raw.empty else 0
sell_val = raw[raw["transaction_type"]=="SELL"]["total_value_cr"].sum() if not raw.empty else 0
high_sig = len(raw[raw["significance"]=="HIGH"])                        if not raw.empty else 0

c1,c2,c3,c4 = st.columns(4)
for col, lbl, val, sub, clr in [
    (c1,"TOTAL TRANSACTIONS", total,                "tracked entries",  "#f1f5f9"),
    (c2,"BUY VALUE",          f"₹{buy_val:.1f} Cr", "accumulation",    "#4ade80"),
    (c3,"SELL VALUE",         f"₹{sell_val:.1f} Cr","distribution",    "#f87171"),
    (c4,"HIGH SIGNIFICANCE",  high_sig,             "flagged trades",   "#f6ad55"),
]:
    with col:
        st.markdown(f"<div class='metric-card'><div class='metric-label'>{lbl}</div><div class='metric-value' style='color:{clr};'>{val}</div><div class='metric-sub'>{sub}</div></div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Empty states ──────────────────────────────────────────────────────────────
if df.empty and not data:
    st.markdown("""
    <div style='text-align:center;padding:80px 0;'>
      <div style='font-size:40px;margin-bottom:16px;'>📡</div>
      <div style='font-size:14px;color:#475569;letter-spacing:0.1em;'>ENTER YOUR GEMINI API KEY AND CLICK FETCH DATA</div>
      <div style='font-size:11px;color:#374151;margin-top:8px;'>Completely free · 1,500 requests/day · No credit card needed</div>
    </div>""", unsafe_allow_html=True)
    st.stop()
elif df.empty:
    st.info("No transactions match your current filters.")
    st.stop()

# ── Table + Detail ────────────────────────────────────────────────────────────
left_col, right_col = st.columns([3, 1.2])

with left_col:
    st.markdown(f"<div style='font-size:10px;color:#475569;letter-spacing:0.1em;margin-bottom:10px;'>SHOWING {len(df)} TRANSACTIONS · CLICK INSPECT TO VIEW DETAILS</div>", unsafe_allow_html=True)

    sc, sdc = st.columns([2,1])
    with sc:  sort_by  = st.selectbox("Sort", ["total_value_cr","shares","price_per_share","significance","transaction_date"], label_visibility="collapsed")
    with sdc: sort_asc = st.selectbox("Dir",  ["Descending","Ascending"], label_visibility="collapsed") == "Ascending"

    df_s = df.sort_values(sort_by, ascending=sort_asc).reset_index(drop=True)

    for i, row in df_s.iterrows():
        is_buy    = row["transaction_type"] == "BUY"
        sig       = row["significance"]
        sig_chip  = "<span class='chip-high'>⚡ HIGH</span>" if sig=="HIGH" else "<span class='chip-medium'>◆ MED</span>" if sig=="MEDIUM" else "<span class='chip-low'>· LOW</span>"
        txn_chip  = "<span class='chip-buy'>▲ BUY</span>" if is_buy else "<span class='chip-sell'>▼ SELL</span>"
        val_color = "#4ade80" if is_buy else "#f87171"

        st.markdown(f"""
        <div style='background:#0d1117;border:1px solid #1e293b;border-radius:5px;padding:14px 18px;margin-bottom:6px;'>
          <div style='display:flex;justify-content:space-between;'>
            <div>
              <span style='font-weight:700;color:#f1f5f9;font-size:13px;'>{row['company']}</span>
              &nbsp;<span class='ticker-badge'>{row['symbol']}</span>
              &nbsp;<span style='font-size:10px;color:#475569;'>{row['sector']}</span>
            </div>
            <div>{txn_chip}&nbsp;{sig_chip}</div>
          </div>
          <div style='display:flex;gap:24px;margin-top:10px;flex-wrap:wrap;'>
            <div><div style='font-size:9px;color:#475569;'>INSIDER</div><div style='font-size:11px;color:#cbd5e1;'>{row['insider_name']}</div></div>
            <div><div style='font-size:9px;color:#475569;'>SHARES</div><div style='font-size:11px;color:#94a3b8;'>{int(row['shares']):,}</div></div>
            <div><div style='font-size:9px;color:#475569;'>PRICE</div><div style='font-size:11px;color:#94a3b8;'>₹{row['price_per_share']:,.2f}</div></div>
            <div><div style='font-size:9px;color:#475569;'>VALUE</div><div style='font-size:12px;font-weight:700;color:{val_color};'>₹{row['total_value_cr']:.2f} Cr</div></div>
            <div><div style='font-size:9px;color:#475569;'>HOLDING</div><div style='font-size:11px;color:#e2e8f0;'>{row['pre_holding_pct']:.2f}% → <b>{row['post_holding_pct']:.2f}%</b></div></div>
            <div><div style='font-size:9px;color:#475569;'>DATE</div><div style='font-size:11px;color:#64748b;'>{row['transaction_date']}</div></div>
          </div>
        </div>""", unsafe_allow_html=True)
        if st.button("Inspect →", key=f"r_{i}"):
            st.session_state.selected_row = row.to_dict()

with right_col:
    sel = st.session_state.selected_row
    if sel:
        is_buy    = sel["transaction_type"] == "BUY"
        val_color = "#4ade80" if is_buy else "#f87171"
        sig       = sel["significance"]
        sig_color = "#f6ad55" if sig=="HIGH" else "#93c5fd" if sig=="MEDIUM" else "#64748b"

        st.markdown(f"""
        <div style='border-left:3px solid {val_color};padding-left:14px;margin-bottom:16px;'>
          <div style='font-family:Space Grotesk,sans-serif;font-size:15px;font-weight:700;color:#f1f5f9;'>{sel['company']}</div>
          <span class='ticker-badge'>{sel['symbol']}</span>
          <span style='font-size:10px;color:#475569;margin-left:8px;'>{sel['sector']}</span>
        </div>""", unsafe_allow_html=True)

        for label, val, clr in [
            ("INSIDER",     sel["insider_name"],                            None),
            ("DESIGNATION", sel["designation"],                             None),
            ("TYPE",        "▲ BUY" if is_buy else "▼ SELL",               val_color),
            ("DATE",        sel["transaction_date"],                        None),
            ("SHARES",      f"{int(sel['shares']):,}",                      None),
            ("PRICE",       f"₹{sel['price_per_share']:,.2f}",              None),
            ("TOTAL VALUE", f"₹{sel['total_value_cr']:.2f} Cr",            val_color),
            ("SIGNAL",      sig,                                            sig_color),
        ]:
            st.markdown(f"<div class='detail-card'><div class='detail-label'>{label}</div><div class='detail-value' style='color:{clr or '#e2e8f0'};'>{val}</div></div>", unsafe_allow_html=True)

        pre  = sel["pre_holding_pct"]
        post = sel["post_holding_pct"]
        pct  = min(100, int((post / max(post, pre, 1)) * 100))
        st.markdown(f"""<div class='detail-card'>
          <div class='detail-label'>HOLDING CHANGE</div>
          <div style='display:flex;align-items:center;gap:8px;margin-top:6px;'>
            <span style='font-size:12px;color:#64748b;'>{pre:.2f}%</span>
            <div style='flex:1;height:4px;background:#1e293b;border-radius:2px;'>
              <div style='width:{pct}%;height:100%;background:{val_color};border-radius:2px;'></div>
            </div>
            <span style='font-size:13px;font-weight:700;color:#f1f5f9;'>{post:.2f}%</span>
          </div>
        </div>""", unsafe_allow_html=True)

        st.markdown(f"<div class='detail-card'><div class='detail-label'>ANALYST RATIONALE</div><div style='font-size:11px;color:#94a3b8;line-height:1.6;margin-top:4px;'>{sel['rationale']}</div></div>", unsafe_allow_html=True)

        if st.button("✕ Close"):
            st.session_state.selected_row = None
            st.rerun()
    else:
        st.markdown("""
        <div style='background:#0d1117;border:1px solid #1e293b;border-radius:6px;padding:40px 20px;text-align:center;'>
          <div style='font-size:28px;margin-bottom:12px;'>🔍</div>
          <div style='font-size:11px;color:#475569;letter-spacing:0.08em;'>CLICK "INSPECT →"<br>ON ANY ROW</div>
        </div>""", unsafe_allow_html=True)

# ── Charts ────────────────────────────────────────────────────────────────────
st.markdown("<br><hr style='border-color:#1e293b;'>", unsafe_allow_html=True)
st.markdown("<div style='font-size:10px;color:#475569;letter-spacing:0.12em;margin-bottom:16px;'>ANALYTICS</div>", unsafe_allow_html=True)
ch1, ch2 = st.columns(2)
with ch1:
    st.markdown("<div style='font-size:11px;color:#94a3b8;margin-bottom:8px;'>BUY vs SELL VALUE BY SECTOR (₹ Cr)</div>", unsafe_allow_html=True)
    sd = raw.groupby(["sector","transaction_type"])["total_value_cr"].sum().reset_index()
    if not sd.empty:
        p = sd.pivot(index="sector", columns="transaction_type", values="total_value_cr").fillna(0)
        p.columns.name = None
        st.bar_chart(p)
with ch2:
    st.markdown("<div style='font-size:11px;color:#94a3b8;margin-bottom:8px;'>TRANSACTION COUNT BY SIGNIFICANCE</div>", unsafe_allow_html=True)
    sd2 = raw.groupby(["significance","transaction_type"]).size().reset_index(name="count")
    if not sd2.empty:
        p2 = sd2.pivot(index="significance", columns="transaction_type", values="count").fillna(0)
        p2.columns.name = None
        st.bar_chart(p2)
