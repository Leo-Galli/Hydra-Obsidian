import sys, os, time, json, uuid, socket, threading, hashlib, hmac, atexit, subprocess, platform, html
from datetime import datetime, timedelta
import psutil
import streamlit as st
import plotly.graph_objects as go
import zmq
from collections import deque

# --- CORE ---
VERSION = "V3.1.0"
CODENAME = "HYDRA"
SECRET_KEY = b"HYDRA_SINGULARITY_ENCRYPT_2026"
ADMIN_KEY = SECRET_KEY
TCP_PORT = 5555
UDP_PORT = 5556
WORKER_UDP_PORT = 5557
BT_SSID = "HYDRA_COMMAND_CENTER"
NODE_TIMEOUT_SEC = 10
REFRESH_SEC = 2
DISCOVERY_SEC = 3
SCAN_INTERVAL_SEC = 30
PEER_TTL_SEC = 45
CMD_TIMEOUT_SEC = 30
CMD_MAX_LEN = 4096
EXEC_RESULT_TTL = 60

# --- DESIGN TOKENS (8px grid · slate dark · 60-30-10) ---
T = {
    "bg": "#020617",
    "surface": "#0f172a",
    "surface2": "#1e293b",
    "border": "#334155",
    "border_subtle": "rgba(148,163,184,0.12)",
    "primary": "#0ea5e9",
    "primary_dim": "#0284c7",
    "primary_glow": "rgba(14,165,233,0.12)",
    "accent": "#10b981",
    "accent_dim": "#059669",
    "accent_glow": "rgba(16,185,129,0.12)",
    "text": "#f1f5f9",
    "text2": "#94a3b8",
    "muted": "#64748b",
    "warn": "#f59e0b",
    "error": "#ef4444",
    "info": "#38bdf8",
}


