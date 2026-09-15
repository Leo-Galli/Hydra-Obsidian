import sys, os, time, json, uuid, socket, threading, hashlib, hmac, atexit, subprocess, platform, html, math, random
from datetime import datetime, timedelta
import psutil
import streamlit as st
import plotly.graph_objects as go
import zmq
from collections import deque

VERSION = "V3.4.0"
DEMO_SECRET = b"HYDRA_DEMO_SANDBOX"
UI_PORT = 8501
CODENAME = "HYDRA"
TCP_PORT = 5555
UDP_PORT = 5556
WORKER_UDP_PORT = 5557
BT_SSID = "HYDRA_COMMAND_CENTER"
NODE_TIMEOUT_SEC = 10
REFRESH_SEC = 2
DISCOVERY_SEC = 3
PEER_TTL_SEC = 45
CMD_TIMEOUT_SEC = 30
CMD_MAX_LEN = 4096
EXEC_RESULT_TTL = 60
INVALID_LOG_COOLDOWN = 15
MIN_KEY_LEN = 8

T = {
    "bg": "#030712",
    "bg2": "#0a0f1a",
    "surface": "#0f1623",
    "surface2": "#151d2e",
    "surface3": "#1c2738",
    "border": "#243044",
    "border_hi": "#334155",
    "primary": "#22d3ee",
    "primary_dim": "#06b6d4",
    "primary_glow": "rgba(34,211,238,0.16)",
    "accent": "#4ade80",
    "accent_dim": "#22c55e",
    "accent_glow": "rgba(74,222,128,0.12)",
    "violet": "#818cf8",
    "violet_glow": "rgba(129,140,248,0.14)",
    "text": "#f8fafc",
    "text2": "#cbd5e1",
    "muted": "#64748b",
    "warn": "#facc15",
    "error": "#fb7185",
    "demo": "#e879f9",
}


def pack_payload(obj: dict) -> bytes:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sign_payload(payload: bytes, key: bytes) -> bytes:
    return hmac.new(key, payload, hashlib.sha256).digest()


def verify_payload(payload: bytes, sig: bytes, key: bytes) -> bool:
    return hmac.compare_digest(sign_payload(payload, key), sig)


def parse_zmq_parts(parts: list):
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return None, None


def resolve_key_from_env():
    env = os.environ.get("HYDRA_SECRET", "").strip()
    if len(env) >= MIN_KEY_LEN:
        return env.encode("utf-8")
    return None


def resolve_key_from_argv():
    if len(sys.argv) > 2:
        arg = sys.argv[2].strip().lower()
        if arg == "demo":
            return DEMO_SECRET
        key = sys.argv[2].strip()
        if len(key) >= MIN_KEY_LEN:
            return key.encode("utf-8")
    return None


def is_demo_mode() -> bool:
    if st.session_state.get("demo_mode"):
        return True
    if len(sys.argv) > 2 and sys.argv[2].strip().lower() == "demo":
        return True
    return get_cluster_key() == DEMO_SECRET


def get_cluster_key():
    return st.session_state.get("cluster_key")


def set_cluster_key(key: bytes):
    st.session_state.cluster_key = key


