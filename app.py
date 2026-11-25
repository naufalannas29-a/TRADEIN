import streamlit as st
import sqlite3, pandas as pd, os, calendar
import psycopg
from datetime import datetime, date, timedelta
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "trades.db"
DATABASE_URL = st.secrets.get("database", {}).get("url", "") if hasattr(st, "secrets") else ""
CLOUD_DB = bool(DATABASE_URL)
UPLOAD_DIR = APP_DIR / "screenshots"
UPLOAD_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Tradein | Trading Journal", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

# Optional private access gate. Configure [auth].password in Streamlit secrets.
AUTH_PASSWORD = st.secrets.get("auth", {}).get("password", "") if hasattr(st, "secrets") else ""
if AUTH_PASSWORD:
    if not st.session_state.get("tradein_authenticated", False):
        st.markdown("<h1>◈ TRADEIN</h1><p>Private Trading Journal</p>", unsafe_allow_html=True)
        pw = st.text_input("Password", type="password")
        if st.button("Login", type="primary"):
            if pw == AUTH_PASSWORD:
                st.session_state["tradein_authenticated"] = True
                st.rerun()
            else:
                st.error("Password salah.")
        st.stop()


# ---------- Theme ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root { --bg:#080d16; --panel:#101827; --panel2:#141f30; --line:#243247; --muted:#8b9bb0; --text:#e8eef7; --green:#32d296; --red:#ff687d; --blue:#79aaff; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
.stApp { background:var(--bg); color:var(--text); }
[data-testid="stHeader"] { background:rgba(8,13,22,.92); }
[data-testid="stSidebar"] { background:#0b1220; border-right:1px solid var(--line); }
[data-testid="stSidebar"] * { color:#dce6f3; }
.block-container { padding-top:1.65rem; padding-bottom:3rem; max-width:1500px; }
h1,h2,h3 { font-family:'Manrope',sans-serif !important; letter-spacing:-.035em; color:var(--text); }
h1 { font-size:2rem !important; font-weight:800 !important; }
h2 { font-size:1.35rem !important; font-weight:750 !important; }
h3 { font-size:1.05rem !important; font-weight:700 !important; }
p, label, .stCaption { color:#a9b7c9; }
div[data-testid="stMetric"] { background:linear-gradient(145deg,#121d2d,#0e1725); border:1px solid #25344a; border-radius:15px; padding:16px 18px; min-height:112px; }
div[data-testid="stMetricLabel"] { color:#91a2b8; font-size:.78rem; text-transform:uppercase; letter-spacing:.08em; }
div[data-testid="stMetricValue"] { color:#edf4ff; font-family:'Manrope',sans-serif; font-weight:800; }
div[data-testid="stMetricDelta"] { font-size:.78rem; }
.stButton > button, .stDownloadButton > button, button[kind="primary"] { border-radius:10px; border:1px solid #2b8e70; background:#147d61; color:white; font-weight:700; min-height:2.55rem; }
.stButton > button:hover { background:#199b77; border-color:#36c99b; color:white; }
div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input, div[data-testid="stDateInput"] input, div[data-testid="stTextArea"] textarea, div[data-testid="stSelectbox"] div[data-baseweb="select"] { background:#0d1726; color:#e8eef7; border-color:#2a3a50; border-radius:9px; }
div[data-testid="stFileUploader"] { background:#0d1726; border:1px dashed #354963; border-radius:12px; padding:10px; }
div[data-testid="stDataFrame"] { border:1px solid #26364b; border-radius:12px; overflow:hidden; }
hr { border-color:#26364b; }
section[data-testid="stSidebar"] .stRadio label { padding:7px 10px; border-radius:8px; }
section[data-testid="stSidebar"] .stRadio label:hover { background:#172337; }
.brand { font-family:Manrope,sans-serif; font-weight:800; font-size:1.18rem; letter-spacing:-.04em; color:#f2f6fc; }
.brand span { color:#35d39b; }
.eyebrow { color:#8fa2ba; font-size:.72rem; text-transform:uppercase; letter-spacing:.13em; font-weight:700; }
.panel { background:linear-gradient(145deg,#121d2d,#0e1725); border:1px solid #26364b; border-radius:15px; padding:17px 19px; }
.small-muted { color:#91a1b5; font-size:.82rem; }
.positive { color:#32d296 !important; } .negative { color:#ff7184 !important; }
div[data-testid="stTabs"] button { color:#9fb0c5; }
div[data-testid="stTabs"] button[aria-selected="true"] { color:#43d9a6; border-bottom-color:#43d9a6; }

/* ---------- Risk metrics and expanded overview grid ---------- */
.metric-grid{grid-template-columns:1.3fr repeat(5,minmax(0,1fr))}
.metric-primary{grid-column:auto}
.risk-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:11px;margin:0 0 10px}
.risk-card{min-width:0;padding:16px 15px 14px;border-radius:12px;background:linear-gradient(145deg,rgba(18,24,40,.82),rgba(11,15,26,.72));border:1px solid rgba(116,133,190,.15)}
.risk-label{font-size:.59rem;font-weight:800;letter-spacing:.11em;color:#8793b1;line-height:1.4;min-height:28px}
.risk-value{font-family:'Manrope',sans-serif;font-size:clamp(1.1rem,1.5vw,1.55rem);font-weight:800;letter-spacing:-.045em;color:#f0f3ff;margin:8px 0 6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.risk-note{font-size:.65rem;color:#75819d;line-height:1.4}
@media(max-width:1150px){.metric-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.metric-primary{grid-column:span 1}.risk-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:700px){.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.metric-primary{grid-column:span 2}.risk-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.risk-card{padding:13px}.risk-value{font-size:1.2rem}}

/* ---------- TraderWaves-inspired minimal sidebar ---------- */
.sidebar-brand-stack{padding:15px 8px 27px;margin:0 0 18px;text-align:left;border-bottom:1px solid rgba(116,133,190,.12)}
.sidebar-logo-mark{width:42px;height:42px;margin:0 0 11px 0;display:flex;align-items:center;justify-content:flex-start}
.sidebar-logo-mark svg{width:42px;height:42px;overflow:visible}
.sidebar-wordmark{font-family:'Manrope',sans-serif;font-size:1.52rem;font-weight:850;letter-spacing:-.065em;line-height:1;color:#f4f6ff}
.sidebar-wordmark span{color:#8294ff}
.sidebar-brand-stack .sidebar-subtitle{font-size:.55rem;letter-spacing:.16em;color:#7885a2;font-weight:700;margin-top:7px}
.sidebar-section-label{padding:0 9px;margin:0 0 9px;color:#697795;font-size:.61rem;letter-spacing:.16em}
[data-testid="stSidebar"] div[data-testid="stRadio"]>label{display:none!important}
[data-testid="stSidebar"] div[data-testid="stRadio"]>div{gap:2px!important}
[data-testid="stSidebar"] div[data-testid="stRadio"] label{min-height:39px;padding:0 10px!important;margin:0!important;border:0!important;border-radius:7px!important;background:transparent!important;color:#a0abc2!important;font-size:.86rem!important;font-weight:550!important;box-shadow:none!important;transition:color .15s ease,background .15s ease}
[data-testid="stSidebar"] div[data-testid="stRadio"] label:hover{background:rgba(120,140,255,.055)!important;color:#eef1ff!important}
[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked){background:rgba(83,109,255,.095)!important;color:#aebaff!important;box-shadow:inset 2px 0 0 #7185ff!important;font-weight:700!important}
[data-testid="stSidebar"] div[data-testid="stRadio"] label>div:first-child{display:none!important}
[data-testid="stSidebar"] div[data-testid="stRadio"] label input[type="radio"]{display:none!important}
[data-testid="stSidebar"] div[data-testid="stRadio"] label [data-testid="stMarkdownContainer"]{margin-left:0!important;padding-left:0!important}
[data-testid="stSidebar"] div[data-testid="stRadio"] label p{color:inherit!important;font-size:.86rem!important}
.sidebar-account-minimal{margin:30px 9px 0;padding-top:14px;border-top:1px solid rgba(116,133,190,.12)}
.account-heading{font-size:.59rem;font-weight:800;letter-spacing:.15em;color:#657291;margin-bottom:9px}
.sidebar-account-minimal .account-name{font-size:.78rem;font-weight:650;color:#dce3f4;margin:0 0 5px}
.sidebar-account-minimal .account-status{font-size:.57rem;font-weight:650;letter-spacing:.08em;color:#7885a2}
.sidebar-footer{margin:21px 9px 0;padding-top:12px;border-top:0;color:#586581;font-size:.56rem;letter-spacing:.11em}
@media(max-width:700px){.sidebar-brand-stack{padding-bottom:20px;margin-bottom:14px}}

/* ---------- Workspace navigation redesign ---------- */
[data-testid="stSidebar"]{border-right:1px solid rgba(116,133,190,.12)!important;background:linear-gradient(180deg,#0b1020 0%,#090c15 55%,#080a11 100%)!important}
[data-testid="stSidebar"]>div:first-child{padding-top:1.35rem}
.sidebar-brand{display:flex;align-items:center;gap:12px;padding:8px 10px 28px;margin-bottom:10px}
.brand-mark{width:39px;height:39px;display:grid;place-items:center;border-radius:12px;background:linear-gradient(145deg,#667cff,#394fc8);color:#fff;font-size:1.35rem;box-shadow:0 7px 22px rgba(75,96,235,.27)}
.sidebar-brand .brand{font-family:'Manrope',sans-serif;font-size:1.25rem;font-weight:850;letter-spacing:-.055em;color:#f3f5ff;line-height:1.1}
.sidebar-brand .brand span{color:#8192ff}
.sidebar-subtitle{font-size:.55rem;letter-spacing:.19em;color:#697694;font-weight:800;margin-top:5px}
.sidebar-section-label{font-size:.62rem;letter-spacing:.18em;font-weight:800;color:#677493;padding:0 12px;margin:0 0 10px}
[data-testid="stSidebar"] div[data-testid="stRadio"]>label{display:none}
[data-testid="stSidebar"] div[data-testid="stRadio"]>div{gap:5px!important}
[data-testid="stSidebar"] div[data-testid="stRadio"] label{position:relative;display:flex;align-items:center;min-height:43px;padding:0 12px!important;margin:0!important;border:1px solid transparent!important;border-radius:10px!important;background:transparent!important;color:#929db8!important;font-size:.84rem!important;font-weight:600!important;transition:all .16s ease}
[data-testid="stSidebar"] div[data-testid="stRadio"] label:hover{background:rgba(132,149,255,.055)!important;color:#e3e8ff!important;border-color:rgba(132,149,255,.09)!important}
[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked){background:linear-gradient(90deg,rgba(83,109,255,.19),rgba(83,109,255,.055))!important;border-color:rgba(117,137,255,.2)!important;color:#e7eaff!important;box-shadow:inset 2px 0 0 #7185ff}
[data-testid="stSidebar"] div[data-testid="stRadio"] label p{color:inherit!important;font-size:.84rem!important;font-weight:600!important}
[data-testid="stSidebar"] div[data-testid="stRadio"] label>div:first-child{margin-right:9px}
.sidebar-account{margin:27px 4px 0;padding:14px 13px;border-radius:12px;border:1px solid rgba(116,133,190,.14);background:linear-gradient(145deg,rgba(21,28,48,.72),rgba(12,16,28,.72))}
.account-top{display:flex;align-items:center;gap:7px;color:#7683a3;font-size:.57rem;font-weight:800;letter-spacing:.13em}
.account-indicator{width:6px;height:6px;border-radius:50%;background:#42d7a5;box-shadow:0 0 8px rgba(66,215,165,.7)}
.account-name{font-size:.82rem;font-weight:700;color:#e0e6f7;margin:10px 0 4px}
.account-name span,.account-status span{color:#65718d;padding:0 3px}
.account-status{font-size:.59rem;font-weight:700;letter-spacing:.08em;color:#7785a4}
.sidebar-footer{margin:22px 10px 0;padding-top:13px;border-top:1px solid rgba(116,133,190,.12);display:flex;justify-content:space-between;color:#56627f;font-size:.58rem;font-weight:800;letter-spacing:.12em}
.sidebar-footer span{color:#7181a5}
@media(max-width:700px){.sidebar-brand{padding-bottom:18px}.sidebar-account{margin-top:18px}}

/* ---------- Minimal performance cards ---------- */
.metric-grid{display:grid;grid-template-columns:1.35fr repeat(4,minmax(0,1fr));gap:12px;margin:0 0 4px}
.metric-card{position:relative;overflow:hidden;min-width:0;min-height:132px;padding:17px 18px 15px;border-radius:13px;background:linear-gradient(145deg,rgba(17,23,39,.88),rgba(10,14,25,.78));border:1px solid rgba(118,137,190,.13);display:flex;flex-direction:column;justify-content:space-between;transition:background .2s ease,border-color .2s ease,transform .2s ease}
.metric-card:hover{background:linear-gradient(145deg,rgba(24,32,55,.96),rgba(13,18,32,.92));border-color:rgba(119,139,255,.38);transform:translateY(-2px)}
.metric-primary{background:radial-gradient(ellipse at 100% 0%,rgba(83,109,255,.2),transparent 55%),linear-gradient(145deg,#171f38,#101522);border-color:rgba(112,132,255,.28)}
.metric-primary:after{content:"";position:absolute;right:-35px;bottom:-70px;width:150px;height:150px;border:1px solid rgba(126,145,255,.13);border-radius:50%;box-shadow:0 0 0 18px rgba(126,145,255,.025),0 0 0 38px rgba(126,145,255,.018);pointer-events:none}
.metric-topline{display:flex;align-items:center;justify-content:space-between;gap:8px}
.metric-label{font-size:.62rem;font-weight:800;letter-spacing:.13em;color:#8793b1;white-space:nowrap}
.metric-symbol{font-size:1rem;color:#8495ff}
.metric-index{font-size:.62rem;color:#536080;font-weight:700}
.metric-value{font-family:'Manrope',sans-serif;font-size:clamp(1.12rem,1.55vw,1.7rem);font-weight:800;letter-spacing:-.055em;color:#f1f4ff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin:9px 0 7px}
.metric-primary .metric-value{font-size:clamp(1.3rem,1.8vw,2rem)}
.metric-unit{font-size:.78rem;font-weight:600;letter-spacing:0;color:#9ba6c1}
.metric-up{color:#58ddb0}.metric-down{color:#ff8294}
.metric-foot{font-size:.7rem;color:#7e8aa6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.metric-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#7187ff;margin:0 7px 1px 0;box-shadow:0 0 9px rgba(113,135,255,.8)}
.metric-separator{color:#4c5874;padding:0 5px}
.section-period{font-size:.59rem;letter-spacing:.11em;color:#56617e;margin-left:8px}
@media(max-width:1150px){.metric-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.metric-primary{grid-column:span 2}}
@media(max-width:700px){.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.metric-primary{grid-column:span 2}.metric-card{min-height:118px;padding:14px}.metric-value{font-size:1.25rem}.metric-primary .metric-value{font-size:1.65rem}.metric-label{font-size:.58rem}}

/* ---------- Dashboard layout refinement ---------- */
.overview-hero{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;padding:8px 0 25px;border-bottom:1px solid #222a40;margin-bottom:22px}
.overview-hero h1{font-size:2.35rem!important;letter-spacing:-.06em!important}
.hero-meta{white-space:nowrap;color:#9aa6c2;font-size:.68rem;font-weight:700;letter-spacing:.1em;padding:10px 13px;border:1px solid #293451;border-radius:30px;background:rgba(17,23,40,.72)}
.live-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#7187ff;box-shadow:0 0 12px #7187ff;margin:0 7px 1px 0}
.hero-divider{color:#4c5876;padding:0 7px}
.section-kicker{font-size:.67rem;font-weight:800;letter-spacing:.16em;color:#7888b4;margin:5px 0 12px}
.section-gap{margin-top:24px}
.chart-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:2px 0 3px}
.chart-heading h3{margin:0 0 3px!important}
.chart-chip{font-size:.62rem;letter-spacing:.12em;font-weight:800;color:#9eacff;border:1px solid #35416d;background:rgba(83,109,255,.1);padding:6px 9px;border-radius:20px;white-space:nowrap}
div[data-testid="stMetric"]{background:linear-gradient(145deg,#151c30 0%,#101522 100%)!important;border:1px solid #293451!important;border-radius:16px!important}
div[data-testid="stMetricLabel"]{font-size:.66rem!important;letter-spacing:.12em!important}
div[data-testid="stMetricValue"]{font-size:clamp(1.15rem,1.65vw,1.75rem)!important}
div[data-testid="stDataFrame"]{background:#101522!important}
@media(max-width:900px){.overview-hero{align-items:flex-start;flex-direction:column}.hero-meta{white-space:normal}.overview-hero h1{font-size:1.8rem!important}}

/* ---------- TRADEIN UI refresh: electric blue / premium trading desk ---------- */
:root {
  --bg:#070910; --panel:#101421; --panel2:#151c2d; --line:#252d43;
  --muted:#929bb2; --text:#f1f4fb; --green:#38d9a5; --red:#ff647f;
  --blue:#536dff; --blue2:#8294ff;
}
.stApp { background:radial-gradient(ellipse at 78% -12%,rgba(50,70,190,.18),transparent 34%),#070910 !important; }
[data-testid="stHeader"] { background:rgba(7,9,16,.82) !important; backdrop-filter:blur(16px); }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#0d1120 0%,#090c15 100%) !important; border-right:1px solid #222a40 !important; }
.block-container { max-width:1540px !important; padding-top:2rem !important; padding-left:2.2rem !important; padding-right:2.2rem !important; }
h1 { font-size:2.25rem !important; letter-spacing:-.055em !important; }
h2 { font-size:1.45rem !important; letter-spacing:-.04em !important; }
h3 { font-size:1.08rem !important; }
.brand { font-size:1.35rem !important; letter-spacing:-.055em !important; }
.brand span { color:#7185ff !important; }
.eyebrow { color:#8794b5 !important; letter-spacing:.16em !important; font-size:.68rem !important; }
.small-muted { color:#8f9ab3 !important; }
.panel, div[data-testid="stMetric"] {
  background:linear-gradient(145deg,rgba(21,27,44,.96),rgba(13,17,29,.98)) !important;
  border:1px solid #252d46 !important; border-radius:17px !important;
  box-shadow:0 12px 32px rgba(0,0,0,.14) !important;
}
div[data-testid="stMetric"] { padding:19px 20px !important; min-height:122px !important; transition:border-color .18s ease,transform .18s ease,box-shadow .18s ease; }
div[data-testid="stMetric"]:hover { border-color:#4658b5 !important; transform:translateY(-2px); box-shadow:0 16px 34px rgba(0,0,0,.22) !important; }
div[data-testid="stMetricLabel"] { color:#9ba7c1 !important; font-size:.7rem !important; letter-spacing:.13em !important; }
div[data-testid="stMetricValue"] { color:#f4f6ff !important; font-size:1.75rem !important; letter-spacing:-.045em !important; }
div[data-testid="stMetricDelta"] { font-size:.76rem !important; }
.stButton > button, .stDownloadButton > button, button[kind="primary"] {
  background:linear-gradient(135deg,#536dff,#354bd1) !important; border:1px solid #7185ff !important;
  border-radius:11px !important; min-height:2.65rem !important; font-weight:700 !important;
  box-shadow:0 6px 18px rgba(64,84,220,.18) !important; transition:all .18s ease !important;
}
.stButton > button:hover, .stDownloadButton > button:hover { filter:brightness(1.12); transform:translateY(-1px); }
div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input,
div[data-testid="stDateInput"] input, div[data-testid="stTextArea"] textarea,
div[data-testid="stSelectbox"] div[data-baseweb="select"], div[data-testid="stMultiSelect"] div[data-baseweb="select"] {
  background:#0c1120 !important; border-color:#2a3452 !important; border-radius:10px !important;
}
div[data-testid="stFileUploader"] { background:#0c1120 !important; border:1px dashed #3a4770 !important; border-radius:14px !important; }
div[data-testid="stDataFrame"] { border:1px solid #29324b !important; border-radius:14px !important; }
hr { border-color:#252d43 !important; }
section[data-testid="stSidebar"] .stRadio > div { gap:5px !important; }
section[data-testid="stSidebar"] .stRadio label { padding:9px 12px !important; border:1px solid transparent; border-radius:10px !important; transition:all .16s ease; }
section[data-testid="stSidebar"] .stRadio label:hover { background:#171e34 !important; border-color:#29365e !important; }
section[data-testid="stSidebar"] .stRadio label[data-checked="true"] { background:rgba(83,109,255,.14) !important; border-color:rgba(111,132,255,.38) !important; }
div[data-testid="stTabs"] button { padding:10px 14px !important; }
div[data-testid="stTabs"] button[aria-selected="true"] { color:#91a2ff !important; border-bottom-color:#7185ff !important; }
[data-testid="stExpander"] { background:#101625 !important; border:1px solid #252e47 !important; border-radius:13px !important; }
[data-testid="stAlert"] { border-radius:12px !important; }
.js-plotly-plot .plotly .modebar { opacity:.45; }
@media (max-width: 900px) {
  .block-container { padding-left:1rem !important; padding-right:1rem !important; padding-top:1.2rem !important; }
  h1 { font-size:1.8rem !important; }
  div[data-testid="stMetric"] { min-height:104px !important; padding:14px !important; }
  div[data-testid="stMetricValue"] { font-size:1.35rem !important; }
}


/* FINAL SIDEBAR OVERRIDE: keep original triangle logo and remove Streamlit radio bullets */
[data-testid="stSidebar"] div[data-testid="stRadio"] label{
  display:flex!important;
  align-items:center!important;
  gap:0!important;
  padding-left:12px!important;
}
[data-testid="stSidebar"] div[data-testid="stRadio"] label > div:first-child{
  display:none!important;
  width:0!important;
  min-width:0!important;
  margin:0!important;
  padding:0!important;
}
[data-testid="stSidebar"] div[data-testid="stRadio"] label > div:last-child{
  margin-left:0!important;
  padding-left:0!important;
}
.sidebar-brand-stack .sidebar-logo-mark svg{
  width:42px!important;
  height:42px!important;
}

</style>
""", unsafe_allow_html=True)

# ---------- Database: SQLite locally, PostgreSQL (Supabase) in cloud ----------
def db():
    if CLOUD_DB:
        return psycopg.connect(DATABASE_URL)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    if CLOUD_DB:
        with db() as con:
            con.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                ticket TEXT, symbol TEXT NOT NULL, direction TEXT NOT NULL,
                open_time TEXT, close_time TEXT, entry DOUBLE PRECISION, exit DOUBLE PRECISION,
                volume DOUBLE PRECISION, sl DOUBLE PRECISION, tp DOUBLE PRECISION,
                pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
                commission DOUBLE PRECISION DEFAULT 0, swap DOUBLE PRECISION DEFAULT 0,
                strategy TEXT, session TEXT, setup TEXT, emotion TEXT,
                followed_plan INTEGER DEFAULT 1, notes TEXT, screenshot TEXT,
                reason_entry TEXT, reason_exit TEXT, decision_making TEXT, outcome_decision TEXT,
                confluences TEXT, lessons TEXT, created_at TEXT
            )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_trades_close ON trades(close_time)")
            existing = {r[0] for r in con.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='trades'"
            ).fetchall()}
            migrations = {
                "commission":"DOUBLE PRECISION DEFAULT 0", "swap":"DOUBLE PRECISION DEFAULT 0",
                "screenshot":"TEXT", "reason_entry":"TEXT", "reason_exit":"TEXT",
                "decision_making":"TEXT", "outcome_decision":"TEXT", "confluences":"TEXT",
                "lessons":"TEXT", "created_at":"TEXT"
            }
            for col, typ in migrations.items():
                if col not in existing:
                    con.execute(f"ALTER TABLE trades ADD COLUMN {col} {typ}")
            # Add a partial unique index only when the existing data permits it.
            # Never delete or rewrite historical rows during startup.
            duplicate_tickets = con.execute("""
                SELECT COUNT(*) FROM (
                    SELECT ticket FROM trades
                    WHERE ticket IS NOT NULL AND ticket <> ''
                    GROUP BY ticket HAVING COUNT(*) > 1
                ) AS duplicates
            """).fetchone()[0]
            if not duplicate_tickets:
                con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_ticket_unique ON trades(ticket) WHERE ticket IS NOT NULL AND ticket <> ''")
    else:
        with db() as con:
            con.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket TEXT, symbol TEXT NOT NULL, direction TEXT NOT NULL,
                open_time TEXT, close_time TEXT, entry REAL, exit REAL,
                volume REAL, sl REAL, tp REAL, pnl REAL NOT NULL DEFAULT 0,
                commission REAL DEFAULT 0, swap REAL DEFAULT 0,
                strategy TEXT, session TEXT, setup TEXT, emotion TEXT,
                followed_plan INTEGER DEFAULT 1, notes TEXT, screenshot TEXT,
                reason_entry TEXT, reason_exit TEXT, decision_making TEXT, outcome_decision TEXT,
                confluences TEXT, lessons TEXT, created_at TEXT
            )""")
            con.execute("CREATE INDEX IF NOT EXISTS idx_trades_close ON trades(close_time)")
            existing = {r[1] for r in con.execute("PRAGMA table_info(trades)")}
            for col, typ in [("commission","REAL DEFAULT 0"),("swap","REAL DEFAULT 0"),("screenshot","TEXT"),("reason_entry","TEXT"),("reason_exit","TEXT"),("decision_making","TEXT"),("outcome_decision","TEXT"),("confluences","TEXT"),("lessons","TEXT"),("created_at","TEXT")]:
                if col not in existing:
                    con.execute(f"ALTER TABLE trades ADD COLUMN {col} {typ}")
            duplicate_tickets = con.execute("""
                SELECT COUNT(*) FROM (
                    SELECT ticket FROM trades
                    WHERE ticket IS NOT NULL AND ticket <> ''
                    GROUP BY ticket HAVING COUNT(*) > 1
                )
            """).fetchone()[0]
            if not duplicate_tickets:
                con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_ticket_unique ON trades(ticket) WHERE ticket IS NOT NULL AND ticket <> ''")
init_db()

def load_trades():
    with db() as con:
        if CLOUD_DB:
            cur = con.execute("SELECT * FROM trades ORDER BY COALESCE(close_time, open_time) DESC, id DESC")
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=[d.name for d in cur.description])
        return pd.read_sql_query("SELECT * FROM trades ORDER BY COALESCE(close_time, open_time) DESC, id DESC", con)

def add_trade(d):
    cols = list(d.keys())
    placeholders = ",".join(["%s" if CLOUD_DB else "?"] * (len(cols)+1))
    with db() as con:
        con.execute(f"INSERT INTO trades ({','.join(cols)}, created_at) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                    list(d.values()) + [datetime.now().isoformat(timespec="seconds")])

def money(x):
    return f"${float(x):,.2f}"

def num(v):
    try: return float(v) if pd.notna(v) and str(v).strip() not in ("","-") else 0.0
    except: return 0.0

def prep(df):
    if df.empty: return df
    df = df.copy()
    for c in ["pnl","volume","entry","exit","sl","tp","commission","swap"]:
        if c in df: df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["open_dt"] = pd.to_datetime(df["open_time"], errors="coerce")
    df["close_dt"] = pd.to_datetime(df["close_time"], errors="coerce")
    df["trade_dt"] = df["close_dt"].fillna(df["open_dt"])
    df["trade_date"] = df["trade_dt"].dt.date
    return df

def performance_trades(df):
    """Exclude malformed legacy MT5 rows from metrics without deleting them.

    Manually entered trades remain eligible even if their lot size is zero.
    Only native-MT5-import rows are subject to the volume/direction validation.
    """
    if df.empty:
        return df.copy()
    out = df.copy()
    imported = out.get("notes", pd.Series("", index=out.index)).fillna("").astype(str).str.startswith(
        "Imported from native MT5 XLSX Positions report"
    )
    volume = pd.to_numeric(out.get("volume", 0), errors="coerce").fillna(0)
    direction = out.get("direction", pd.Series("", index=out.index)).fillna("").astype(str).str.upper().str.strip()
    valid_mt5 = (volume > 0) & direction.isin(["BUY", "SELL"])
    return out.loc[(~imported) | valid_mt5].copy()


def metric_card(label, value, note=""):
    st.metric(label, value, note if note else None)

def chart_layout(fig, height=300):
    fig.update_layout(
        height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#aebdd0", family="DM Sans"),
        margin=dict(l=8,r=8,t=24,b=8), legend=dict(orientation="h",y=1.12,x=0),
        xaxis=dict(gridcolor="#1d2b3e", zerolinecolor="#26364b"),
        yaxis=dict(gridcolor="#1d2b3e", zerolinecolor="#26364b"),
        hoverlabel=dict(bgcolor="#142033",font_color="#edf4ff")
    )
    return fig

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown(
        '<div class="sidebar-brand-stack">'
        '<div class="sidebar-logo-mark"><svg viewBox="0 0 64 64" role="img" aria-label="TRADEIN triangle logo">'
        '<path d="M32 5 L59 55 H5 Z" fill="none" stroke="#8294ff" stroke-width="5" stroke-linejoin="round"/>'
        '<path d="M32 22 L45 47 H19 Z" fill="#536dff" opacity=".82"/>'
        '</svg></div>'
        '<div class="sidebar-wordmark">TRADEIN<span>.</span></div>'
        '<div class="sidebar-subtitle">YOUR PERSONAL TRADING JOURNAL</div></div>',
        unsafe_allow_html=True
    )
    st.markdown('<div class="sidebar-section-label">WORKSPACE</div>', unsafe_allow_html=True)
    menu = [
        "Overview", "Calendar", "Trade Journal", "Add Trade",
        "Import MT5", "Analytics", "Reports", "Playbook", "Backup & Settings"
    ]
    page = st.radio("Workspace navigation", menu, label_visibility="collapsed")
    st.markdown(
        '<div class="sidebar-account-minimal"><div class="account-heading">ACCOUNT</div>'
        '<div class="account-name">Forex · MetaTrader 5</div>'
        f'<div class="account-status">{"CLOUD DATABASE" if CLOUD_DB else "LOCAL DATABASE"} · PRIVATE</div></div>',
        unsafe_allow_html=True
    )
    st.markdown('<div class="sidebar-footer">PERSONAL EDITION <span>V2.0</span></div>', unsafe_allow_html=True)

df = prep(load_trades())
filtered = df.copy()
if not df.empty:
    min_date = df["trade_date"].dropna().min()
    max_date = df["trade_date"].dropna().max()
else:
    min_date, max_date = date.today(), date.today()

def page_header(title, subtitle, action=None):
    st.markdown(f'<div class="eyebrow">TRADEIN · TRADING JOURNAL</div><h1 style="margin:3px 0 2px">{title}</h1><div class="small-muted">{subtitle}</div>', unsafe_allow_html=True)

def calc_stats(d):
    n=len(d); wins=int((d.pnl>0).sum()); losses=int((d.pnl<0).sum())
    gp=float(d.loc[d.pnl>0,"pnl"].sum()); gl=abs(float(d.loc[d.pnl<0,"pnl"].sum()))
    pf=gp/gl if gl else (float("inf") if gp else 0)
    return {"n":n,"wins":wins,"losses":losses,"net":float(d.pnl.sum()),"wr":wins/n*100 if n else 0,
            "pf":pf,"avg":float(d.pnl.mean()) if n else 0,"gp":gp,"gl":gl}

def calculate_risk_metrics(d):
    """Trade-based risk statistics from realized P/L; no account balance is assumed."""
    if d.empty or "pnl" not in d:
        return {"max_dd_pct":None,"current_dd_pct":None,"max_dd_money":0.0,
                "sharpe":None,"sortino":None,"equity":pd.Series(dtype=float),
                "drawdown":pd.Series(dtype=float)}
    ordered=d.dropna(subset=["pnl"]).copy()
    if "trade_dt" in ordered.columns:
        ordered=ordered.sort_values(["trade_dt"],kind="stable")
    pnl=pd.to_numeric(ordered["pnl"],errors="coerce").dropna().astype(float)
    if pnl.empty:
        return {"max_dd_pct":None,"current_dd_pct":None,"max_dd_money":0.0,
                "sharpe":None,"sortino":None,"equity":pd.Series(dtype=float),
                "drawdown":pd.Series(dtype=float)}
    equity=pnl.cumsum()
    peaks=equity.cummax().clip(lower=0)
    drawdown=(peaks-equity).clip(lower=0)
    valid_peak=peaks.where(peaks>0)
    dd_pct=(drawdown/valid_peak)*100
    max_dd_pct=float(dd_pct.max()) if dd_pct.notna().any() else None
    current_dd_pct=float(dd_pct.iloc[-1]) if pd.notna(dd_pct.iloc[-1]) else None
    max_dd_money=float(drawdown.max()) if not drawdown.empty else 0.0
    std=float(pnl.std(ddof=1)) if len(pnl)>1 else 0.0
    sharpe=float(pnl.mean()/std) if std>0 else None
    downside=(pnl.clip(upper=0).pow(2).mean())**0.5
    sortino=float(pnl.mean()/downside) if downside>0 else None
    return {"max_dd_pct":max_dd_pct,"current_dd_pct":current_dd_pct,
            "max_dd_money":max_dd_money,"sharpe":sharpe,"sortino":sortino,
            "equity":equity,"drawdown":drawdown}


def show_risk_section(d, compact=False):
    risk=calculate_risk_metrics(d)
    def pct(v): return f"{v:.2f}%" if v is not None else "—"
    def ratio(v): return f"{v:.2f}" if v is not None else "—"
    st.markdown('<div class="section-kicker section-gap">RISK METRICS</div>',unsafe_allow_html=True)
    metrics=[
        ("MAX DRAWDOWN %",pct(risk["max_dd_pct"]),"Largest peak-to-trough decline"),
        ("CURRENT DRAWDOWN %",pct(risk["current_dd_pct"]),"Distance from latest equity peak"),
        ("MAX EQUITY DRAWDOWN",money(risk["max_dd_money"]),"Largest realized P/L decline"),
        ("SHARPE RATIO",ratio(risk["sharpe"]),"Per-trade · non-annualized"),
        ("SORTINO RATIO",ratio(risk["sortino"]),"Per-trade · downside deviation")
    ]
    cards='<div class="risk-grid">'+''.join(
        f'<div class="risk-card"><div class="risk-label">{label}</div><div class="risk-value">{value}</div><div class="risk-note">{note}</div></div>'
        for label,value,note in metrics
    )+'</div>'
    st.markdown(cards,unsafe_allow_html=True)
    st.caption("Drawdown % uses the peak of cumulative realized P/L, not account balance. Sharpe and Sortino use trade P/L observations, risk-free/target return = 0, and are not annualized. Accurate account-equity drawdown requires starting balance and deposit/withdrawal history.")
    if not compact and not risk["drawdown"].empty:
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=list(range(1,len(risk["drawdown"])+1)),y=risk["drawdown"],
            mode="lines",line=dict(color="#ff7184",width=2.2),fill="tozeroy",
            fillcolor="rgba(255,113,132,.10)",name="Drawdown",
            hovertemplate="Trade #%{x}<br>Drawdown: $%{y:,.2f}<extra></extra>"))
        fig.update_layout(showlegend=False,xaxis_title="Closed trade",yaxis_title="Drawdown")
        st.plotly_chart(chart_layout(fig,250),use_container_width=True,config={"displayModeBar":False})


def show_overview(d):
    d = performance_trades(d)
    today_label = date.today().strftime("%A, %d %B %Y")
    st.markdown(
        f'<div class="overview-hero"><div><div class="eyebrow">YOUR TRADING WORKSPACE</div>'
        f'<h1 style="margin:5px 0 3px">Performance overview</h1>'
        f'<div class="small-muted">A focused view of your execution, consistency, and results.</div></div>'
        f'<div class="hero-meta"><span class="live-dot"></span> PRIVATE JOURNAL <span class="hero-divider">/</span> {today_label}</div></div>',
        unsafe_allow_html=True
    )
    if d.empty:
        st.info("Belum ada trade. Tambahkan posisi manual atau import report MT5 untuk mulai.")
        c1,c2=st.columns(2)
        with c1: st.markdown('<div class="panel"><h3>01 · Add your first trade</h3><p class="small-muted">Catat entry, exit, risk, strategi, dan kondisi psikologi.</p></div>',unsafe_allow_html=True)
        with c2: st.markdown('<div class="panel"><h3>02 · Import MT5 history</h3><p class="small-muted">Upload report XLSX dari MT5 dan cocokkan hasil import.</p></div>',unsafe_allow_html=True)
        return

    s=calc_stats(d)
    net_color = "positive" if s["net"] >= 0 else "negative"
    st.markdown('<div class="section-kicker">PERFORMANCE SNAPSHOT <span class="section-period">ALL CLOSED TRADES</span></div>', unsafe_allow_html=True)
    pf_value = "∞" if s["pf"]==float("inf") else f'{s["pf"]:.2f}'
    volume_value = f'{d.volume.sum():,.2f}'
    net_class = "metric-up" if s["net"] >= 0 else "metric-down"
    metrics_html = f"""
    <div class="metric-grid">
      <div class="metric-card metric-primary">
        <div class="metric-topline"><span class="metric-label">NET PROFIT / LOSS</span><span class="metric-symbol">↗</span></div>
        <div class="metric-value {net_class}">{money(s["net"])}</div>
        <div class="metric-foot"><span class="metric-dot"></span>{s["n"]} closed trades recorded</div>
      </div>
      <div class="metric-card">
        <div class="metric-topline"><span class="metric-label">WIN RATE</span><span class="metric-index">01</span></div>
        <div class="metric-value">{s["wr"]:.1f}<span class="metric-unit">%</span></div>
        <div class="metric-foot">{s["wins"]} wins <span class="metric-separator">/</span> {s["losses"]} losses</div>
      </div>
      <div class="metric-card">
        <div class="metric-topline"><span class="metric-label">PROFIT FACTOR</span><span class="metric-index">02</span></div>
        <div class="metric-value">{pf_value}</div>
        <div class="metric-foot">Gross profit vs. gross loss</div>
      </div>
      <div class="metric-card">
        <div class="metric-topline"><span class="metric-label">AVERAGE TRADE</span><span class="metric-index">03</span></div>
        <div class="metric-value">{money(s["avg"])}</div>
        <div class="metric-foot">Average net result per trade</div>
      </div>
      <div class="metric-card">
        <div class="metric-topline"><span class="metric-label">TOTAL TRADES</span><span class="metric-index">04</span></div>
        <div class="metric-value">{s["n"]}</div>
        <div class="metric-foot">Closed positions analyzed</div>
      </div>
      <div class="metric-card">
        <div class="metric-topline"><span class="metric-label">TRADED VOLUME</span><span class="metric-index">05</span></div>
        <div class="metric-value">{volume_value}<span class="metric-unit"> lots</span></div>
        <div class="metric-foot">Total executed volume</div>
      </div>
    </div>
    """
    st.markdown(metrics_html, unsafe_allow_html=True)

    st.markdown('<div class="section-kicker section-gap">PERFORMANCE CURVE</div>', unsafe_allow_html=True)
    left,right=st.columns([1.8,1],gap="large")
    with left:
        curve=d.dropna(subset=["trade_dt"]).sort_values("trade_dt").copy()
        curve["equity"]=curve.pnl.cumsum()
        st.markdown('<div class="chart-heading"><div><h3>Equity development</h3><span class="small-muted">Cumulative realized P/L across closed trades</span></div><span class="chart-chip">CUMULATIVE</span></div>',unsafe_allow_html=True)
        if not curve.empty:
            fig=go.Figure()
            fig.add_trace(go.Scatter(
                x=curve.trade_dt,y=curve.equity,mode="lines",
                line=dict(color="#7187ff",width=3,shape="spline"),
                fill="tozeroy",fillcolor="rgba(83,109,255,.13)",
                hovertemplate="%{x|%d %b %Y}<br><b>$%{y:,.2f}</b><extra></extra>",
                name="Cumulative P/L"
            ))
            fig.add_hline(y=0,line_dash="dot",line_color="#46516d",line_width=1)
            fig.update_layout(showlegend=False)
            st.plotly_chart(chart_layout(fig,340),use_container_width=True,config={"displayModeBar":False})
        else:
            st.caption("Trade date belum tersedia untuk membentuk equity curve.")
    with right:
        st.markdown('<div class="chart-heading"><div><h3>Trade outcomes</h3><span class="small-muted">Distribution by result</span></div></div>',unsafe_allow_html=True)
        outcome=pd.DataFrame({"Outcome":["Wins","Losses","Breakeven"],"Trades":[s["wins"],s["losses"],s["n"]-s["wins"]-s["losses"]]})
        fig=px.pie(outcome,names="Outcome",values="Trades",hole=.76,color="Outcome",
            color_discrete_map={"Wins":"#7187ff","Losses":"#ff7184","Breakeven":"#56627b"})
        fig.update_traces(textinfo="percent",textfont_color="#eaf1fa",hole=.76,
            marker=dict(line=dict(color="#111625",width=4)),
            hovertemplate="%{label}: %{value} trades<extra></extra>")
        fig.update_layout(showlegend=True,legend=dict(orientation="h",y=-.04,x=.0,font=dict(size=10)))
        st.plotly_chart(chart_layout(fig,340),use_container_width=True,config={"displayModeBar":False})

    st.markdown('<div class="section-kicker section-gap">MARKET & ACTIVITY</div>', unsafe_allow_html=True)
    l,r=st.columns([1,1.35],gap="large")
    with l:
        st.markdown('<div class="chart-heading"><div><h3>Performance by pair</h3><span class="small-muted">Net P/L grouped by instrument</span></div></div>',unsafe_allow_html=True)
        pair=d.groupby("symbol",as_index=False).pnl.sum().sort_values("pnl")
        fig=px.bar(pair,x="pnl",y="symbol",orientation="h",color="pnl",
            color_continuous_scale=["#ff7184","#303b62","#7187ff"])
        fig.update_layout(coloraxis_showscale=False)
        fig.update_traces(marker_line_width=0,hovertemplate="%{y}<br><b>$%{x:,.2f}</b><extra></extra>")
        st.plotly_chart(chart_layout(fig,300),use_container_width=True,config={"displayModeBar":False})
    with r:
        st.markdown('<div class="chart-heading"><div><h3>Recent trades</h3><span class="small-muted">Latest recorded positions</span></div><span class="chart-chip">LATEST 7</span></div>',unsafe_allow_html=True)
        recent=d[["symbol","direction","close_time","volume","pnl"]].head(7).copy()
        recent.columns=["Instrument","Side","Closed at","Lots","Net P/L"]
        recent["Net P/L"]=recent["Net P/L"].map(money)
        recent["Lots"]=recent["Lots"].map(lambda x:f"{float(x):.2f}")
        recent["Side"]=recent["Side"].fillna("—").astype(str).str.upper()
        st.dataframe(recent,use_container_width=True,hide_index=True,height=300)

    st.markdown('<div class="section-kicker section-gap">EDGE & CONSISTENCY</div>', unsafe_allow_html=True)
    best_by_pair=d.groupby("symbol").pnl.sum()
    best=best_by_pair.idxmax() if not best_by_pair.empty else "—"
    worst=best_by_pair.idxmin() if not best_by_pair.empty else "—"
    discipline=d.groupby("followed_plan").pnl.mean()
    x,y,z=st.columns(3)
    x.metric("STRONGEST INSTRUMENT",best,money(best_by_pair.max())+" net" if not best_by_pair.empty else None)
    y.metric("WEAKEST INSTRUMENT",worst,money(best_by_pair.min())+" net" if not best_by_pair.empty else None)
    z.metric("AVG. P/L · FOLLOWED PLAN",money(d.loc[d.followed_plan==1,"pnl"].mean()) if (d.followed_plan==1).any() else "—")

def show_calendar(d):
    page_header("Trading Calendar","Daily realized P/L. Select a month to review your consistency.")
    # Keep Calendar aligned with Overview/Analytics: malformed native-MT5
    # import rows remain archived in storage but are excluded from metrics.
    d = performance_trades(d)
    today=date.today()
    c1,c2=st.columns([1,3])
    with c1: month_pick=st.date_input("Month",value=today.replace(day=1))
    month_start=date(month_pick.year,month_pick.month,1)
    days=calendar.monthrange(month_pick.year,month_pick.month)[1]
    daily=d[d.trade_date.notna()].groupby("trade_date").pnl.sum().to_dict() if not d.empty else {}
    cols=st.columns(7)
    for col,name in zip(cols,["MON","TUE","WED","THU","FRI","SAT","SUN"]): col.markdown(f"<div class='eyebrow' style='text-align:center'>{name}</div>",unsafe_allow_html=True)
    offset=month_start.weekday()
    cells=[None]*offset+[date(month_pick.year,month_pick.month,day) for day in range(1,days+1)]
    cells += [None]*((7-len(cells)%7)%7)
    for start in range(0,len(cells),7):
        row=st.columns(7)
        for col,dt in zip(row,cells[start:start+7]):
            if dt is None:
                col.markdown("<div style='height:86px'></div>",unsafe_allow_html=True)
            else:
                val=daily.get(dt)
                bg="#102b28" if val is not None and val>0 else "#321c28" if val is not None and val<0 else "#101a29"
                color="#35d39b" if val is not None and val>0 else "#ff7184" if val is not None and val<0 else "#8293a9"
                pl=f"{val:+.2f}" if val is not None else "—"
                col.markdown(f"<div style='height:78px;background:{bg};border:1px solid #26364b;border-radius:10px;padding:9px'><div style='color:#cbd6e4;font-size:12px'>{dt.day}</div><div style='color:{color};font-weight:700;font-size:13px;margin-top:15px'>{pl}</div></div>",unsafe_allow_html=True)
    st.markdown("---")
    month_trades=d[d.trade_dt.dt.to_period("M")==pd.Period(month_pick, freq="M")] if not d.empty else d
    s=calc_stats(month_trades) if not month_trades.empty else {"n":0,"net":0,"wr":0,"wins":0,"losses":0,"pf":0,"avg":0,"gp":0,"gl":0}
    a,b,c=st.columns(3); a.metric("Monthly P/L",money(s["net"])); b.metric("Trades",s["n"]); c.metric("Win rate",f"{s['wr']:.1f}%")

def show_journal(d):
    page_header("Trade Journal","Search, inspect, edit, and manage every recorded position.")
    show_archive = st.checkbox("Show archived / invalid MT5 import rows", value=False,
                               help="Rows are preserved in the database and backup, but excluded from performance metrics.")
    valid = performance_trades(d)
    if not show_archive:
        d = valid
    if d.empty: st.info("Belum ada trade valid untuk ditampilkan."); return
    if show_archive:
        st.caption(f"Showing {len(d)} total records, including {len(d)-len(valid)} archived MT5 rows excluded from performance.")
    c1,c2,c3=st.columns([2,1,1])
    q=c1.text_input("Search",placeholder="Pair, ticket, strategy, notes…")
    pair=c2.multiselect("Pair",sorted(d.symbol.dropna().unique()))
    outcome=c3.selectbox("Outcome",["All","Win","Loss","Breakeven"])
    v=d.copy()
    if q: v=v[v.astype(str).apply(lambda col:col.str.contains(q,case=False,na=False)).any(axis=1)]
    if pair: v=v[v.symbol.isin(pair)]
    if outcome=="Win": v=v[v.pnl>0]
    elif outcome=="Loss": v=v[v.pnl<0]
    elif outcome=="Breakeven": v=v[v.pnl==0]
    show_cols=["id","symbol","direction","volume","pnl","strategy","session","decision_making","outcome_decision"]
    st.caption(f"{len(v)} positions shown")
    st.dataframe(v[show_cols],use_container_width=True,hide_index=True)
    st.markdown("### Manage selected trade")
    ids=v.id.astype(int).tolist()
    if not ids: return
    selected=st.selectbox("Trade ID",ids,format_func=lambda x:f"#{x} · {v.loc[v.id==x,'symbol'].iloc[0]} · {money(v.loc[v.id==x,'pnl'].iloc[0])}")
    r=v[v.id==selected].iloc[0]
    with st.expander("Edit trade details",expanded=False):
        with st.form(f"edit_{selected}"):
            a,b,c=st.columns(3)
            symbol=a.text_input("Pair",str(r.symbol))
            direction=b.selectbox("Direction",["BUY","SELL"],index=0 if r.direction=="BUY" else 1)
            volume=c.number_input("Lots",min_value=0.0,value=float(r.volume or 0),step=.01)
            pnl=st.number_input("Net P/L",value=float(r.pnl or 0),step=1.0)
            strategy=st.text_input("Strategy",str(r.strategy or ""))
            reason_entry=st.text_area("Reason for Entry",str(r.get("reason_entry", "") or ""))
            reason_exit=st.text_area("Reason for Exit",str(r.get("reason_exit", "") or ""))
            a,b=st.columns(2)
            decision_opts=["Good Decision","Bad Decision"]
            outcome_opts=["Good Outcome","Bad Outcome"]
            decision_default=str(r.get("decision_making", "") or "")
            outcome_default=str(r.get("outcome_decision", "") or "")
            decision=a.selectbox("Decision Making",["— Select —"]+decision_opts,index=(decision_opts.index(decision_default)+1 if decision_default in decision_opts else 0))
            outcome=b.selectbox("Outcome Decision",["— Select —"]+outcome_opts,index=(outcome_opts.index(outcome_default)+1 if outcome_default in outcome_opts else 0))
            confluence_opts=["CRT","Turtle Soup","Model-1","Time","True Structure Shift","FVG","SMT"]
            existing_conf=[x.strip() for x in str(r.get("confluences", "") or "").split(",") if x.strip()]
            confluences=st.multiselect("Confluence Checklist",confluence_opts,default=[x for x in existing_conf if x in confluence_opts])
            notes=st.text_area("Notes",str(r.notes or ""))
            lessons=st.text_area("Lessons",str(r.get("lessons", "") or ""))
            save=st.form_submit_button("Save changes")
            if save:
                with db() as con:
                    con.execute("UPDATE trades SET symbol=%s,direction=%s,volume=%s,pnl=%s,strategy=%s,reason_entry=%s,reason_exit=%s,decision_making=%s,outcome_decision=%s,confluences=%s,notes=%s,lessons=%s WHERE id=%s" if CLOUD_DB else "UPDATE trades SET symbol=?,direction=?,volume=?,pnl=?,strategy=?,reason_entry=?,reason_exit=?,decision_making=?,outcome_decision=?,confluences=?,notes=?,lessons=? WHERE id=?",
                        (symbol.upper(),direction,volume,pnl,strategy,reason_entry,reason_exit,decision if decision!="— Select —" else "",outcome if outcome!="— Select —" else "",", ".join(confluences),notes,lessons,int(selected)))
                st.success("Trade updated."); st.rerun()
    with st.expander("Trade review details",expanded=True):
        x,y=st.columns(2)
        with x:
            st.markdown("**Reason for Entry**")
            st.write(str(r.get("reason_entry", "") or "—"))
            st.markdown("**Decision Making**")
            st.write(str(r.get("decision_making", "") or "—"))
        with y:
            st.markdown("**Reason for Exit**")
            st.write(str(r.get("reason_exit", "") or "—"))
            st.markdown("**Outcome Decision**")
            st.write(str(r.get("outcome_decision", "") or "—"))
        st.markdown("**Confluences**")
        conf=str(r.get("confluences", "") or "").strip()
        st.write(conf if conf else "—")
        st.markdown("**Notes**")
        st.write(str(r.notes or "—"))
        st.markdown("**Lessons**")
        st.write(str(r.get("lessons", "") or "—"))
    with st.expander("Delete trade",expanded=False):
        st.warning("Penghapusan bersifat permanen. Buat backup sebelum melanjutkan.")
        confirm=st.checkbox(f"I understand — delete trade #{selected}",key=f"confirm_{selected}")
        if st.button("Delete selected trade",disabled=not confirm):
            with db() as con: con.execute("DELETE FROM trades WHERE id=%s" if CLOUD_DB else "DELETE FROM trades WHERE id=?",(int(selected),))
            st.success("Trade deleted."); st.rerun()
    if r.screenshot and isinstance(r.screenshot,str) and os.path.exists(r.screenshot):
        st.markdown("### Attached chart")
        st.image(r.screenshot,width=650)

def show_add():
    page_header("Add Trade","Review the setup, decision quality, and outcome — not just the P/L.")
    with st.form("add_trade",clear_on_submit=True):
        st.markdown("#### Trade")
        a,b,c=st.columns(3)
        symbol=a.text_input("Pair","EURUSD").upper().strip()
        direction=b.selectbox("Side",["BUY","SELL"])
        volume=c.number_input("Lot size",min_value=0.0,value=.10,step=.01,format="%.2f")
        pnl=st.number_input("Net P/L (account currency)",value=0.0,step=1.0)
        st.markdown("#### Trade reasoning")
        reason_entry=st.text_area("Reason for Entry",placeholder="Kenapa lu mengambil posisi ini? Jelaskan setup dan validasinya…")
        reason_exit=st.text_area("Reason for Exit",placeholder="Kenapa lu menutup posisi? TP, invalidation, partial, atau alasan lain…")
        a,b=st.columns(2)
        decision=a.selectbox("Decision Making",["— Select —","Good Decision","Bad Decision"])
        outcome=b.selectbox("Outcome Decision",["— Select —","Good Outcome","Bad Outcome"])
        st.markdown("#### Confluence checklist")
        confluences=st.multiselect("Pilih confluence yang benar-benar muncul pada trade ini",["CRT","Turtle Soup","Model-1","Time","True Structure Shift","FVG","SMT"])
        st.markdown("#### Review & learning")
        a,b=st.columns(2)
        strategy=a.text_input("Strategy")
        session=b.selectbox("Session",["Asia","London","New York","Overlap","Other"])
        a,b=st.columns(2)
        setup=a.text_input("Setup / pattern")
        emotion=b.selectbox("Emotion",["Calm","Confident","Fearful","FOMO","Revenge","Greedy","Other"])
        notes=st.text_area("Notes",placeholder="Catatan tambahan untuk trade ini…")
        lessons=st.text_area("Lessons",placeholder="Apa pelajaran yang lu ambil dari trade ini?")
        screenshot=st.file_uploader("Chart screenshot",type=["png","jpg","jpeg"])
        submit=st.form_submit_button("Save trade review",type="primary")
        if submit:
            if not symbol: st.error("Pair wajib diisi.")
            else:
                shot=""
                if screenshot:
                    name=f"{datetime.now():%Y%m%d%H%M%S}_{screenshot.name.replace(' ','_')}"
                    shot=str(UPLOAD_DIR/name)
                    with open(shot,"wb") as f: f.write(screenshot.getbuffer())
                add_trade({"ticket":"","symbol":symbol,"direction":direction,"open_time":"","close_time":"",
                    "entry":0,"exit":0,"volume":volume,"sl":0,"tp":0,"pnl":pnl,"commission":0,
                    "swap":0,"strategy":strategy,"session":session,"setup":setup,"emotion":emotion,
                    "followed_plan":1 if decision=="Good Decision" else 0,"notes":notes,"screenshot":shot,
                    "reason_entry":reason_entry,"reason_exit":reason_exit,
                    "decision_making":"" if decision=="— Select —" else decision,
                    "outcome_decision":"" if outcome=="— Select —" else outcome,
                    "confluences":", ".join(confluences),"lessons":lessons})
                st.success("Trade review saved."); st.rerun()

def show_import():
    page_header("Import MT5 History","Import native MT5 XLSX Positions report or map a CSV export.")
    st.markdown('<div class="panel"><b>Supported:</b> Excel report (.xlsx / .xls) from MT5 · CSV · TXT<br><span class="small-muted">XLSX importer detects the Positions header and imports position-level rows. Existing ticket IDs are skipped.</span></div>',unsafe_allow_html=True)
    file=st.file_uploader("Choose MT5 report",type=["xlsx","xls","csv","txt"])
    if not file: return
    if file.name.lower().endswith((".xlsx",".xls")):
        try: raw=pd.read_excel(file,header=None)
        except Exception as e: st.error(f"Could not read Excel file: {e}"); return
        header_idx=None
        for i in range(min(40,len(raw))):
            vals=[str(x).strip().lower() for x in raw.iloc[i].tolist() if pd.notna(x)]
            if {"position","symbol","profit","volume"}.issubset(set(vals)):
                header_idx=i; break
        if header_idx is None: st.error("Header Positions tidak ditemukan. Pastikan file adalah report History MT5."); return
        # MT5 Positions reports repeat "Time" and "Price" for open/close.
        # Make every header unique so pandas can address both columns reliably.
        base_headers=[str(x).strip() if pd.notna(x) else f"col_{j}" for j,x in enumerate(raw.iloc[header_idx])]
        seen={}
        headers=[]
        for name in base_headers:
            count=seen.get(name,0)
            headers.append(name if count == 0 else f"{name}.{count}")
            seen[name]=count+1
        data=raw.iloc[header_idx+1:].copy(); data.columns=headers
        data=data[data["Position"].notna() & data["Symbol"].notna()].copy()
        data=data[pd.to_numeric(data["Position"],errors="coerce").notna()]
        st.success(f"MT5 report rows detected · {len(data)} candidate rows")
        needed=["Position","Symbol","Type","Volume","Profit","Swap"]
        missing=[x for x in needed if x not in data.columns]
        if missing:
            st.error(f"Kolom wajib tidak ditemukan: {', '.join(missing)}")
            st.caption("Kolom yang terbaca: " + ", ".join(map(str, data.columns)))
            return
        st.dataframe(data[needed].head(20),use_container_width=True,hide_index=True)
        st.caption("Net P/L imported = Profit + Commission + Swap (biaya dipakai di perhitungan internal, tidak ditampilkan sebagai kolom jurnal). One row per MT5 position.")
        # Keep raw MT5 execution fields internal for accurate import and P/L calculation.
        required_import=["Time","Position","Symbol","Type","Volume","Price","Time.1","Price.1","Commission","Swap","Profit"]
        missing_import=[x for x in required_import if x not in data.columns]
        if missing_import:
            st.error(f"Data MT5 belum lengkap untuk import: {', '.join(missing_import)}")
            return
        if st.button("Import valid positions",type="primary"):
            inserted=skipped=0
            with db() as con: existing={str(r[0]) for r in con.execute("SELECT ticket FROM trades WHERE ticket IS NOT NULL AND ticket != ''")}
            for _,r in data.iterrows():
                ticket=str(r["Position"]).strip()
                direction=str(r["Type"]).strip().upper()
                volume=num(r["Volume"])
                # Do not import pending orders, zero-volume rows, or non-market directions.
                if not ticket or ticket in existing or volume <= 0 or direction not in ("BUY", "SELL"):
                    skipped+=1; continue
                comm,sw,profit=num(r["Commission"]),num(r["Swap"]),num(r["Profit"])
                add_trade({"ticket":ticket,"symbol":str(r["Symbol"]).strip().upper(),"direction":direction,
                    "open_time":str(r["Time"]),"close_time":str(r["Time.1"]),"entry":num(r["Price"]),"exit":num(r["Price.1"]),
                    "volume":num(r["Volume"]),"sl":num(r["S / L"]) if "S / L" in data.columns else 0,
                    "tp":num(r["T / P"]) if "T / P" in data.columns else 0,"pnl":profit+comm+sw,
                    "commission":comm,"swap":sw,"strategy":"","session":"","setup":"","emotion":"",
                    "followed_plan":1,"notes":"Imported from native MT5 XLSX Positions report","screenshot":""})
                existing.add(ticket); inserted+=1
            st.success(f"Import complete · {inserted} valid positions added · {skipped} duplicates / invalid rows skipped")
            st.rerun()
    else:
        try: imported=pd.read_csv(file,sep=None,engine="python")
        except Exception:
            try: imported=pd.read_csv(pd.io.common.BytesIO(file.getvalue()),sep=";")
            except Exception as e: st.error(f"CSV read failed: {e}"); return
        if imported.empty: st.warning("No rows found."); return
        st.markdown("#### Preview"); st.dataframe(imported.head(12),use_container_width=True)
        cols=list(imported.columns)
        def choose(label,candidates):
            found=next((x for x in cols if str(x).strip().lower() in candidates),None)
            return st.selectbox(label,["(skip)"]+cols,index=(cols.index(found)+1 if found else 0))
        a,b,c=st.columns(3)
        sym= a.selectbox("Symbol",["(skip)"]+cols,index=next((cols.index(x)+1 for x in cols if x.lower() in ["symbol","pair","instrument"]),0))
        typ= b.selectbox("Direction",["(skip)"]+cols,index=next((cols.index(x)+1 for x in cols if x.lower() in ["type","direction","side"]),0))
        tim= c.selectbox("Time",["(skip)"]+cols,index=next((cols.index(x)+1 for x in cols if x.lower() in ["time","close time"]),0))
        a,b,c=st.columns(3)
        vol=a.selectbox("Volume",["(skip)"]+cols,index=next((cols.index(x)+1 for x in cols if x.lower() in ["volume","lots","size"]),0))
        price=b.selectbox("Price",["(skip)"]+cols,index=next((cols.index(x)+1 for x in cols if x.lower() in ["price","exit"]),0))
        prof=c.selectbox("Profit",["(skip)"]+cols,index=next((cols.index(x)+1 for x in cols if x.lower() in ["profit","p/l","pl"]),0))
        ticket_col=st.selectbox("Ticket",["(skip)"]+cols,index=next((cols.index(x)+1 for x in cols if x.lower() in ["ticket","deal","position"]),0))
        if st.button("Import mapped CSV",type="primary"):
            inserted=skipped=0
            with db() as con: existing={str(r[0]) for r in con.execute("SELECT ticket FROM trades WHERE ticket IS NOT NULL AND ticket != ''")}
            for _,r in imported.iterrows():
                get=lambda col,default="": r[col] if col!="(skip)" else default
                ticket=str(get(ticket_col,"")).strip(); symbol=str(get(sym,"")).strip().upper()
                typv=str(get(typ,"BUY")).upper(); pnl=num(get(prof,0)); volume=num(get(vol,0)); pricev=num(get(price,0)); t=str(get(tim,""))
                if (ticket and ticket in existing) or not symbol or symbol=="NAN" or (vol!="(skip)" and volume<=0) or (typ!="(skip)" and typv not in ("BUY","SELL")):
                    skipped+=1; continue
                add_trade({"ticket":ticket,"symbol":symbol,"direction":"SELL" if "SELL" in typv else "BUY",
                    "open_time":t,"close_time":t,"entry":pricev,"exit":pricev,"volume":volume,"sl":0,"tp":0,
                    "pnl":pnl,"commission":0,"swap":0,"strategy":"","session":"","setup":"","emotion":"",
                    "followed_plan":1,"notes":"Imported from CSV","screenshot":""})
                if ticket: existing.add(ticket)
                inserted+=1
            st.success(f"Import complete · {inserted} added · {skipped} skipped"); st.rerun()

def show_analytics(d):
    page_header("Analytics","Understand what drives your results — and what holds you back.")
    d = performance_trades(d)
    if d.empty: st.info("Import or add trades to unlock analytics."); return
    tabs=st.tabs(["Performance","Execution","Psychology","Risk"])
    with tabs[0]:
        show_risk_section(d,compact=True)
        a,b=st.columns(2)
        with a:
            p=d.groupby("symbol",as_index=False).agg(net_pnl=("pnl","sum"),trades=("id","count"),avg_pnl=("pnl","mean"))
            st.markdown("### Pair performance"); st.dataframe(p.sort_values("net_pnl",ascending=False),use_container_width=True,hide_index=True)
        with b:
            sess=d.groupby("session",as_index=False).agg(net_pnl=("pnl","sum"),trades=("id","count"))
            st.markdown("### Session performance"); st.plotly_chart(chart_layout(px.bar(sess,x="session",y="net_pnl",color="net_pnl",color_continuous_scale=["#ff7184","#26364b","#35d39b"])),use_container_width=True)
        st.markdown("### Monthly performance")
        m=d.dropna(subset=["trade_dt"]).set_index("trade_dt").resample("ME").pnl.sum().reset_index()
        if not m.empty:
            m["month"]=m.trade_dt.dt.strftime("%b %Y")
            st.plotly_chart(chart_layout(px.bar(m,x="month",y="pnl",color="pnl",color_continuous_scale=["#ff7184","#26364b","#35d39b"])),use_container_width=True)
    with tabs[1]:
        a,b=st.columns(2)
        with a:
            st.markdown("### Direction"); direction=d.groupby("direction",as_index=False).agg(net_pnl=("pnl","sum"),trades=("id","count"),avg_pnl=("pnl","mean"))
            st.dataframe(direction,use_container_width=True,hide_index=True)
        with b:
            st.markdown("### Weekday")
            weekday=d.dropna(subset=["trade_dt"]).copy(); weekday["weekday"]=weekday.trade_dt.dt.day_name()
            wd=weekday.groupby("weekday",as_index=False).pnl.sum()
            order=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
            wd["sort"]=wd.weekday.map({v:i for i,v in enumerate(order)}); wd=wd.sort_values("sort")
            st.plotly_chart(chart_layout(px.bar(wd,x="weekday",y="pnl",color="pnl",color_continuous_scale=["#ff7184","#26364b","#35d39b"])),use_container_width=True)
    with tabs[2]:
        st.markdown("### Emotional state")
        e=d.groupby("emotion",dropna=False).agg(trades=("id","count"),net_pnl=("pnl","sum"),avg_pnl=("pnl","mean")).reset_index()
        st.dataframe(e,use_container_width=True,hide_index=True)
        st.markdown("### Decision quality")
        quality=d.groupby(["decision_making","outcome_decision"],dropna=False).agg(trades=("id","count"),net_pnl=("pnl","sum"),avg_pnl=("pnl","mean")).reset_index()
        quality["decision_making"]=quality.decision_making.fillna("").replace("", "Not reviewed")
        quality["outcome_decision"]=quality.outcome_decision.fillna("").replace("", "Not reviewed")
        st.dataframe(quality,use_container_width=True,hide_index=True)
        st.markdown("### Trading plan discipline")
        discipline=d.groupby("followed_plan").agg(trades=("id","count"),net_pnl=("pnl","sum"),avg_pnl=("pnl","mean")).reset_index()
        discipline["Plan status"]=discipline.followed_plan.map({1:"Followed plan",0:"Did not follow"})
        st.dataframe(discipline[["Plan status","trades","net_pnl","avg_pnl"]],use_container_width=True,hide_index=True)
    with tabs[3]:
        show_risk_section(d,compact=False)
        st.markdown("### Position sizing & outcomes")
        a,b,c=st.columns(3)
        a.metric("Average lot",f"{d.volume.mean():.2f}")
        b.metric("Largest lot",f"{d.volume.max():.2f}")
        c.metric("Average winner",money(d.loc[d.pnl>0,"pnl"].mean()) if (d.pnl>0).any() else "—")
        st.caption("R-multiple, MAE/MFE, and planned risk need risk-at-entry / tick-value data. They are not inferred from incomplete MT5 reports.")
        st.dataframe(d[["symbol","direction","volume","pnl"]],use_container_width=True,hide_index=True)

def show_reports(d):
    page_header("Reports","A consolidated trading report with performance, risk, and exportable records.")
    d=performance_trades(d)
    if d.empty:
        st.info("Belum ada trade valid untuk dibuatkan report.")
        return
    stats=calc_stats(d)
    risk=calculate_risk_metrics(d)
    st.markdown('<div class="section-kicker">REPORT SUMMARY</div>',unsafe_allow_html=True)
    a,b,c,dcol=st.columns(4)
    a.metric("TOTAL TRADES",stats["n"])
    b.metric("NET P/L",money(stats["net"]))
    c.metric("WIN RATE",f'{stats["wr"]:.1f}%')
    dcol.metric("PROFIT FACTOR","∞" if stats["pf"]==float("inf") else f'{stats["pf"]:.2f}')
    show_risk_section(d,compact=True)
    st.markdown('<div class="section-kicker section-gap">TRADE PERFORMANCE REPORT</div>',unsafe_allow_html=True)
    report=d.copy()
    report_cols=[c for c in ["trade_dt","symbol","direction","volume","pnl","strategy","session","followed_plan"] if c in report.columns]
    report=report[report_cols].rename(columns={"trade_dt":"Trade date","symbol":"Instrument","direction":"Side","volume":"Lots","pnl":"Net P/L","strategy":"Strategy","session":"Session","followed_plan":"Followed plan"})
    st.dataframe(report,use_container_width=True,hide_index=True)
    st.download_button("Download performance report CSV",report.to_csv(index=False).encode("utf-8-sig"),
        "tradein_performance_report.csv","text/csv",type="primary")
    st.caption(f"Report includes {len(report)} valid closed trades. Archived malformed MT5 rows remain stored and are excluded from performance calculations.")


def show_playbook(d):
    page_header("Playbook","A review space for strategies, setups, and execution discipline.")
    d = performance_trades(d)
    if d.empty: st.info("Belum ada trade untuk direview."); return
    strategies=d.groupby("strategy",dropna=False).agg(trades=("id","count"),net_pnl=("pnl","sum"),avg_pnl=("pnl","mean"),win_rate=("pnl",lambda x:(x>0).mean()*100)).reset_index()
    st.markdown("### Strategy scorecard")
    st.dataframe(strategies.sort_values("net_pnl",ascending=False),use_container_width=True,hide_index=True)
    st.markdown("### Setup notes")
    notes=d[d.setup.fillna("").astype(str).str.strip()!=""][["symbol","setup","strategy","emotion","pnl","reason_entry","reason_exit","decision_making","outcome_decision","confluences","notes","lessons"]]
    if notes.empty: st.caption("Belum ada setup notes. Isi saat menambahkan trade.")
    else: st.dataframe(notes,use_container_width=True,hide_index=True)

def show_backup(d):
    page_header("Backup & Settings","Your data is stored in the cloud. Export backups regularly." if CLOUD_DB else "Your data stays on this computer. Export backups regularly.")
    st.markdown('<div class="panel"><b>Storage location</b><br><span class="small-muted">Supabase PostgreSQL · private cloud database.</span></div>' if CLOUD_DB else '<div class="panel"><b>Storage location</b><br><span class="small-muted">trades.db · screenshots/ · in this application folder. No cloud account or external server is used.</span></div>',unsafe_allow_html=True)
    st.markdown("### Export")
    st.caption("CSV export includes all stored records, including archived rows excluded from performance metrics.")
    if not d.empty:
        st.download_button("Download trades CSV",d.to_csv(index=False).encode("utf-8-sig"),"trade_journal_backup.csv","text/csv")
    if not CLOUD_DB and DB_PATH.exists():
        st.download_button("Download SQLite database",DB_PATH.read_bytes(),"trades_backup.db","application/octet-stream")
    st.markdown("### Restore CSV backup")
    backup=st.file_uploader("Select a previously exported trade CSV",type=["csv"],key="restore")
    if backup and st.button("Append backup records"):
        old=pd.read_csv(backup)
        if not {"symbol","direction","pnl"}.issubset(old.columns): st.error("Backup file missing required columns.")
        else:
            inserted=0
            for _,r in old.iterrows():
                ticket=str(r.get("ticket","") or "")
                with db() as con:
                    exists=con.execute("SELECT 1 FROM trades WHERE ticket=%s AND ticket!=''" if CLOUD_DB else "SELECT 1 FROM trades WHERE ticket=? AND ticket!=''",(ticket,)).fetchone() if ticket else None
                if exists: continue
                fields=["ticket","symbol","direction","open_time","close_time","entry","exit","volume","sl","tp","pnl","commission","swap","strategy","session","setup","emotion","followed_plan","notes","screenshot"]
                item={}
                for k in fields:
                    val=r.get(k,"")
                    item[k]="" if pd.isna(val) else val
                add_trade(item); inserted+=1
            st.success(f"{inserted} records appended."); st.rerun()
    st.markdown("### Data safety")
    st.warning("Database cloud disimpan di Supabase. Export CSV secara berkala. File screenshot lokal tidak ikut tersinkronisasi di hosting cloud." if CLOUD_DB else "Jangan hapus trades.db atau folder screenshots. Sebelum mengganti versi aplikasi, buat backup database terlebih dahulu.")

# ---------- Routes ----------
if page=="Overview": show_overview(df)
elif page=="Calendar": show_calendar(df)
elif page=="Trade Journal": show_journal(df)
elif page=="Add Trade": show_add()
elif page=="Import MT5": show_import()
elif page=="Analytics": show_analytics(df)
elif page=="Reports": show_reports(df)
elif page=="Playbook": show_playbook(df)
elif page=="Backup & Settings": show_backup(df)