def apply_styles():
    st.set_page_config(page_title=f"{CODENAME} {VERSION}", layout="wide", initial_sidebar_state="expanded")
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    :root {{
        --bg:{T['bg']}; --surface:{T['surface']}; --surface2:{T['surface2']};
        --border:{T['border']}; --primary:{T['primary']}; --accent:{T['accent']};
        --text:{T['text']}; --text2:{T['text2']}; --muted:{T['muted']};
    }}
    html,body,[class*="css"] {{ background:var(--bg)!important; color:var(--text); font-family:'Inter',system-ui,sans-serif; font-size:14px; line-height:1.5; }}
    #MainMenu,footer,header {{ visibility:hidden; }}
    .block-container {{ padding:32px 40px 48px; max-width:1440px; }}
    [data-testid="stSidebar"] {{ background:var(--surface); border-right:1px solid var(--border_subtle); }}
    [data-testid="stSidebar"] .block-container {{ padding:24px 16px; }}

    .hero {{ background:linear-gradient(135deg,var(--surface) 0%,var(--surface2) 100%); border:1px solid var(--border_subtle); border-radius:16px; padding:32px; margin-bottom:32px; display:flex; align-items:flex-start; justify-content:space-between; gap:24px; }}
    .hero-eyebrow {{ font-size:12px; font-weight:500; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin-bottom:8px; }}
    .hero-title {{ font-size:30px; font-weight:700; letter-spacing:-.025em; color:var(--text); margin:0; line-height:1.2; }}
    .hero-meta {{ font-family:'JetBrains Mono',monospace; font-size:12px; color:var(--text2); margin:8px 0 0; }}
    .hero-actions {{ display:flex; flex-direction:column; align-items:flex-end; gap:8px; }}
    .hero-status {{ display:flex; align-items:center; gap:8px; background:{T['accent_glow']}; border:1px solid rgba(16,185,129,.3); border-radius:999px; padding:8px 16px; font-size:12px; font-weight:600; color:var(--accent); }}
    .live-pill {{ display:flex; align-items:center; gap:8px; font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); }}
    .status-dot {{ width:8px; height:8px; background:var(--accent); border-radius:50%; flex-shrink:0; }}
    .status-dot.scan {{ background:var(--primary); animation:blink 1.6s ease-in-out infinite; }}
    @keyframes blink {{ 0%,100%{{opacity:1;transform:scale(1)}} 50%{{opacity:.4;transform:scale(.9)}} }}
    @media(prefers-reduced-motion:reduce){{ .status-dot.scan{{animation:none}} }}

    [data-testid="stMetric"] {{ background:var(--surface)!important; border:1px solid var(--border_subtle)!important; border-radius:12px!important; padding:16px!important; transition:border-color .2s ease,box-shadow .2s ease; }}
    [data-testid="stMetric"]:hover {{ border-color:rgba(14,165,233,.35)!important; box-shadow:0 4px 16px rgba(0,0,0,.2); }}
    [data-testid="stMetricLabel"] {{ font-size:11px!important; font-weight:500!important; letter-spacing:.06em!important; text-transform:uppercase!important; color:var(--muted)!important; }}
    [data-testid="stMetricValue"] {{ font-size:24px!important; font-weight:600!important; color:var(--text)!important; }}
    [data-testid="stMetricDelta"] {{ display:none; }}

    [data-testid="stVerticalBlockBorderWrapper"] {{ background:var(--surface)!important; border:1px solid var(--border_subtle)!important; border-radius:12px!important; padding:8px!important; margin-bottom:16px!important; transition:border-color .2s ease; }}
    [data-testid="stVerticalBlockBorderWrapper"]:hover {{ border-color:rgba(14,165,233,.25)!important; }}

    .node-head {{ display:flex; align-items:center; justify-content:space-between; padding:16px 8px; border-bottom:1px solid var(--border_subtle); margin-bottom:8px; gap:16px; }}
    .node-head-left {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
    .badge {{ font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:500; letter-spacing:.06em; text-transform:uppercase; padding:4px 8px; border-radius:6px; border:1px solid; }}
    .badge-online {{ color:var(--accent); background:{T['accent_glow']}; border-color:rgba(16,185,129,.3); }}
    .badge-pending {{ color:var(--primary); background:{T['primary_glow']}; border-color:rgba(14,165,233,.3); }}
    .node-name {{ font-size:16px; font-weight:600; color:var(--text); }}
    .node-meta {{ font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); background:var(--surface2); border:1px solid var(--border_subtle); border-radius:6px; padding:4px 8px; }}
    .stat-label {{ font-size:11px; font-weight:500; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); margin:0 0 4px; }}
    .stat-num {{ font-size:20px; font-weight:600; color:var(--text); margin:0 0 8px; }}
    .stat-num.accent {{ color:var(--accent); }}
    .stat-sub {{ font-family:'JetBrains Mono',monospace; font-size:12px; color:var(--text2); margin:0; }}
    div[data-testid="stProgressBar"]>div {{ background:var(--surface2)!important; border-radius:4px!important; height:6px!important; }}
    div[data-testid="stProgressBar"]>div>div {{ background:linear-gradient(90deg,{T['primary_dim']},{T['primary']})!important; border-radius:4px!important; }}

    .panel {{ border:1px solid var(--border_subtle); border-radius:12px; overflow:hidden; background:var(--surface); }}
    .panel-head {{ display:flex; align-items:center; justify-content:space-between; padding:12px 16px; background:var(--surface2); border-bottom:1px solid var(--border_subtle); }}
    .panel-dots {{ display:flex; gap:6px; }}
    .dot {{ width:10px; height:10px; border-radius:50%; }}
    .dot-r{{background:#ef4444}} .dot-y{{background:#f59e0b}} .dot-g{{background:#10b981}}
    .panel-title {{ font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); margin-left:8px; }}
    .panel-body {{ padding:16px; font-family:'JetBrains Mono',monospace; font-size:12px; line-height:1.7; color:var(--muted); overflow-y:auto; }}
    .panel-body.h420 {{ height:420px; }} .panel-body.h480 {{ height:480px; }}
    .log-ok{{color:{T['accent']}}} .log-warn{{color:{T['warn']}}} .log-err{{color:{T['error']}}} .log-info{{color:{T['info']}}} .log-cmd{{color:#93c5fd}} .log-out{{color:#e2e8f0}}

    .section-head {{ font-size:12px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); margin:0 0 16px; padding-bottom:8px; border-bottom:1px solid var(--border_subtle); }}
    .discovery-bar {{ display:flex; align-items:center; justify-content:space-between; gap:16px; background:var(--surface); border:1px solid var(--border_subtle); border-radius:12px; padding:16px 24px; margin-bottom:24px; flex-wrap:wrap; }}
    .discovery-left {{ display:flex; align-items:center; gap:12px; }}
    .discovery-text {{ font-size:13px; color:var(--text2); }}
    .discovery-text strong {{ color:var(--text); font-weight:600; }}
    .peer-chip {{ display:inline-flex; align-items:center; gap:6px; background:var(--surface2); border:1px solid var(--border_subtle); border-radius:8px; padding:6px 12px; margin:4px; font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--text2); }}

    .empty-box {{ text-align:center; padding:48px 32px; border:1px dashed var(--border); border-radius:12px; color:var(--muted); background:var(--surface); }}
    .empty-box strong {{ color:var(--text); display:block; margin-bottom:8px; font-size:15px; font-weight:600; }}
    .empty-box code {{ font-family:'JetBrains Mono',monospace; font-size:12px; color:var(--primary); background:{T['primary_glow']}; padding:4px 8px; border-radius:6px; }}

    .admin-warn {{ background:rgba(239,68,68,.06); border:1px solid rgba(239,68,68,.25); border-radius:12px; padding:16px 24px; margin-bottom:24px; }}
    .admin-warn-title {{ font-size:12px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:{T['error']}; margin-bottom:8px; }}
    .admin-warn-text {{ font-size:13px; color:var(--text2); line-height:1.6; }}

    .steps {{ display:flex; margin-bottom:32px; background:var(--surface); border:1px solid var(--border_subtle); border-radius:12px; overflow:hidden; }}
    .step {{ flex:1; text-align:center; padding:16px; border-right:1px solid var(--border_subtle); }}
    .step:last-child {{ border-right:none; }}
    .step.active {{ background:{T['primary_glow']}; }}
    .step.done {{ background:rgba(16,185,129,.05); }}
    .step-num {{ width:32px; height:32px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; font-size:13px; font-weight:600; border:2px solid var(--border); color:var(--muted); margin-bottom:8px; }}
    .step.active .step-num {{ border-color:var(--primary); color:var(--primary); background:{T['primary_glow']}; }}
    .step.done .step-num {{ border-color:var(--accent); background:var(--accent); color:#020617; }}
    .step-lbl {{ font-size:11px; font-weight:500; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); }}
    .step.active .step-lbl {{ color:var(--primary); }}
    .link-strip {{ display:flex; align-items:center; gap:12px; background:{T['accent_glow']}; border:1px solid rgba(16,185,129,.25); border-radius:12px; padding:16px 24px; margin-bottom:24px; font-family:'JetBrains Mono',monospace; font-size:13px; color:var(--accent); }}

    .stButton>button {{ background:var(--surface2)!important; border:1px solid var(--border)!important; color:var(--text)!important; font-weight:500!important; border-radius:8px!important; min-height:44px!important; font-size:14px!important; transition:all .2s ease!important; }}
    .stButton>button:hover {{ border-color:var(--primary)!important; color:var(--primary)!important; background:{T['primary_glow']}!important; }}
    .stButton>button:focus-visible {{ outline:2px solid var(--primary)!important; outline-offset:2px!important; }}
    [data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea,[data-testid="stSelectbox"] div[data-baseweb="select"] {{ background:var(--surface2)!important; border:1px solid var(--border)!important; border-radius:8px!important; color:var(--text)!important; min-height:44px; }}
    [data-testid="stTabs"] button {{ font-size:13px; font-weight:500; min-height:44px; }}
    [data-testid="stTabs"] button[aria-selected="true"] {{ color:var(--primary)!important; border-bottom-color:var(--primary)!important; }}

    .sb-brand {{ font-size:18px; font-weight:700; color:var(--text); margin-bottom:4px; }}
    .sb-ver {{ font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--primary); }}
    .sb-block {{ background:var(--surface2); border:1px solid var(--border_subtle); border-radius:8px; padding:16px; margin-bottom:16px; }}
    .sb-block-title {{ font-size:10px; font-weight:600; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin-bottom:8px; }}
    </style>
    """, unsafe_allow_html=True)


def make_signature(payload: bytes) -> bytes:
    return hmac.new(SECRET_KEY, payload, hashlib.sha256).digest()


def verify_signature(payload: bytes, sig: bytes) -> bool:
    return hmac.compare_digest(make_signature(payload), sig)


def get_local_ip() -> str:
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"


def get_subnet_base() -> str:
    return ".".join(get_local_ip().split(".")[:-1])


def get_system_meta() -> dict:
    return {
        "os": platform.system(),
        "release": platform.release(),
        "arch": platform.machine(),
        "shell": os.environ.get("COMSPEC", "cmd.exe") if sys.platform == "win32" else os.environ.get("SHELL", "/bin/sh"),
    }


def run_shell_command(command: str) -> dict:
    shell_exe = os.environ.get("COMSPEC", "cmd.exe") if sys.platform == "win32" else "/bin/sh"
    try:
        proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=CMD_TIMEOUT_SEC, executable=shell_exe, cwd=os.path.expanduser("~"))
        return {"stdout": proc.stdout or "", "stderr": proc.stderr or "", "exit_code": proc.returncode, "os": platform.system(), "shell": shell_exe, "error": None}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Timeout ({CMD_TIMEOUT_SEC}s)", "exit_code": -1, "os": platform.system(), "shell": shell_exe, "error": "timeout"}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": -1, "os": platform.system(), "shell": shell_exe, "error": str(e)}


def send_udp_beacon(msg: bytes, port: int):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for dest in [("<broadcast>", port), ("127.0.0.1", port)]:
            try:
                s.sendto(msg, dest)
            except Exception:
                pass


def discover_master(timeout: float = 2.0):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("", UDP_PORT))
            s.settimeout(timeout)
            data, _ = s.recvfrom(1024)
            parts = data.decode().split("|")
            if parts[0] == "HYDRA_BEACON":
                return parts[2]
    except Exception:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            if s.connect_ex(("127.0.0.1", TCP_PORT)) == 0:
                return "127.0.0.1"
    except Exception:
        pass
    try:
        base = get_subnet_base()
        for i in range(1, 255):
            ip = f"{base}.{i}"
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.015)
                if s.connect_ex((ip, TCP_PORT)) == 0:
                    return ip
    except Exception:
        pass
    return None


def build_chart(values, height=160, title="CPU — 60s"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(range(len(values))), y=list(values), fill="tozeroy", fillcolor="rgba(14,165,233,0.1)", line=dict(color=T["primary"], width=2), mode="lines"))
    fig.update_layout(
        height=height,
        title=dict(text=title, font=dict(size=11, color=T["muted"]), x=0),
        margin=dict(l=32, r=8, t=28, b=24),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=T["surface2"],
        font=dict(family="JetBrains Mono", color=T["muted"], size=10),
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(gridcolor="rgba(148,163,184,0.08)", range=[0, 100], ticksuffix="%", nticks=4),
        showlegend=False,
    )
    return fig


def format_log_line(line: str) -> str:
    esc = html.escape(line)
    if any(k in line for k in ("ERRORE", "INVALIDA", "negato", "RIFIUTATO")):
        return f'<span class="log-err">{esc}</span>'
    if "HANDSHAKE" in line or "EXEC OK" in line:
        return f'<span class="log-ok">{esc}</span>'
    if "DISCOVERY" in line or "SCAN" in line or "PEER" in line:
        return f'<span class="log-info">{esc}</span>'
    if "EXEC" in line or "WARN" in line:
        return f'<span class="log-warn">{esc}</span>'
    return esc


def format_terminal_entry(entry: dict) -> str:
    ts, host, cmd = html.escape(entry.get("ts", "")), html.escape(entry.get("host", "?")), html.escape(entry.get("command", ""))
    stdout = html.escape(entry.get("stdout", "") or "").replace("\n", "<br>")
    stderr = html.escape(entry.get("stderr", "") or "").replace("\n", "<br>")
    block = f'<span class="log-cmd">[{ts}] {host} $ {cmd}</span><br><span class="log-muted">exit {entry.get("exit_code", "?")}</span><br>'
    if stdout:
        block += f'<span class="log-out">{stdout}</span><br>'
    if stderr:
        block += f'<span class="log-err">{stderr}</span><br>'
    return block + "<br>"


def render_panel(title: str, body_html: str, tall: bool = False):
    h = "h480" if tall else "h420"
    st.markdown(f"""
    <div class="panel"><div class="panel-head">
    <div style="display:flex;align-items:center"><div class="panel-dots"><span class="dot dot-r"></span><span class="dot dot-y"></span><span class="dot dot-g"></span></div>
    <span class="panel-title">{html.escape(title)}</span></div></div>
    <div class="panel-body {h}">{body_html}</div></div>
    """, unsafe_allow_html=True)


def render_hero(title: str, subtitle: str, status: str = "", live_text: str = ""):
    live = f'<div class="live-pill"><span class="status-dot scan"></span>{html.escape(live_text)}</div>' if live_text else ""
    status_html = f'<div class="hero-status"><span class="status-dot"></span>{html.escape(status)}</div>' if status else ""
    st.markdown(f"""
    <div class="hero"><div>
    <div class="hero-eyebrow">Infrastructure Control Plane</div>
    <div class="hero-title">{html.escape(title)}</div>
    <div class="hero-meta">{html.escape(subtitle)}</div></div>
    <div class="hero-actions">{status_html}{live}</div></div>
    """, unsafe_allow_html=True)


def render_sidebar(mode: str, extra: str = ""):
    with st.sidebar:
        st.markdown(f"<div class='sb-brand'>{CODENAME}</div><div class='sb-ver'>{VERSION} / {mode.upper()}</div>", unsafe_allow_html=True)
        st.divider()
        st.markdown(f"""
        <div class="sb-block"><div class="sb-block-title">Network</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:{T['text2']}">TCP {TCP_PORT}<br>UDP {UDP_PORT} / {WORKER_UDP_PORT}</div></div>
        <div class="sb-block"><div class="sb-block-title">Auto Discovery</div>
        <div style="font-size:13px;color:{T['text2']}">Refresh ogni {REFRESH_SEC}s<br>Scan rete ogni {SCAN_INTERVAL_SEC}s</div></div>
        {extra}
        """, unsafe_allow_html=True)
        st.markdown("**Launch**")
        st.code("streamlit run main.py -- master", language="bash")
        st.code("streamlit run main.py -- worker", language="bash")


def render_node_card(nid: str, host: str, ip: str, stats: dict, history: list, meta: dict):
    cpu, ram, disk = float(stats.get("cpu", 0)), float(stats.get("ram", 0)), float(stats.get("disk", 0))
    os_label = f"{meta.get('os', '?')} {meta.get('release', '')}".strip()
    with st.container(border=True):
        st.markdown(f"""
        <div class="node-head"><div class="node-head-left">
        <span class="badge badge-online">Online</span>
        <span class="node-name">{html.escape(host)}</span>
        <span class="node-meta">{html.escape(os_label)}</span></div>
        <span class="node-meta">{html.escape(nid)}</span></div>
        """, unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<p class="stat-label">CPU</p><p class="stat-num accent">{cpu:.1f}%</p>', unsafe_allow_html=True)
            st.progress(min(cpu / 100, 1.0))
        with c2:
            st.markdown(f'<p class="stat-label">RAM</p><p class="stat-num">{ram:.1f}%</p>', unsafe_allow_html=True)
            st.progress(min(ram / 100, 1.0))
        with c3:
            st.markdown(f'<p class="stat-label">Disco</p><p class="stat-num">{disk:.1f}%</p>', unsafe_allow_html=True)
            st.progress(min(disk / 100, 1.0))
        with c4:
            st.markdown(f'<p class="stat-label">Rete</p><p class="stat-sub">{html.escape(ip)}</p><p class="stat-label" style="margin-top:8px">Threads</p><p class="stat-num" style="font-size:18px">{stats.get("threads", 0)}</p>', unsafe_allow_html=True)
        if history:
            st.plotly_chart(build_chart(history, title=f"{host} — CPU"), width="stretch", key=f"chart_{nid}")


class HydraMaster:
    def __init__(self):
        self.nodes = {}
        self.peers = {}
        self.events = deque(maxlen=300)
        self.terminal_log = deque(maxlen=200)
        self.pending_exec = {}
        self.lock = threading.Lock()
        self.active = True
        self._socket_ok = False
        self.started_at = datetime.now()
        self.scan_state = {"scanning": False, "last_scan": None, "hosts_probed": 0}
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(zmq.ROUTER)
        self.socket.setsockopt(zmq.LINGER, 0)
        try:
            self.socket.bind(f"tcp://0.0.0.0:{TCP_PORT}")
            self._socket_ok = True
            self.events.appendleft(f"[{self._ts()}] Master attivo su tcp://0.0.0.0:{TCP_PORT}")
        except Exception as e:
            self.events.appendleft(f"[{self._ts()}] ERRORE BIND porta {TCP_PORT}: {e}")

    def _ts(self):
        return datetime.now().strftime("%H:%M:%S")

    def launch(self):
        if not self._socket_ok:
            return
        threading.Thread(target=self._discovery_beacon, daemon=True).start()
        threading.Thread(target=self._data_collector, daemon=True).start()
        threading.Thread(target=self._peer_listener, daemon=True).start()
        threading.Thread(target=self._subnet_scanner, daemon=True).start()
        self.events.appendleft(f"[{self._ts()}] Auto-discovery attivo (beacon + scan + peer listener)")

    def _discovery_beacon(self):
        while self.active:
            msg = f"HYDRA_BEACON|{BT_SSID}|{get_local_ip()}".encode()
            send_udp_beacon(msg, UDP_PORT)
            time.sleep(2)

    def _peer_listener(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("", WORKER_UDP_PORT))
            except Exception as e:
                self.events.appendleft(f"[{self._ts()}] PEER LISTENER ERR: {e}")
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
                    peer_id = parts[1] if len(parts) >= 2 else "?"
                    with self.lock:
                        is_new = peer_ip not in self.peers
                        self.peers[peer_ip] = {"host": peer_host, "id": peer_id, "ip": peer_ip, "last": time.time(), "kind": parts[0]}
                        if is_new:
                            self.events.appendleft(f"[{self._ts()}] PEER RILEVATO: {peer_host} @ {peer_ip}")
                except socket.timeout:
                    pass
                except Exception:
                    pass
                self._expire_peers()

    def _subnet_scanner(self):
        while self.active:
            self.scan_state["scanning"] = True
            probed = 0
            base = get_subnet_base()
            for i in range(1, 255):
                if not self.active:
                    break
                ip = f"{base}.{i}"
                probed += 1
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                        sock.settimeout(0.02)
                        if sock.connect_ex((ip, TCP_PORT)) == 0 and ip != get_local_ip():
                            with self.lock:
                                if ip not in self.peers:
                                    self.peers[ip] = {"host": "?", "id": "?", "ip": ip, "last": time.time(), "kind": "SCAN"}
                                    self.events.appendleft(f"[{self._ts()}] SCAN: host attivo {ip}:{TCP_PORT}")
                except Exception:
                    pass
            self.scan_state["scanning"] = False
            self.scan_state["last_scan"] = time.time()
            self.scan_state["hosts_probed"] = probed
            self._expire_peers()
            time.sleep(SCAN_INTERVAL_SEC)

    def _expire_peers(self):
        now = time.time()
        with self.lock:
            expired = [ip for ip, p in self.peers.items() if now - p["last"] > PEER_TTL_SEC]
            for ip in expired:
                del self.peers[ip]

    def _data_collector(self):
        while self.active:
            try:
                if self.socket.poll(500, zmq.POLLIN):
                    parts = self.socket.recv_multipart(flags=zmq.NOBLOCK)
                    if len(parts) < 4:
                        continue
                    identity, payload, sig = parts[0], parts[2], parts[3]
                    if not verify_signature(payload, sig):
                        self.events.appendleft(f"[{self._ts()}] FIRMA INVALIDA")
                        continue
                    data = json.loads(payload.decode("utf-8"))
                    if data.get("t") == "tel":
                        self._sync_node(identity, data)
                    elif data.get("t") == "exec_result":
                        self._store_exec_result(data)
            except zmq.Again:
                pass
            except Exception as e:
                self.events.appendleft(f"[{self._ts()}] Errore collector: {e}")
            self._expire_pending()

    def _sync_node(self, identity, data):
        nid = data.get("id", "UNKNOWN")
        ip = data.get("ip", "?")
        with self.lock:
            is_new = nid not in self.nodes
            self.nodes[nid] = {
                "host": data.get("host", "?"), "ip": ip, "stats": data.get("s", {}),
                "history": data.get("h", []), "meta": data.get("meta", {}),
                "identity": identity, "last": time.time(),
            }
            self.peers.pop(ip, None)
            if is_new:
                os_info = data.get("meta", {}).get("os", "?")
                self.events.appendleft(f"[{self._ts()}] HANDSHAKE OK: {data.get('host', '?')} ({nid}) @ {ip} [{os_info}]")

    def _store_exec_result(self, data):
        entry = {"cmd_id": data.get("cmd_id"), "node_id": data.get("id"), "host": data.get("host", "?"), "command": data.get("command", ""), "stdout": data.get("stdout", ""), "stderr": data.get("stderr", ""), "exit_code": data.get("exit_code", -1), "ts": self._ts()}
        with self.lock:
            self.terminal_log.appendleft(entry)
            self.pending_exec.pop(data.get("cmd_id", ""), None)
        self.events.appendleft(f"[{self._ts()}] EXEC OK: {entry['host']} exit={entry['exit_code']}")

    def _expire_pending(self):
        now = time.time()
        with self.lock:
            for cmd_id in [k for k, v in self.pending_exec.items() if now - v["sent_at"] > EXEC_RESULT_TTL]:
                p = self.pending_exec.pop(cmd_id)
                self.events.appendleft(f"[{self._ts()}] EXEC TIMEOUT: {p['host']}")

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
        raw = json.dumps({"t": "exec", "cmd_id": cmd_id, "command": command}).encode()
        try:
            self.socket.send_multipart([identity, b"", raw, make_signature(raw)])
        except Exception as e:
            self.events.appendleft(f"[{self._ts()}] EXEC SEND ERR: {e}")
            return None
        with self.lock:
            self.pending_exec[cmd_id] = {"host": host, "command": command, "sent_at": time.time()}
        return cmd_id

    def send_command_all(self, command: str) -> list:
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

    def uptime(self) -> str:
        s = int((datetime.now() - self.started_at).total_seconds())
        h, r = divmod(s, 3600)
        m, sec = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def shutdown(self):
        self.active = False
        try:
            self.socket.close()
        except Exception:
            pass
        try:
            self.ctx.term()
        except Exception:
            pass


class HydraWorker:
    def __init__(self, target_ip):
        self.id = f"HYDRA-NODE-{uuid.uuid4().hex[:6].upper()}"
        self.target = target_ip
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.DEALER)
        self.sock.setsockopt(zmq.LINGER, 0)
        self.sock.setsockopt_string(zmq.IDENTITY, self.id)
        self.sock_lock = threading.Lock()
        self.cpu_history = deque([0] * 60, maxlen=60)
        self.connected = False
        self.error_msg = ""
        self.last_stats = {"cpu": 0, "ram": 0, "disk": 0, "threads": 0}
        self.meta = get_system_meta()

    def engage_link(self) -> bool:
        try:
            self.sock.connect(f"tcp://{self.target}:{TCP_PORT}")
            self.connected = True
            threading.Thread(target=self._worker_loop, daemon=True).start()
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

    def announce(self, kind: str = "HYDRA_PROBE"):
        host = socket.gethostname()
        msg = f"{kind}|{self.id if kind == 'HYDRA_WORKER' else 'PROBE'}|{host}|{get_local_ip()}".encode()
        send_udp_beacon(msg, WORKER_UDP_PORT)

    def _send_signed(self, payload_obj: dict):
        raw = json.dumps(payload_obj).encode()
        with self.sock_lock:
            self.sock.send_multipart([b"", raw, make_signature(raw)])

    def _handle_exec(self, data: dict):
        command = str(data.get("command", "")).strip()[:CMD_MAX_LEN]
        cmd_id = data.get("cmd_id", "")
        if not command or not cmd_id:
            return
        result = run_shell_command(command)
        self._send_signed({"t": "exec_result", "cmd_id": cmd_id, "id": self.id, "host": socket.gethostname(), "command": command, "stdout": result["stdout"][:65536], "stderr": result["stderr"][:65536], "exit_code": result["exit_code"], "os": result["os"]})

    def _worker_loop(self):
        psutil.cpu_percent(interval=None)
        disk_path = "C:\\" if sys.platform == "win32" else "/"
        last_tel = last_ann = 0.0
        while self.connected:
            try:
                with self.sock_lock:
                    polled = self.sock.poll(100, zmq.POLLIN)
                if polled:
                    with self.sock_lock:
                        parts = self.sock.recv_multipart(flags=zmq.NOBLOCK)
                    if len(parts) >= 3:
                        payload, sig = parts[-2], parts[-1]
                        if verify_signature(payload, sig):
                            msg = json.loads(payload.decode())
                            if msg.get("t") == "exec":
                                self._handle_exec(msg)
                now = time.time()
                if now - last_tel >= 1.0:
                    stats = {"cpu": psutil.cpu_percent(interval=None), "ram": psutil.virtual_memory().percent, "disk": psutil.disk_usage(disk_path).percent, "threads": threading.active_count()}
                    self.last_stats = stats
                    self.cpu_history.append(stats["cpu"])
                    self._send_signed({"t": "tel", "id": self.id, "host": socket.gethostname(), "ip": get_local_ip(), "s": stats, "h": list(self.cpu_history), "meta": self.meta})
                    last_tel = now
                if now - last_ann >= 5.0:
                    self.announce("HYDRA_WORKER")
                    last_ann = now
            except zmq.ZMQError:
                self.connected = False
                break
            except Exception:
                pass


@st.fragment(run_every=timedelta(seconds=REFRESH_SEC))
def live_master_dashboard(m: HydraMaster):
    active = m.get_active_nodes()
    pending = m.get_pending_peers()
    avg_cpu = round(sum(n["stats"].get("cpu", 0) for n in active.values()) / max(len(active), 1), 1)
    avg_ram = round(sum(n["stats"].get("ram", 0) for n in active.values()) / max(len(active), 1), 1)
    scan_txt = "Scansione in corso..." if m.scan_state["scanning"] else f"Ultimo scan: {datetime.fromtimestamp(m.scan_state['last_scan']).strftime('%H:%M:%S') if m.scan_state['last_scan'] else '—'}"

    r1 = st.columns(5)
    r1[0].metric("Nodi online", len(active))
    r1[1].metric("Peer rilevati", len(pending))
    r1[2].metric("CPU media", f"{avg_cpu}%")
    r1[3].metric("RAM media", f"{avg_ram}%")
    r1[4].metric("Uptime", m.uptime())

    st.markdown(f"""
    <div class="discovery-bar"><div class="discovery-left">
    <span class="status-dot scan"></span>
    <div class="discovery-text"><strong>Auto-discovery attivo</strong> — refresh ogni {REFRESH_SEC}s, scan subnet ogni {SCAN_INTERVAL_SEC}s<br>{html.escape(scan_txt)}</div>
    </div>
    <div class="discovery-text">Host analizzati: <strong>{m.scan_state.get('hosts_probed', 0)}</strong></div></div>
    """, unsafe_allow_html=True)

    if pending:
        chips = "".join(f'<span class="peer-chip"><span class="status-dot scan"></span>{html.escape(p["host"])} @ {html.escape(ip)}</span>' for ip, p in pending.items())
        st.markdown(f'<div style="margin-bottom:24px"><div class="section-head">Peer in rete (in attesa di connessione)</div>{chips}</div>', unsafe_allow_html=True)

    tab_mon, tab_term = st.tabs(["Monitoraggio", "Terminal remoto"])
    with tab_mon:
        render_monitor_tab(m, active)
    with tab_term:
        render_terminal_tab(m, active)


def render_monitor_tab(m: HydraMaster, active: dict):
    col_nodes, col_log = st.columns([1.6, 1])
    with col_nodes:
        st.markdown("<div class='section-head'>Topologia nodi</div>", unsafe_allow_html=True)
        if not active:
            st.markdown("""<div class="empty-box"><strong>Nessun nodo connesso</strong>
            Discovery automatico in corso. Avvia worker sulle macchine target:<br><br>
            <code>streamlit run main.py -- worker</code></div>""", unsafe_allow_html=True)
        for nid, d in active.items():
            render_node_card(nid, d["host"], d["ip"], d["stats"], d["history"], d.get("meta", {}))
    with col_log:
        st.markdown("<div class='section-head'>Log eventi</div>", unsafe_allow_html=True)
        lines = [format_log_line(l) for l in list(m.events)] if m.events else ["In attesa..."]
        render_panel("hydra-events.log", "<br>".join(lines))


def render_terminal_tab(m: HydraMaster, active: dict):
    st.markdown("""<div class="admin-warn"><div class="admin-warn-title">Privilegi amministratore</div>
    <div class="admin-warn-text">I comandi vengono eseguiti con i privilegi dell'utente che avvia il Worker.
    Avvia il Worker come admin/root. Ogni comando e firmato HMAC-SHA256.</div></div>""", unsafe_allow_html=True)
    if "admin_unlocked" not in st.session_state:
        st.session_state.admin_unlocked = False
    if not st.session_state.admin_unlocked:
        admin_key = st.text_input("Chiave admin", type="password")
        confirm = st.checkbox("Confermo esecuzione comandi con privilegi amministratore")
        if st.button("Sblocca terminal", width="stretch"):
            if admin_key.encode() == ADMIN_KEY and confirm:
                st.session_state.admin_unlocked = True
                st.rerun()
            else:
                st.error("Chiave o conferma mancante.")
        return
    if not active:
        st.info("Nessun nodo online.")
        return
    node_options = {f"{d['host']} ({nid})": nid for nid, d in active.items()}
    target = st.selectbox("Target", ["Tutti i nodi"] + list(node_options.keys()))
    command = st.text_area("Comando shell", placeholder="Windows: dir\nLinux: ls -la && uname -a", height=88)
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        run = st.button("Esegui", width="stretch")
    with c2:
        run_all = st.button("Esegui su tutti", width="stretch")
    with c3:
        if st.button("Lock", width="stretch"):
            st.session_state.admin_unlocked = False
            st.rerun()
    if (run or run_all) and command.strip():
        if run_all or target == "Tutti i nodi":
            m.send_command_all(command.strip())
        else:
            m.send_command(node_options[target], command.strip())
    entries = m.get_terminal_log()
    body = "".join(format_terminal_entry(e) for e in entries) if entries else '<span class="log-muted">Nessun comando eseguito.</span>'
    render_panel("hydra-remote.shell", body, tall=True)


def render_master(m: HydraMaster):
    render_hero("HYDRA OVERLORD", f"{VERSION}  /  TCP {TCP_PORT}  /  UDP {UDP_PORT}", "ACTIVE", f"Aggiornamento live ogni {REFRESH_SEC}s")
    if not m._socket_ok:
        st.error(f"Porta {TCP_PORT} non disponibile.")
        return
    live_master_dashboard(m)


@st.fragment(run_every=timedelta(seconds=DISCOVERY_SEC))
def auto_discover_worker():
    if st.session_state.get("step") != 1:
        return
    if not st.session_state.get("auto_discover", True):
        return
    HydraWorker("0.0.0.0").announce("HYDRA_PROBE")
    ip = discover_master(timeout=1.5)
    if ip:
        st.session_state.target_ip = ip
        st.session_state.step = 2
        st.rerun()
    st.caption(f"Ricerca master automatica... ({datetime.now().strftime('%H:%M:%S')})")


@st.fragment(run_every=timedelta(seconds=REFRESH_SEC))
def live_worker_dashboard(w: HydraWorker):
    if not w.connected:
        st.warning("Connessione persa — tentativo riconnessione...")
        ip = discover_master(timeout=1.0) or st.session_state.get("target_ip")
        if ip:
            nw = HydraWorker(ip)
            if nw.engage_link():
                st.session_state.worker = nw
                st.session_state.target_ip = ip
                st.rerun()
        return
    s = w.last_stats
    with st.container(border=True):
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("CPU", f"{s['cpu']:.1f}%")
        m2.metric("RAM", f"{s['ram']:.1f}%")
        m3.metric("Disco", f"{s['disk']:.1f}%")
        m4.metric("OS", w.meta.get("os", "?"))
        st.plotly_chart(build_chart(list(w.cpu_history), height=300), width="stretch")


def render_stepper(current: int):
    steps = ["Scoperta", "Auth", "Streaming"]
    out = '<div class="steps">'
    for i, lbl in enumerate(steps, 1):
        cls = "done" if i < current else ("active" if i == current else "")
        out += f'<div class="step {cls}"><div class="step-num">{i}</div><div class="step-lbl">{lbl}</div></div>'
    return out + "</div>"


def render_worker():
    render_hero("HYDRA WORKER", f"Agent  /  {VERSION}  /  {platform.system()}", "STANDBY", f"Discovery ogni {DISCOVERY_SEC}s")
    if "step" not in st.session_state:
        st.session_state.step = 1
    if "auto_discover" not in st.session_state:
        st.session_state.auto_discover = True
    st.markdown(render_stepper(st.session_state.step), unsafe_allow_html=True)

    if st.session_state.step == 1:
        st.markdown("<div class='section-head'>Discovery master</div>", unsafe_allow_html=True)
        st.session_state.auto_discover = st.toggle("Discovery automatica continua", value=st.session_state.auto_discover)
        if st.session_state.auto_discover:
            auto_discover_worker()
        method = st.radio("Metodo manuale", ["Beacon + localhost", "IP manuale"], horizontal=True)
        static_ip = st.text_input("IP Master", placeholder="192.168.1.100") if method == "IP manuale" else ""
        if st.button("Cerca ora", width="stretch"):
            ip = static_ip.strip() if method == "IP manuale" else discover_master(timeout=3.0)
            if ip:
                st.session_state.target_ip = ip
                st.session_state.step = 2
                st.rerun()
            st.error("Master non trovato.")

    elif st.session_state.step == 2:
        st.info(f"Master: {st.session_state.target_ip}")
        key_in = st.text_input("Chiave cluster", type="password")
        c1, c2 = st.columns([3, 1])
        with c1:
            if st.button("Connetti", width="stretch"):
                if key_in.encode() == SECRET_KEY:
                    w = HydraWorker(st.session_state.target_ip)
                    if w.engage_link():
                        st.session_state.worker = w
                        st.session_state.step = 3
                        st.rerun()
                    st.error(f"Connessione fallita: {w.error_msg}")
                else:
                    st.error("Chiave non valida.")
        with c2:
            if st.button("Indietro", width="stretch"):
                st.session_state.step = 1
                st.rerun()

    elif st.session_state.step == 3:
        w: HydraWorker = st.session_state.worker
        st.markdown(f'<div class="link-strip"><span class="status-dot"></span>SECURE LINK &rarr; {html.escape(st.session_state.target_ip)}</div>', unsafe_allow_html=True)
        live_worker_dashboard(w)
        st.caption("Auto-discovery e riconnessione attivi.")
        if st.button("Disconnetti", width="stretch"):
            w.disconnect()
            st.session_state.step = 1
            del st.session_state.worker
            st.rerun()


def main():
    apply_styles()
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "master"
    render_sidebar(mode)
    if mode == "master":
        if "master" not in st.session_state:
            master = HydraMaster()
            master.launch()
            st.session_state.master = master
            atexit.register(master.shutdown)
        render_master(st.session_state.master)
    elif mode == "worker":
        render_worker()
    else:
        st.error("Usa: master o worker.")


if __name__ == "__main__":
    main()