def apply_styles():
    st.set_page_config(page_title=f"{CODENAME} {VERSION}", layout="wide", initial_sidebar_state="expanded")
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
    :root {{
        --bg:{T['bg']}; --bg2:{T['bg2']}; --surface:{T['surface']}; --surface2:{T['surface2']};
        --border:{T['border']}; --primary:{T['primary']}; --accent:{T['accent']};
        --text:{T['text']}; --text2:{T['text2']}; --muted:{T['muted']};
    }}
    html,body,[class*="css"] {{
        background-color:var(--bg)!important;
        background-image:
            linear-gradient(rgba(34,211,238,.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(34,211,238,.03) 1px, transparent 1px),
            radial-gradient(ellipse 80% 50% at 50% -20%, rgba(34,211,238,.12), transparent),
            radial-gradient(ellipse 60% 40% at 100% 0%, rgba(129,140,248,.08), transparent)!important;
        background-size:48px 48px, 48px 48px, 100% 100%, 100% 100%!important;
        color:var(--text); font-family:'Plus Jakarta Sans',system-ui,sans-serif;
    }}
    #MainMenu,footer,header {{ visibility:hidden; }}
    .block-container {{ padding:20px 28px 56px; max-width:1520px; }}
    [data-testid="stSidebar"] {{
        background:linear-gradient(180deg, {T['surface2']} 0%, {T['bg']} 100%)!important;
        border-right:1px solid {T['border']}!important;
    }}
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label {{ color:{T['text2']}!important; }}
    [data-testid="stSidebar"] code {{ background:{T['surface3']}!important; color:{T['primary']}!important; border:1px solid {T['border']}; border-radius:8px; }}

    .hero {{
        position:relative; overflow:hidden; margin-bottom:28px;
        background:linear-gradient(135deg, rgba(15,22,35,.95) 0%, rgba(21,29,46,.9) 100%);
        border:1px solid {T['border_hi']}; border-radius:24px; padding:32px 36px;
        box-shadow:0 32px 64px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.06);
        backdrop-filter:blur(12px);
    }}
    .hero::before {{
        content:''; position:absolute; top:-50%; right:-10%; width:420px; height:420px;
        background:radial-gradient(circle, {T['primary_glow']}, transparent 70%);
        pointer-events:none;
    }}
    .hero-mark {{ display:flex; align-items:center; gap:20px; position:relative; z-index:1; }}
    .logo {{
        width:56px; height:56px; border-radius:16px; flex-shrink:0;
        background:linear-gradient(135deg, {T['primary_dim']}, {T['violet']});
        display:flex; align-items:center; justify-content:center;
        font-weight:800; font-size:22px; color:{T['bg']};
        box-shadow:0 8px 32px {T['primary_glow']}, inset 0 1px 0 rgba(255,255,255,.2);
    }}
    .shell-eyebrow {{ font-size:10px; font-weight:700; letter-spacing:.16em; text-transform:uppercase; color:{T['primary']}; margin-bottom:4px; }}
    .shell-title {{ font-size:36px; font-weight:800; letter-spacing:-.04em; margin:0 0 4px; line-height:1.1;
        background:linear-gradient(135deg, #fff 0%, {T['text2']} 100%);
        -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
    .shell-sub {{ color:var(--text2); font-size:14px; margin:0; line-height:1.6; max-width:640px; }}
    .shell-row {{ display:flex; align-items:center; justify-content:space-between; gap:24px; flex-wrap:wrap; position:relative; z-index:1; }}
    .pill {{ display:inline-flex; align-items:center; gap:8px; padding:9px 16px; border-radius:999px; font-size:11px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; border:1px solid; }}
    .pill-ok {{ color:var(--accent); background:{T['accent_glow']}; border-color:rgba(74,222,128,.35); }}
    .pill-live {{ color:var(--primary); background:{T['primary_glow']}; border-color:rgba(34,211,238,.35); }}
    .pill-demo {{ color:{T['demo']}; background:{T['violet_glow']}; border-color:rgba(232,121,249,.35); }}
    .dot {{ width:6px; height:6px; border-radius:50%; background:currentColor; box-shadow:0 0 10px currentColor; }}
    .dot-pulse {{ animation:pulse 2s ease-in-out infinite; }}
    @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.35}} }}
    @media(prefers-reduced-motion:reduce){{ .dot-pulse{{animation:none}} }}

    .stats {{ display:grid; grid-template-columns:repeat(5,1fr); gap:16px; margin-bottom:28px; }}
    @media(max-width:1100px){{ .stats{{grid-template-columns:repeat(3,1fr);}} }}
    @media(max-width:700px){{ .stats{{grid-template-columns:repeat(2,1fr);}} }}
    .stat {{
        background:linear-gradient(180deg, {T['surface2']} 0%, {T['surface']} 100%);
        border:1px solid {T['border']}; border-radius:16px; padding:20px;
        position:relative; overflow:hidden;
        box-shadow:0 4px 24px rgba(0,0,0,.25);
        transition:border-color .2s, transform .2s;
    }}
    .stat:hover {{ border-color:{T['border_hi']}; transform:translateY(-2px); }}
    .stat::after {{ content:''; position:absolute; top:0; left:0; right:0; height:2px;
        background:linear-gradient(90deg, transparent, var(--stat-accent, {T['primary']}), transparent); opacity:.8; }}
    .stat-lbl {{ font-size:10px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); margin-bottom:8px; }}
    .stat-val {{ font-size:28px; font-weight:800; letter-spacing:-.03em; color:var(--stat-accent, {T['primary']}); line-height:1; }}
    .stat-sub {{ font-size:11px; color:var(--muted); margin-top:6px; }}

    [data-testid="stVerticalBlockBorderWrapper"] {{
        background:linear-gradient(180deg, {T['surface2']} 0%, {T['surface']} 100%)!important;
        border:1px solid {T['border']}!important; border-radius:20px!important;
        padding:20px!important; margin-bottom:16px!important;
        box-shadow:0 8px 32px rgba(0,0,0,.3)!important;
        transition:border-color .2s, box-shadow .2s!important;
    }}
    [data-testid="stVerticalBlockBorderWrapper"]:hover {{
        border-color:{T['border_hi']}!important;
        box-shadow:0 12px 40px rgba(0,0,0,.35), 0 0 0 1px {T['primary_glow']}!important;
    }}

    .section {{ font-size:10px; font-weight:800; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); margin:0 0 20px; display:flex; align-items:center; gap:12px; }}
    .section::after {{ content:''; flex:1; height:1px; background:linear-gradient(90deg, {T['border_hi']}, transparent); }}
    .node-top {{ display:flex; justify-content:space-between; align-items:flex-start; gap:16px; padding-bottom:16px; margin-bottom:16px; border-bottom:1px solid {T['border']}; }}
    .node-left {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
    .tag {{ font-family:'JetBrains Mono',monospace; font-size:9px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; padding:5px 10px; border-radius:6px; border:1px solid {T['border']}; color:var(--text2); background:{T['surface3']}; }}
    .tag-live {{ color:var(--accent); border-color:rgba(74,222,128,.3); background:{T['accent_glow']}; }}
    .tag-demo {{ color:{T['demo']}; border-color:rgba(232,121,249,.3); background:{T['violet_glow']}; }}
    .node-title {{ font-size:18px; font-weight:700; letter-spacing:-.02em; }}
    .gauge-row {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:16px; }}
    @media(max-width:900px){{ .gauge-row{{grid-template-columns:repeat(2,1fr);}} }}
    .gauge {{ text-align:center; padding:12px 8px; background:{T['surface3']}; border-radius:14px; border:1px solid {T['border']}; }}
    .gauge svg {{ display:block; margin:0 auto 8px; }}
    .gauge-lbl {{ font-size:9px; font-weight:700; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); }}
    .gauge-val {{ font-size:13px; font-weight:700; font-family:'JetBrains Mono',monospace; margin-top:4px; }}
    .gauge-val.cyan {{ color:{T['primary']}; }} .gauge-val.green {{ color:{T['accent']}; }} .gauge-val.amber {{ color:{T['warn']}; }}
    .node-meta {{ display:flex; gap:16px; flex-wrap:wrap; padding:12px 16px; background:{T['surface3']}; border-radius:12px; border:1px solid {T['border']}; margin-bottom:16px; }}
    .node-meta-item {{ font-size:12px; color:var(--text2); }}
    .node-meta-item strong {{ color:var(--text); font-weight:600; display:block; font-size:10px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin-bottom:2px; }}

    .panel {{ border:1px solid {T['border']}; border-radius:16px; overflow:hidden; background:{T['surface']}; box-shadow:0 20px 48px rgba(0,0,0,.35); }}
    .panel-bar {{ display:flex; align-items:center; gap:10px; padding:14px 18px; background:{T['surface3']}; border-bottom:1px solid {T['border']}; }}
    .traffic {{ display:flex; gap:7px; }}
    .traffic span {{ width:11px; height:11px; border-radius:50%; box-shadow:inset 0 -2px 4px rgba(0,0,0,.2); }}
    .t-red {{ background:#ff5f57; }} .t-yellow {{ background:#febc2e; }} .t-green {{ background:#28c840; }}
    .panel-title {{ font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:500; color:var(--muted); margin-left:6px; }}
    .panel-body {{ padding:18px; font-family:'JetBrains Mono',monospace; font-size:12px; line-height:1.8; color:var(--text2); overflow-y:auto; height:420px; white-space:pre-wrap; }}
    .panel-body.tall {{ height:500px; }}
    .log-ok{{color:{T['accent']}}} .log-warn{{color:{T['warn']}}} .log-err{{color:{T['error']}}} .log-info{{color:{T['primary']}}}

    .banner {{ display:flex; align-items:flex-start; gap:14px; padding:16px 20px; border:1px solid {T['border']}; border-radius:16px; background:{T['surface2']}; margin-bottom:24px; }}
    .banner-demo {{ border-color:rgba(232,121,249,.25); background:linear-gradient(135deg, rgba(232,121,249,.06), {T['surface2']}); }}
    .banner-text {{ font-size:13px; color:var(--text2); line-height:1.6; }}
    .banner-text strong {{ color:var(--text); }}
    .peer-wrap {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:24px; }}
    .peer {{ display:inline-flex; align-items:center; gap:8px; padding:8px 14px; border-radius:10px; border:1px solid {T['border']}; background:{T['surface3']}; font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--text2); }}

    .gate {{ max-width:520px; margin:48px auto; padding:40px; background:{T['surface2']}; border:1px solid {T['border_hi']}; border-radius:24px; box-shadow:0 32px 64px rgba(0,0,0,.4); }}
    .gate-title {{ font-size:28px; font-weight:800; margin:0 0 8px; letter-spacing:-.03em; }}
    .gate-sub {{ color:var(--text2); font-size:14px; margin:0 0 28px; line-height:1.7; }}
    .gate-code {{ display:block; margin-top:10px; padding:12px 16px; background:{T['bg']}; border:1px solid {T['border']}; border-radius:10px; font-family:'JetBrains Mono',monospace; font-size:11px; color:{T['primary']}; }}

    .warn-box {{ background:rgba(251,113,133,.06); border:1px solid rgba(251,113,133,.2); border-radius:16px; padding:16px 20px; margin-bottom:20px; }}
    .warn-title {{ font-size:10px; font-weight:800; letter-spacing:.1em; text-transform:uppercase; color:{T['error']}; margin-bottom:6px; }}
    .warn-text {{ font-size:13px; color:var(--text2); line-height:1.6; }}

    .cmd-chips {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:16px; }}
    .cmd-chip {{ font-family:'JetBrains Mono',monospace; font-size:11px; padding:6px 12px; border-radius:8px; border:1px solid {T['border']}; background:{T['surface3']}; color:{T['primary']}; }}

    .steps {{ display:flex; margin-bottom:28px; border:1px solid {T['border']}; border-radius:16px; overflow:hidden; background:{T['surface']}; }}
    .step {{ flex:1; text-align:center; padding:20px 12px; border-right:1px solid {T['border']}; }}
    .step:last-child {{ border-right:none; }}
    .step.active {{ background:{T['primary_glow']}; }}
    .step.done {{ background:{T['accent_glow']}; }}
    .step-num {{ width:36px; height:36px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; font-weight:800; font-size:14px; border:2px solid {T['border']}; margin-bottom:8px; }}
    .step.active .step-num {{ border-color:var(--primary); color:var(--primary); }}
    .step.done .step-num {{ border-color:var(--accent); background:var(--accent); color:{T['bg']}; }}
    .step-lbl {{ font-size:10px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }}

    .stButton>button {{
        background:{T['surface3']}!important; border:1px solid {T['border']}!important;
        color:var(--text)!important; border-radius:12px!important; min-height:44px!important;
        font-weight:600!important; font-family:'Plus Jakarta Sans',sans-serif!important;
        transition:all .15s ease!important;
    }}
    .stButton>button:hover {{ border-color:var(--primary)!important; color:var(--primary)!important; background:{T['primary_glow']}!important; }}
    .stButton>button[kind="primary"] {{ background:linear-gradient(135deg,{T['primary_dim']},{T['primary']})!important; border:none!important; color:{T['bg']}!important; }}
    [data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea,[data-testid="stSelectbox"] div[data-baseweb="select"]>div {{
        background:{T['surface3']}!important; border:1px solid {T['border']}!important;
        border-radius:12px!important; color:var(--text)!important;
    }}
    div[data-testid="stProgressBar"] {{ display:none!important; }}
    [data-testid="stTabs"] {{ background:{T['surface2']}; border-radius:14px; padding:4px; border:1px solid {T['border']}; }}
    [data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap:4px; background:transparent; }}
    [data-testid="stTabs"] button {{ font-weight:700!important; font-size:13px!important; border-radius:10px!important; padding:10px 20px!important; }}
    [data-testid="stTabs"] [aria-selected="true"] {{ background:{T['primary_glow']}!important; color:var(--primary)!important; border-color:transparent!important; }}
    [data-testid="stAlert"], .stAlert {{ border-radius:12px!important; border:1px solid {T['border']}!important; }}
    </style>
    """, unsafe_allow_html=True)


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def get_dashboard_urls() -> dict:
    ip = get_local_ip()
    return {
        "local": f"http://127.0.0.1:{UI_PORT}",
        "network": f"http://{ip}:{UI_PORT}",
        "ip": ip,
    }


def get_system_meta() -> dict:
    return {"os": platform.system(), "release": platform.release(), "arch": platform.machine()}


def send_udp(msg: bytes, port: int):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for dest in [("<broadcast>", port), ("127.0.0.1", port)]:
            try:
                s.sendto(msg, dest)
            except Exception:
                pass


def discover_master_udp(timeout: float = 2.0):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("", UDP_PORT))
            s.settimeout(timeout)
            data, _ = s.recvfrom(1024)
            parts = data.decode().split("|")
            if parts[0] == "HYDRA_BEACON" and len(parts) >= 3:
                return parts[2]
    except Exception:
        pass
    return None


def run_shell_command(command: str) -> dict:
    shell_exe = os.environ.get("COMSPEC", "cmd.exe") if sys.platform == "win32" else "/bin/sh"
    try:
        proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=CMD_TIMEOUT_SEC, executable=shell_exe, cwd=os.path.expanduser("~"))
        return {"stdout": proc.stdout or "", "stderr": proc.stderr or "", "exit_code": proc.returncode, "os": platform.system()}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Timeout ({CMD_TIMEOUT_SEC}s)", "exit_code": -1, "os": platform.system()}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": -1, "os": platform.system()}


def build_chart(values, height=180, title="CPU 60s"):
    fig = go.Figure()
    y = list(values) if values else [0]
    fig.add_trace(go.Scatter(
        x=list(range(len(y))), y=y, fill="tozeroy",
        fillcolor="rgba(34,211,238,0.08)",
        line=dict(color=T["primary"], width=2, shape="spline", smoothing=1.2),
        mode="lines",
    ))
    fig.update_layout(
        height=height,
        title=dict(text=title, font=dict(size=10, color=T["muted"], family="Plus Jakarta Sans"), x=0, xanchor="left"),
        margin=dict(l=40, r=12, t=36, b=28),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(
            gridcolor="rgba(100,116,139,0.12)", zeroline=False,
            range=[0, 100], ticksuffix="%", nticks=5,
            tickfont=dict(size=9, color=T["muted"]),
        ),
        showlegend=False, hovermode="x unified",
    )
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _gauge_color(val: float) -> str:
    if val >= 80:
        return T["warn"]
    if val >= 55:
        return T["primary"]
    return T["accent"]


def _gauge_class(val: float) -> str:
    if val >= 80:
        return "amber"
    if val >= 55:
        return "cyan"
    return "green"


def render_gauge_svg(val: float, size: int = 72) -> str:
    val = max(0, min(100, val))
    color = _gauge_color(val)
    r = (size - 10) / 2
    circ = 2 * math.pi * r
    offset = circ * (1 - val / 100)
    cx, cy = size / 2, size / 2
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
    <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{T['border']}" stroke-width="5"/>
    <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="5"
        stroke-dasharray="{circ:.1f}" stroke-dashoffset="{offset:.1f}"
        stroke-linecap="round" transform="rotate(-90 {cx} {cy})"/>
    <text x="{cx}" y="{cy + 5}" text-anchor="middle" fill="{color}" font-size="13" font-weight="700" font-family="JetBrains Mono">{val:.0f}</text>
    </svg>"""


def render_stat_row(nodes: int, peers: int, avg_cpu: float, avg_ram: float, uptime: str):
    items = [
        ("Nodi attivi", str(nodes), "online", T["accent"]),
        ("Peer UDP", str(peers), "discovery", T["violet"]),
        ("CPU media", f"{avg_cpu}%", "cluster", T["primary"]),
        ("RAM media", f"{avg_ram}%", "cluster", T["primary"]),
        ("Uptime", uptime, "master", T["accent"]),
    ]
    cards = "".join(
        f'<div class="stat" style="--stat-accent:{accent}"><div class="stat-lbl">{html.escape(lbl)}</div>'
        f'<div class="stat-val">{html.escape(val)}</div><div class="stat-sub">{html.escape(sub)}</div></div>'
        for lbl, val, sub, accent in items
    )
    st.markdown(f'<div class="stats">{cards}</div>', unsafe_allow_html=True)


FAKE_NODES_SPEC = [
    {"id": "HYDRA-NODE-A1B2C3", "host": "nexus-core", "ip": "10.0.0.12", "os": "Linux", "release": "6.8.0", "arch": "x86_64", "phase": 0.0, "cpu_base": 28, "ram_base": 54},
    {"id": "HYDRA-NODE-D4E5F6", "host": "edge-gateway", "ip": "10.0.0.24", "os": "Linux", "release": "6.5.0", "arch": "aarch64", "phase": 1.4, "cpu_base": 15, "ram_base": 38},
    {"id": "HYDRA-NODE-G7H8I9", "host": "win-ops-01", "ip": "10.0.0.31", "os": "Windows", "release": "11", "arch": "AMD64", "phase": 2.2, "cpu_base": 47, "ram_base": 71},
    {"id": "HYDRA-NODE-J0K1L2", "host": "vault-db", "ip": "10.0.0.40", "os": "Linux", "release": "6.8.0", "arch": "x86_64", "phase": 0.9, "cpu_base": 62, "ram_base": 83},
]

DEMO_QUICK_CMDS = ["fastfetch", "ls -la", "cat /etc/os-release", "whoami", "hostname", "uptime", "dir", "type README.md"]


def demo_exec_response(host: str, os_name: str, command: str) -> dict:
    cmd = command.strip().lower()
    if cmd in ("fastfetch", "fastfetch --logo none"):
        art = r"""
   ▄▄▄▄▄▄▄  nexus-core  ▄▄▄▄▄▄▄
  █ HYDRA █  Linux 6.8  █ DEMO  █
   ▀▀▀▀▀▀▀  x86_64      ▀▀▀▀▀▀▀
  OS       Ubuntu 24.04 LTS
  Host     """ + host + r"""
  Kernel   6.8.0-45-generic
  Uptime   14 days, 6 hours
  CPU      AMD EPYC 7543 (8) @ 3.4GHz
  Memory   12.4 GiB / 32 GiB
  Disk     214 GiB / 512 GiB (42%)
"""
        return {"stdout": art.strip(), "stderr": "", "exit_code": 0}
    if cmd in ("ls", "ls -la", "ls -lah"):
        return {"stdout": "total 48\ndrwxr-xr-x  5 root root 4096 Sep 15 18:00 .\ndrwxr-xr-x 18 root root 4096 Sep  1 09:00 ..\n-rw-r--r--  1 root root  220 Sep  1 09:00 .bash_logout\n-rw-r--r--  1 root root 3526 Sep  1 09:00 .bashrc\ndrwxr-xr-x  3 root root 4096 Sep 10 14:22 hydra\n-rw-r--r--  1 root root  807 Sep  1 09:00 .profile\ndrwxr-xr-x  2 root root 4096 Sep 12 11:05 scripts\n-rwxr-xr-x  1 root root 8192 Sep 14 20:30 worker.sh", "stderr": "", "exit_code": 0}
    if "cat" in cmd and ("os-release" in cmd or "etc" in cmd):
        return {"stdout": 'PRETTY_NAME="Ubuntu 24.04.1 LTS"\nNAME="Ubuntu"\nVERSION_ID="24.04"\nID=ubuntu\nHOME_URL="https://ubuntu.com/"', "stderr": "", "exit_code": 0}
    if cmd == "whoami":
        user = "Administrator" if os_name == "Windows" else "root"
        return {"stdout": user, "stderr": "", "exit_code": 0}
    if cmd == "hostname":
        return {"stdout": host, "stderr": "", "exit_code": 0}
    if cmd == "uptime":
        return {"stdout": " 20:37:12 up 14 days,  6:22,  2 users,  load average: 0.42, 0.38, 0.35", "stderr": "", "exit_code": 0}
    if cmd in ("dir", "dir /w"):
        return {"stdout": " Volume in drive C is OS\n Directory of C:\\Users\\Admin\n\n09/15/2026  08:00 PM    <DIR>          .\n09/15/2026  08:00 PM    <DIR>          ..\n09/14/2026  03:15 PM             1,024 hydra-worker.log\n09/15/2026  07:30 PM    <DIR>          Projects\n               1 File(s)          1,024 bytes", "stderr": "", "exit_code": 0}
    if cmd.startswith("type ") or cmd.startswith("cat "):
        fname = command.split(maxsplit=1)[1] if " " in command else "file"
        return {"stdout": f"# {fname}\n\nHydra-Obsidian v3.3 — distributed monitoring\nMode: demo sandbox\nNode: {host}", "stderr": "", "exit_code": 0}
    if cmd == "ps aux" or cmd == "ps":
        return {"stdout": "USER       PID  CPU MEM COMMAND\nroot         1  0.0 0.1 /sbin/init\nroot       412  0.2 1.2 hydra-worker\nroot       891  0.1 0.8 sshd\nroot      1204  0.0 0.3 fastfetch", "stderr": "", "exit_code": 0}
    if cmd == "free -h":
        return {"stdout": "               total        used        free\nMem:            32Gi        12Gi        19Gi\nSwap:           8.0Gi          0B       8.0Gi", "stderr": "", "exit_code": 0}
    return {"stdout": f"[demo] {host}$ {command}\nCommand simulated in sandbox mode.", "stderr": "", "exit_code": 0}


def format_log_line(line: str) -> str:
    esc = html.escape(line)
    if any(k in line for k in ("ERRORE", "INVALIDA", "RIFIUTATO")):
        return f'<span class="log-err">{esc}</span>'
    if "HANDSHAKE" in line or "EXEC OK" in line:
        return f'<span class="log-ok">{esc}</span>'
    if "PEER" in line or "DISCOVERY" in line:
        return f'<span class="log-info">{esc}</span>'
    if "EXEC" in line or "WARN" in line:
        return f'<span class="log-warn">{esc}</span>'
    return esc


def render_header(title: str, subtitle: str, status: str = "", live: str = "", demo: bool = False):
    status_html = f'<span class="pill pill-ok"><span class="dot"></span>{html.escape(status)}</span>' if status else ""
    live_html = f'<span class="pill pill-live"><span class="dot dot-pulse"></span>{html.escape(live)}</span>' if live else ""
    demo_html = '<span class="pill pill-demo"><span class="dot dot-pulse"></span>Sandbox</span>' if demo else ""
    st.markdown(f"""
    <div class="hero"><div class="shell-row">
    <div class="hero-mark"><div class="logo">H</div><div>
    <div class="shell-eyebrow">Infrastructure Control Plane</div>
    <h1 class="shell-title">{html.escape(title)}</h1>
    <p class="shell-sub">{html.escape(subtitle)}</p></div></div>
    <div style="display:flex;flex-direction:column;gap:8px;align-items:flex-end">{demo_html}{status_html}{live_html}</div>
    </div></div>
    """, unsafe_allow_html=True)


def render_key_gate(mode: str):
    st.markdown(f"""
    <div class="gate">
    <h2 class="gate-title">Configura chiave cluster</h2>
    <p class="gate-sub">La chiave non e piu nel codice sorgente. Usa la stessa password su Master e Worker,
    oppure avvia la demo sandbox con nodi simulati. Minimo {MIN_KEY_LEN} caratteri per produzione.</p></div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        key = st.text_input("Chiave cluster", type="password", placeholder="Inserisci la tua chiave segreta")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Avvia " + mode.upper(), width="stretch"):
                if len(key.strip()) >= MIN_KEY_LEN:
                    st.session_state.demo_mode = False
                    set_cluster_key(key.strip().encode("utf-8"))
                    st.rerun()
                else:
                    st.error(f"Chiave troppo corta (min {MIN_KEY_LEN} caratteri).")
        with b2:
            if st.button("Avvia DEMO", width="stretch"):
                st.session_state.demo_mode = True
                set_cluster_key(DEMO_SECRET)
                st.rerun()
        st.markdown(f"""
        <span class="gate-code">streamlit run main.py -- {mode} TUA_CHIAVE</span>
        <span class="gate-code">streamlit run main.py -- {mode} demo</span>
        <span class="gate-code">set HYDRA_SECRET=TUA_CHIAVE</span>
        """, unsafe_allow_html=True)
    st.stop()


def ensure_cluster_key(mode: str) -> bytes:
    if len(sys.argv) > 2 and sys.argv[2].strip().lower() == "demo":
        st.session_state.demo_mode = True
    if "cluster_key" not in st.session_state:
        argv_key = resolve_key_from_argv()
        env_key = resolve_key_from_env()
        if argv_key:
            if argv_key == DEMO_SECRET:
                st.session_state.demo_mode = True
            set_cluster_key(argv_key)
        elif env_key:
            set_cluster_key(env_key)
    key = get_cluster_key()
    if not key:
        render_key_gate(mode)
    return key


class HydraMaster:
    def __init__(self, secret_key: bytes):
        self.secret_key = secret_key
        self.nodes = {}
        self.peers = {}
        self.events = deque(maxlen=300)
        self.terminal_log = deque(maxlen=200)
        self.pending_exec = {}
        self.lock = threading.Lock()
        self.active = True
        self._socket_ok = False
        self._last_invalid_log = 0.0
        self._invalid_count = 0
        self.started_at = datetime.now()
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(zmq.ROUTER)
        self.socket.setsockopt(zmq.LINGER, 0)
        try:
            self.socket.bind(f"tcp://0.0.0.0:{TCP_PORT}")
            self._socket_ok = True
            self.events.appendleft(f"[{self._ts()}] Backend ZMQ attivo (porta {TCP_PORT})")
        except Exception as e:
            self._socket_ok = False
            self.events.appendleft(f"[{self._ts()}] Backend gia attivo o porta {TCP_PORT} occupata")

    def _ts(self):
        return datetime.now().strftime("%H:%M:%S")

    def _log_invalid_once(self):
        self._invalid_count += 1
        now = time.time()
        if now - self._last_invalid_log >= INVALID_LOG_COOLDOWN:
            self.events.appendleft(f"[{self._ts()}] FIRMA INVALIDA ({self._invalid_count} pacchetti scartati — verifica stessa chiave su Master/Worker)")
            self._invalid_count = 0
            self._last_invalid_log = now

    def launch(self):
        if not self._socket_ok:
            return
        threading.Thread(target=self._beacon_loop, daemon=True).start()
        threading.Thread(target=self._collector_loop, daemon=True).start()
        threading.Thread(target=self._peer_listener, daemon=True).start()
        self.events.appendleft(f"[{self._ts()}] Discovery UDP attivo")

    def _beacon_loop(self):
        while self.active:
            send_udp(f"HYDRA_BEACON|{BT_SSID}|{get_local_ip()}".encode(), UDP_PORT)
            time.sleep(2)

    def _peer_listener(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("", WORKER_UDP_PORT))
            except Exception as e:
                self.events.appendleft(f"[{self._ts()}] Peer listener err: {e}")
                return
            s.settimeout(1.0)
            while self.active:
                try:
                    data, addr = s.recvfrom(1024)
                    parts = data.decode().split("|")
                    if parts[0] not in ("HYDRA_WORKER", "HYDRA_PROBE"):
                        continue
                    peer_ip = parts[-1] if len(parts) >= 4 else addr[0]
                    peer_host = parts[2] if len(parts) >= 3 else "?"
                    with self.lock:
                        is_new = peer_ip not in self.peers
                        self.peers[peer_ip] = {"host": peer_host, "ip": peer_ip, "last": time.time()}
                        if is_new:
                            self.events.appendleft(f"[{self._ts()}] PEER: {peer_host} @ {peer_ip}")
                except socket.timeout:
                    pass
                except Exception:
                    pass
                self._expire_peers()

    def _expire_peers(self):
        now = time.time()
        with self.lock:
            for ip in [ip for ip, p in self.peers.items() if now - p["last"] > PEER_TTL_SEC]:
                del self.peers[ip]

    def _collector_loop(self):
        while self.active:
            try:
                if self.socket.poll(500, zmq.POLLIN):
                    parts = self.socket.recv_multipart(flags=zmq.NOBLOCK)
                    payload, sig = parse_zmq_parts(parts)
                    if not payload or not sig:
                        continue
                    if not verify_payload(payload, sig, self.secret_key):
                        self._log_invalid_once()
                        continue
                    data = json.loads(payload.decode("utf-8"))
                    if data.get("t") == "tel":
                        self._sync_node(parts[0], data)
                    elif data.get("t") == "exec_result":
                        self._store_exec_result(data)
            except zmq.Again:
                pass
            except Exception as e:
                self.events.appendleft(f"[{self._ts()}] Collector err: {e}")
            self._expire_pending()

    def _sync_node(self, identity, data):
        nid = data.get("id", "UNKNOWN")
        ip = data.get("ip", "?")
        with self.lock:
            is_new = nid not in self.nodes
            self.nodes[nid] = {"host": data.get("host", "?"), "ip": ip, "stats": data.get("s", {}), "history": data.get("h", []), "meta": data.get("meta", {}), "identity": identity, "last": time.time()}
            self.peers.pop(ip, None)
            if is_new:
                self.events.appendleft(f"[{self._ts()}] HANDSHAKE OK: {data.get('host', '?')} ({nid}) @ {ip}")

    def _store_exec_result(self, data):
        entry = {"host": data.get("host", "?"), "command": data.get("command", ""), "stdout": data.get("stdout", ""), "stderr": data.get("stderr", ""), "exit_code": data.get("exit_code", -1), "ts": self._ts()}
        with self.lock:
            self.terminal_log.appendleft(entry)
            self.pending_exec.pop(data.get("cmd_id", ""), None)
        self.events.appendleft(f"[{self._ts()}] EXEC OK: {entry['host']} exit={entry['exit_code']}")

    def _expire_pending(self):
        now = time.time()
        with self.lock:
            for cmd_id in [k for k, v in self.pending_exec.items() if now - v["sent_at"] > EXEC_RESULT_TTL]:
                self.pending_exec.pop(cmd_id)

    def send_command(self, node_id: str, command: str):
        command = command.strip()
        if not command or len(command) > CMD_MAX_LEN:
            return None
        cmd_id = uuid.uuid4().hex[:12]
        with self.lock:
            node = self.nodes.get(node_id)
            if not node:
                return None
            identity, host = node["identity"], node["host"]
        raw = pack_payload({"t": "exec", "cmd_id": cmd_id, "command": command})
        try:
            self.socket.send_multipart([identity, b"", raw, sign_payload(raw, self.secret_key)])
        except Exception:
            return None
        with self.lock:
            self.pending_exec[cmd_id] = {"host": host, "sent_at": time.time()}
        return cmd_id

    def send_command_all(self, command: str):
        return [cid for nid in self.get_active_nodes() if (cid := self.send_command(nid, command))]

    def get_active_nodes(self):
        now = time.time()
        with self.lock:
            return {k: dict(v) for k, v in self.nodes.items() if now - v["last"] < NODE_TIMEOUT_SEC}

    def get_pending_peers(self):
        now = time.time()
        active_ips = {v["ip"] for v in self.nodes.values() if now - v["last"] < NODE_TIMEOUT_SEC}
        with self.lock:
            return {ip: dict(p) for ip, p in self.peers.items() if ip not in active_ips}

    def get_terminal_log(self):
        with self.lock:
            return list(self.terminal_log)

    def uptime(self):
        s = int((datetime.now() - self.started_at).total_seconds())
        h, r = divmod(s, 3600)
        m, sec = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def shutdown(self):
        self.active = False
        try:
            self.socket.close()
            self.ctx.term()
        except Exception:
            pass


class HydraDemoMaster:
    def __init__(self):
        self.secret_key = DEMO_SECRET
        self.nodes = {}
        self.peers = {}
        self.events = deque(maxlen=300)
        self.terminal_log = deque(maxlen=200)
        self.pending_exec = {}
        self.lock = threading.Lock()
        self.active = True
        self._socket_ok = True
        self.started_at = datetime.now()
        self._specs = [dict(s) for s in FAKE_NODES_SPEC]
        now = time.time()
        for spec in self._specs:
            hist = [max(5, min(95, spec["cpu_base"] + random.randint(-8, 8))) for _ in range(60)]
            self.nodes[spec["id"]] = {
                "host": spec["host"], "ip": spec["ip"],
                "stats": {"cpu": hist[-1], "ram": spec["ram_base"], "disk": random.randint(30, 75), "threads": random.randint(18, 64)},
                "history": hist,
                "meta": {"os": spec["os"], "release": spec["release"], "arch": spec["arch"]},
                "identity": spec["id"].encode(), "last": now, "demo": True,
            }
        self.peers = {
            "10.0.0.55": {"host": "probe-rpi", "ip": "10.0.0.55", "last": now},
            "10.0.0.61": {"host": "lab-nas", "ip": "10.0.0.61", "last": now - 5},
        }
        self.events.appendleft(f"[{self._ts()}] DEMO MODE — sandbox attivo (nessun backend reale)")
        for spec in self._specs:
            self.events.appendleft(f"[{self._ts()}] HANDSHAKE OK: {spec['host']} ({spec['id']}) @ {spec['ip']}")
        self.events.appendleft(f"[{self._ts()}] PEER: probe-rpi @ 10.0.0.55")

    def _ts(self):
        return datetime.now().strftime("%H:%M:%S")

    def launch(self):
        threading.Thread(target=self._sim_loop, daemon=True).start()

    def _sim_loop(self):
        tick = 0
        while self.active:
            t = time.time()
            with self.lock:
                for spec in self._specs:
                    nid = spec["id"]
                    node = self.nodes.get(nid)
                    if not node:
                        continue
                    wave = math.sin(t / 4 + spec["phase"]) * 12
                    spike = random.uniform(-4, 4)
                    cpu = max(3, min(96, spec["cpu_base"] + wave + spike))
                    ram = max(10, min(94, spec["ram_base"] + math.sin(t / 7 + spec["phase"]) * 6))
                    hist = list(node["history"])
                    hist.append(round(cpu, 1))
                    if len(hist) > 60:
                        hist = hist[-60:]
                    node["stats"] = {
                        "cpu": round(cpu, 1), "ram": round(ram, 1),
                        "disk": node["stats"]["disk"], "threads": node["stats"]["threads"] + random.randint(-1, 2),
                    }
                    node["history"] = hist
                    node["last"] = t
                for ip, p in self.peers.items():
                    p["last"] = t - random.randint(0, 3)
            tick += 1
            if tick == 4:
                self._auto_exec("HYDRA-NODE-A1B2C3", "fastfetch")
            elif tick == 12:
                self._auto_exec("HYDRA-NODE-G7H8I9", "dir")
            elif tick == 20:
                self._auto_exec("HYDRA-NODE-J0K1L2", "cat /etc/os-release")
            time.sleep(1.0)

    def _auto_exec(self, nid: str, command: str):
        with self.lock:
            node = self.nodes.get(nid)
            if not node:
                return
            host, os_name = node["host"], node["meta"]["os"]
        r = demo_exec_response(host, os_name, command)
        entry = {"host": host, "command": command, "stdout": r["stdout"], "stderr": r["stderr"], "exit_code": r["exit_code"], "ts": self._ts()}
        with self.lock:
            self.terminal_log.appendleft(entry)
        self.events.appendleft(f"[{self._ts()}] EXEC OK: {host} exit={r['exit_code']}")

    def send_command(self, node_id: str, command: str) -> str | None:
        command = command.strip()
        if not command or len(command) > CMD_MAX_LEN:
            return None
        with self.lock:
            node = self.nodes.get(node_id)
            if not node:
                return None
            host, os_name = node["host"], node["meta"]["os"]
        cmd_id = uuid.uuid4().hex[:12]
        r = demo_exec_response(host, os_name, command)
        entry = {"host": host, "command": command, "stdout": r["stdout"], "stderr": r["stderr"], "exit_code": r["exit_code"], "ts": self._ts()}
        with self.lock:
            self.terminal_log.appendleft(entry)
        self.events.appendleft(f"[{self._ts()}] EXEC OK: {host} exit={r['exit_code']}")
        return cmd_id

    def send_command_all(self, command: str):
        return [cid for nid in self.get_active_nodes() if (cid := self.send_command(nid, command))]

    def get_active_nodes(self):
        now = time.time()
        with self.lock:
            return {k: dict(v) for k, v in self.nodes.items() if now - v["last"] < NODE_TIMEOUT_SEC}

    def get_pending_peers(self):
        now = time.time()
        active_ips = {v["ip"] for v in self.nodes.values()}
        with self.lock:
            return {ip: dict(p) for ip, p in self.peers.items() if ip not in active_ips and now - p["last"] < PEER_TTL_SEC}

    def get_terminal_log(self):
        with self.lock:
            return list(self.terminal_log)

    def uptime(self):
        s = int((datetime.now() - self.started_at).total_seconds())
        h, r = divmod(s, 3600)
        m, sec = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def shutdown(self):
        self.active = False


class HydraWorker:
    def __init__(self, target_ip: str, secret_key: bytes):
        self.secret_key = secret_key
        self.id = f"HYDRA-NODE-{uuid.uuid4().hex[:6].upper()}"
        self.target = target_ip
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.DEALER)
        self.sock.setsockopt(zmq.LINGER, 0)
        self.sock.setsockopt_string(zmq.IDENTITY, self.id)
        self.lock = threading.Lock()
        self.cpu_history = deque([0] * 60, maxlen=60)
        self.connected = False
        self.error_msg = ""
        self.last_stats = {"cpu": 0, "ram": 0, "disk": 0, "threads": 0}
        self.meta = get_system_meta()

    def engage_link(self) -> bool:
        try:
            self.sock.connect(f"tcp://{self.target}:{TCP_PORT}")
            self.connected = True
            threading.Thread(target=self._loop, daemon=True).start()
            return True
        except Exception as e:
            self.error_msg = str(e)
            return False

    def disconnect(self):
        self.connected = False
        try:
            self.sock.close()
            self.ctx.term()
        except Exception:
            pass

    def announce(self):
        send_udp(f"HYDRA_PROBE|{self.id}|{socket.gethostname()}|{get_local_ip()}".encode(), WORKER_UDP_PORT)

    def _send(self, obj: dict):
        raw = pack_payload(obj)
        with self.lock:
            self.sock.send_multipart([b"", raw, sign_payload(raw, self.secret_key)])

    def _loop(self):
        psutil.cpu_percent(interval=None)
        disk = "C:\\" if sys.platform == "win32" else "/"
        last_tel = last_ann = 0.0
        while self.connected:
            try:
                with self.lock:
                    polled = self.sock.poll(100, zmq.POLLIN)
                if polled:
                    with self.lock:
                        parts = self.sock.recv_multipart(flags=zmq.NOBLOCK)
                    payload, sig = parse_zmq_parts(parts)
                    if payload and sig and verify_payload(payload, sig, self.secret_key):
                        msg = json.loads(payload.decode())
                        if msg.get("t") == "exec":
                            cmd = str(msg.get("command", "")).strip()[:CMD_MAX_LEN]
                            if cmd and msg.get("cmd_id"):
                                r = run_shell_command(cmd)
                                self._send({"t": "exec_result", "cmd_id": msg["cmd_id"], "id": self.id, "host": socket.gethostname(), "command": cmd, "stdout": r["stdout"][:65536], "stderr": r["stderr"][:65536], "exit_code": r["exit_code"], "os": r["os"]})
                now = time.time()
                if now - last_tel >= 1.0:
                    stats = {"cpu": psutil.cpu_percent(interval=None), "ram": psutil.virtual_memory().percent, "disk": psutil.disk_usage(disk).percent, "threads": threading.active_count()}
                    self.last_stats = stats
                    self.cpu_history.append(stats["cpu"])
                    self._send({"t": "tel", "id": self.id, "host": socket.gethostname(), "ip": get_local_ip(), "s": stats, "h": list(self.cpu_history), "meta": self.meta})
                    last_tel = now
                if now - last_ann >= 5.0:
                    send_udp(f"HYDRA_WORKER|{self.id}|{socket.gethostname()}|{get_local_ip()}".encode(), WORKER_UDP_PORT)
                    last_ann = now
            except zmq.ZMQError:
                self.connected = False
                break
            except Exception:
                pass


def render_node(nid, d, demo: bool = False):
    stats, meta = d["stats"], d.get("meta", {})
    cpu, ram, disk = float(stats.get("cpu", 0)), float(stats.get("ram", 0)), float(stats.get("disk", 0))
    threads = stats.get("threads", 0)
    live_tag = '<span class="tag tag-demo">Simulated</span>' if demo else '<span class="tag tag-live">Online</span>'
    gauges = "".join(
        f'<div class="gauge"><div class="gauge-lbl">{lbl}</div>{render_gauge_svg(v)}'
        f'<div class="gauge-val {_gauge_class(v)}">{v:.1f}%</div></div>'
        for lbl, v in [("CPU", cpu), ("RAM", ram), ("Disco", disk), ("Load", min(100, cpu * 0.85 + ram * 0.15))]
    )
    with st.container(border=True):
        st.markdown(f"""<div class="node-top"><div class="node-left">
        {live_tag}<span class="node-title">{html.escape(d['host'])}</span>
        <span class="tag">{html.escape(meta.get('os', '?'))}</span>
        <span class="tag">{html.escape(meta.get('arch', ''))}</span></div>
        <span class="tag">{html.escape(nid)}</span></div>
        <div class="node-meta">
        <div class="node-meta-item"><strong>IP</strong>{html.escape(d['ip'])}</div>
        <div class="node-meta-item"><strong>OS</strong>{html.escape(meta.get('os', '?'))} {html.escape(meta.get('release', ''))}</div>
        <div class="node-meta-item"><strong>Threads</strong>{threads}</div>
        </div>
        <div class="gauge-row">{gauges}</div>""", unsafe_allow_html=True)
        if d["history"]:
            st.plotly_chart(build_chart(d["history"], title=f"{d['host']} — CPU 60s"), width="stretch", key=f"c_{nid}", config={"displayModeBar": False})


@st.fragment(run_every=timedelta(seconds=REFRESH_SEC))
def live_master(m, demo: bool = False):
    active, pending = m.get_active_nodes(), m.get_pending_peers()
    avg_cpu = round(sum(n["stats"].get("cpu", 0) for n in active.values()) / max(len(active), 1), 1)
    avg_ram = round(sum(n["stats"].get("ram", 0) for n in active.values()) / max(len(active), 1), 1)

    render_stat_row(len(active), len(pending), avg_cpu, avg_ram, m.uptime())

    if demo:
        st.markdown(f"""<div class="banner banner-demo"><span class="dot dot-pulse" style="background:{T['demo']}"></span>
        <div class="banner-text"><strong>Demo sandbox</strong> — 4 nodi simulati con telemetria live e terminal remoto.
        Prova i comandi rapidi: fastfetch, ls, cat, whoami, dir. Nessun worker reale richiesto.</div></div>""", unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="banner"><span class="dot dot-pulse" style="background:{T["primary"]}"></span><div class="banner-text"><strong>Auto-discovery attivo</strong> — aggiornamento ogni {REFRESH_SEC}s via beacon UDP (no TCP scan)</div></div>', unsafe_allow_html=True)

    if pending:
        chips = "".join(f'<span class="peer"><span class="dot dot-pulse"></span>{html.escape(p["host"])} @ {html.escape(ip)}</span>' for ip, p in pending.items())
        st.markdown(f'<div class="section">Peer in rete</div><div class="peer-wrap">{chips}</div>', unsafe_allow_html=True)

    t1, t2 = st.tabs(["Monitoraggio", "Terminal remoto"])
    with t1:
        left, right = st.columns([1.55, 1])
        with left:
            st.markdown('<div class="section">Topologia cluster</div>', unsafe_allow_html=True)
            if not active:
                st.info("Nessun nodo connesso. Avvia worker con la stessa chiave cluster.")
            node_items = list(active.items())
            for i in range(0, len(node_items), 2):
                cols = st.columns(2)
                for j, col in enumerate(cols):
                    if i + j >= len(node_items):
                        break
                    nid, d = node_items[i + j]
                    with col:
                        render_node(nid, d, demo=demo or d.get("demo", False))
        with right:
            st.markdown('<div class="section">Eventi</div>', unsafe_allow_html=True)
            lines = [format_log_line(l) for l in list(m.events)] if m.events else ["In attesa..."]
            st.markdown(f'<div class="panel"><div class="panel-bar"><div class="traffic"><span class="t-red"></span><span class="t-yellow"></span><span class="t-green"></span></div><span class="panel-title">events.log</span></div><div class="panel-body">{"<br>".join(lines)}</div></div>', unsafe_allow_html=True)
    with t2:
        render_terminal(m, active, demo=demo)


def render_terminal(m, active: dict, demo: bool = False):
    if not demo:
        st.markdown('<div class="warn-box"><div class="warn-title">Admin required</div><div class="warn-text">Comandi eseguiti con privilegi dell utente Worker. Avvia Worker come amministratore.</div></div>', unsafe_allow_html=True)
        if not st.session_state.get("admin_ok"):
            if st.button("Sblocca terminal (chiave gia verificata)", width="stretch"):
                st.session_state.admin_ok = True
                st.rerun()
            return
    if not active:
        st.warning("Nessun nodo online.")
        return
    opts = {f"{d['host']} ({nid})": nid for nid, d in active.items()}
    target = st.selectbox("Target", ["Tutti"] + list(opts.keys()))
    if demo:
        chips = "".join(f'<span class="cmd-chip">{html.escape(qc)}</span>' for qc in DEMO_QUICK_CMDS)
        st.markdown(f'<div class="section">Comandi rapidi</div><div class="cmd-chips">{chips}</div>', unsafe_allow_html=True)
        cols = st.columns(4)
        for i, qc in enumerate(DEMO_QUICK_CMDS):
            with cols[i % 4]:
                if st.button(qc, key=f"demo_cmd_{qc}", width="stretch"):
                    m.send_command_all(qc) if target == "Tutti" else m.send_command(opts[target], qc)
                    st.rerun()
    cmd = st.text_area("Comando", placeholder="fastfetch / ls -la / cat /etc/os-release / whoami / dir", height=80)
    if st.button("Esegui", width="stretch") and cmd.strip():
        m.send_command_all(cmd.strip()) if target == "Tutti" else m.send_command(opts[target], cmd.strip())
    entries = m.get_terminal_log()
    body = "".join(f'<span class="log-info">[{html.escape(e["ts"])}] {html.escape(e["host"])} $ {html.escape(e["command"])}</span><br><span class="log-ok">{html.escape(e.get("stdout",""))}</span><br><span class="log-err">{html.escape(e.get("stderr",""))}</span><br><br>' for e in entries) if entries else "Nessun output."
    st.markdown(f'<div class="panel"><div class="panel-bar"><div class="traffic"><span class="t-red"></span><span class="t-yellow"></span><span class="t-green"></span></div><span class="panel-title">remote.shell</span></div><div class="panel-body tall">{body}</div></div>', unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def get_master(secret_key: bytes) -> HydraMaster:
    master = HydraMaster(secret_key)
    master.launch()
    atexit.register(master.shutdown)
    return master


@st.cache_resource(show_spinner=False)
def get_demo_master() -> HydraDemoMaster:
    master = HydraDemoMaster()
    master.launch()
    atexit.register(master.shutdown)
    return master


def render_master(m, demo: bool = False):
    urls = get_dashboard_urls()
    render_header(
        "HYDRA OVERLORD",
        f"{VERSION}  /  Dashboard LAN: {urls['network']}",
        "SANDBOX" if demo else "ACTIVE",
        f"Aggiornamento ogni {REFRESH_SEC}s",
        demo=demo,
    )
    if not demo:
        st.markdown(f"""
        <div class="banner"><span class="dot" style="background:{T['accent']}"></span>
        <div class="banner-text">
        <strong>Accesso mobile</strong> — apri da telefono (stessa WiFi): 
        <strong>{html.escape(urls['network'])}</strong><br>
        Puoi ricaricare la pagina liberamente; la sessione backend resta attiva.
        </div></div>
        """, unsafe_allow_html=True)
        if not m._socket_ok:
            st.warning("Backend telemetry gia in esecuzione in background. La dashboard resta utilizzabile.")
    live_master(m, demo=demo)


@st.fragment(run_every=timedelta(seconds=DISCOVERY_SEC))
def auto_discover():
    if st.session_state.get("step") != 1 or not st.session_state.get("auto_discover", True):
        return
    send_udp(f"HYDRA_PROBE|PROBE|{socket.gethostname()}|{get_local_ip()}".encode(), WORKER_UDP_PORT)
    ip = discover_master_udp(1.5)
    if ip:
        st.session_state.target_ip = ip
        st.session_state.step = 2
        st.rerun()
    st.caption(f"Discovery UDP... {datetime.now().strftime('%H:%M:%S')}")


@st.fragment(run_every=timedelta(seconds=REFRESH_SEC))
def live_worker(w: HydraWorker):
    if not w.connected:
        st.warning("Riconnessione...")
        ip = discover_master_udp(1.0) or st.session_state.get("target_ip")
        if ip:
            nw = HydraWorker(ip, st.session_state.cluster_key)
            if nw.engage_link():
                st.session_state.worker = nw
                st.rerun()
        return
    s = w.last_stats
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("CPU", f"{s['cpu']:.1f}%")
        c2.metric("RAM", f"{s['ram']:.1f}%")
        c3.metric("Disco", f"{s['disk']:.1f}%")
        c4.metric("OS", w.meta.get("os", "?"))
        st.plotly_chart(build_chart(list(w.cpu_history)), width="stretch")


def render_worker(key: bytes):
    render_header("HYDRA WORKER", f"{VERSION} / {platform.system()}", "STANDBY", f"Discovery {DISCOVERY_SEC}s")
    if "step" not in st.session_state:
        st.session_state.step = 1
    steps = ["Discovery", "Connect", "Stream"]
    html_steps = '<div class="steps">' + "".join(f'<div class="step {"done" if i < st.session_state.step else ("active" if i == st.session_state.step else "")}"><div class="step-num">{i}</div><div class="step-lbl">{lbl}</div></div>' for i, lbl in enumerate(steps, 1)) + "</div>"
    st.markdown(html_steps, unsafe_allow_html=True)

    if st.session_state.step == 1:
        st.session_state.auto_discover = st.toggle("Auto-discovery UDP", value=st.session_state.get("auto_discover", True))
        if st.session_state.auto_discover:
            auto_discover()
        ip_manual = st.text_input("IP Master (opzionale)", placeholder="192.168.1.100")
        if st.button("Connetti manualmente", width="stretch"):
            ip = ip_manual.strip() or discover_master_udp(3.0)
            if ip:
                st.session_state.target_ip = ip
                st.session_state.step = 2
                st.rerun()
            st.error("Master non trovato via UDP beacon.")

    elif st.session_state.step == 2:
        st.success(f"Master: {st.session_state.target_ip}")
        if st.button("Avvia streaming", width="stretch"):
            w = HydraWorker(st.session_state.target_ip, key)
            if w.engage_link():
                st.session_state.worker = w
                st.session_state.step = 3
                st.rerun()
            st.error(w.error_msg or "Connessione fallita.")
        if st.button("Indietro", width="stretch"):
            st.session_state.step = 1
            st.rerun()

    elif st.session_state.step == 3:
        st.markdown(f'<div class="banner"><span class="dot" style="background:{T["accent"]}"></span><div class="banner-text">Connesso a <strong>{html.escape(st.session_state.target_ip)}</strong></div></div>', unsafe_allow_html=True)
        live_worker(st.session_state.worker)
        if st.button("Disconnetti", width="stretch"):
            st.session_state.worker.disconnect()
            st.session_state.step = 1
            del st.session_state.worker
            st.rerun()


def main():
    apply_styles()
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "master"
    key = ensure_cluster_key(mode)
    demo = is_demo_mode()
    urls = get_dashboard_urls()
    with st.sidebar:
        st.markdown(f"""
        <div style="padding:8px 0 20px">
        <div style="width:40px;height:40px;border-radius:12px;background:linear-gradient(135deg,{T['primary_dim']},{T['violet']});
        display:flex;align-items:center;justify-content:center;font-weight:800;font-size:18px;color:{T['bg']};margin-bottom:12px">H</div>
        <div style="font-size:18px;font-weight:800;letter-spacing:-.02em;color:{T['text']}">{CODENAME}</div>
        <div style="font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:{T['muted']};margin-top:2px">{VERSION}</div>
        </div>
        """, unsafe_allow_html=True)
        st.caption(f"Mode · {mode.upper()}" + (" · DEMO" if demo else ""))
        st.markdown("**Dashboard**")
        st.code(urls["local"], language=None)
        st.code(urls["network"], language=None)
        st.caption("Network URL per telefono (stessa WiFi)")
        st.divider()
        st.markdown("**Avvio rapido**")
        st.code(f"streamlit run main.py -- {mode} demo", language="bash")
        st.code(f"streamlit run main.py -- {mode} CHIAVE", language="bash")
    if mode == "master":
        render_master(get_demo_master() if demo else get_master(key), demo=demo)
    elif mode == "worker":
        if demo:
            st.error("La demo e disponibile solo in modalita master.")
        else:
            render_worker(key)
    else:
        st.error("Usa: master o worker")


if __name__ == "__main__":
    main()
