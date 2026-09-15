import sys, os, time, json, uuid, socket, threading, hashlib, hmac, atexit, subprocess, platform, html, math, random
from datetime import datetime, timedelta
import psutil
import streamlit as st
import plotly.graph_objects as go
import zmq
from collections import deque

VERSION = "V3.4.1"
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
    "bg": "#090909",
    "surface": "#111111",
    "surface2": "#161616",
    "border": "#222222",
    "border_hi": "#2e2e2e",
    "text": "#ededed",
    "text2": "#a3a3a3",
    "muted": "#737373",
    "ok": "#22c55e",
    "warn": "#d97706",
    "error": "#dc2626",
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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
    :root {{
        --bg:{T['bg']}; --surface:{T['surface']}; --surface2:{T['surface2']};
        --border:{T['border']}; --border-hi:{T['border_hi']};
        --text:{T['text']}; --text2:{T['text2']}; --muted:{T['muted']};
    }}
    html,body,[class*="css"] {{ background:var(--bg)!important; color:var(--text); font-family:'Inter',system-ui,sans-serif; }}
    #MainMenu,footer,header {{ visibility:hidden; }}
    .block-container {{ padding:24px 32px 48px; max-width:1400px; }}
    [data-testid="stSidebar"] {{ background:var(--surface)!important; border-right:1px solid var(--border)!important; }}
    [data-testid="stSidebar"] .stMarkdown p, [data-testid="stSidebar"] label {{ color:var(--text2)!important; font-size:13px; }}
    [data-testid="stSidebar"] code {{ background:var(--surface2)!important; color:var(--text)!important; border:1px solid var(--border); font-size:12px; }}

    .topbar {{ display:flex; justify-content:space-between; align-items:flex-end; gap:24px; flex-wrap:wrap;
        padding-bottom:24px; margin-bottom:24px; border-bottom:1px solid var(--border); }}
    .kicker {{ font-size:11px; font-weight:500; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin:0 0 6px; }}
    .topbar-title {{ font-size:24px; font-weight:600; letter-spacing:-.02em; margin:0 0 4px; color:var(--text); }}
    .topbar-sub {{ font-size:13px; color:var(--text2); margin:0; line-height:1.5; }}
    .badges {{ display:flex; gap:8px; flex-wrap:wrap; align-items:center; }}
    .badge {{ display:inline-flex; align-items:center; gap:6px; padding:5px 10px; border:1px solid var(--border);
        border-radius:6px; font-size:11px; font-weight:500; color:var(--text2); background:var(--surface); }}
    .badge .dot {{ width:6px; height:6px; border-radius:50%; background:var(--muted); }}
    .badge-ok .dot {{ background:{T['ok']}; }}
    .badge-live .dot {{ background:var(--text2); }}

    .stats {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:24px; }}
    @media(max-width:1000px){{ .stats{{grid-template-columns:repeat(3,1fr);}} }}
    @media(max-width:640px){{ .stats{{grid-template-columns:repeat(2,1fr);}} }}
    .stat {{ background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:16px; }}
    .stat-lbl {{ font-size:11px; font-weight:500; color:var(--muted); margin-bottom:6px; }}
    .stat-val {{ font-size:22px; font-weight:600; letter-spacing:-.02em; color:var(--text); line-height:1; font-variant-numeric:tabular-nums; }}

    [data-testid="stVerticalBlockBorderWrapper"] {{
        background:var(--surface)!important; border:1px solid var(--border)!important;
        border-radius:8px!important; padding:16px!important; margin-bottom:12px!important;
        box-shadow:none!important;
    }}
    [data-testid="stMetric"] {{
        background:var(--surface)!important; border:1px solid var(--border)!important;
        border-radius:8px!important; padding:16px!important; box-shadow:none!important;
    }}
    [data-testid="stMetricLabel"] {{ font-size:11px!important; color:var(--muted)!important; font-weight:500!important; }}
    [data-testid="stMetricValue"] {{ font-size:22px!important; font-weight:600!important; color:var(--text)!important; }}
    [data-testid="stMetricDelta"] {{ display:none; }}

    .section {{ font-size:11px; font-weight:600; letter-spacing:.06em; text-transform:uppercase;
        color:var(--muted); margin:0 0 12px; padding-bottom:8px; border-bottom:1px solid var(--border); }}
    .node-head {{ display:flex; justify-content:space-between; align-items:center; gap:12px;
        margin-bottom:12px; padding-bottom:12px; border-bottom:1px solid var(--border); }}
    .node-name {{ font-size:15px; font-weight:600; color:var(--text); }}
    .node-id {{ font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--muted); }}
    .node-tags {{ display:flex; gap:6px; flex-wrap:wrap; margin-bottom:12px; }}
    .tag {{ font-size:11px; font-weight:500; padding:3px 8px; border-radius:4px; border:1px solid var(--border); color:var(--text2); }}
    .tag-ok {{ color:var(--text2); }}
    .tag-ok::before {{ content:''; display:inline-block; width:5px; height:5px; border-radius:50%; background:{T['ok']}; margin-right:6px; vertical-align:middle; }}
    .metrics {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:12px; }}
    .mrow-head {{ display:flex; justify-content:space-between; font-size:11px; color:var(--muted); margin-bottom:6px; }}
    .mrow-head span:last-child {{ color:var(--text); font-weight:500; font-variant-numeric:tabular-nums; }}
    .mtrack {{ height:4px; background:var(--surface2); border-radius:2px; overflow:hidden; }}
    .mfill {{ height:100%; background:var(--border-hi); border-radius:2px; }}
    .mfill-warn {{ background:{T['warn']}; }}
    .node-foot {{ display:flex; gap:20px; font-size:12px; color:var(--text2); margin-bottom:4px; }}
    .node-foot span {{ font-family:'IBM Plex Mono',monospace; font-size:11px; }}

    .panel {{ border:1px solid var(--border); border-radius:8px; overflow:hidden; background:var(--surface); }}
    .panel-bar {{ padding:10px 14px; background:var(--surface2); border-bottom:1px solid var(--border);
        font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--muted); }}
    .panel-body {{ padding:14px; font-family:'IBM Plex Mono',monospace; font-size:12px; line-height:1.7;
        color:var(--text2); overflow-y:auto; height:400px; white-space:pre-wrap; }}
    .panel-body.tall {{ height:480px; }}
    .log-ok{{color:var(--text2)}} .log-warn{{color:{T['warn']}}} .log-err{{color:{T['error']}}} .log-info{{color:var(--text2)}}

    .notice {{ padding:12px 14px; border:1px solid var(--border); border-radius:8px; background:var(--surface);
        margin-bottom:20px; font-size:13px; color:var(--text2); line-height:1.5; }}
    .notice strong {{ color:var(--text); font-weight:600; }}
    .peers {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:20px; }}
    .peer {{ font-family:'IBM Plex Mono',monospace; font-size:11px; padding:5px 10px; border:1px solid var(--border);
        border-radius:6px; color:var(--text2); background:var(--surface); }}

    .gate {{ max-width:480px; margin:64px auto; padding:32px; background:var(--surface); border:1px solid var(--border); border-radius:8px; }}
    .gate-title {{ font-size:20px; font-weight:600; margin:0 0 8px; }}
    .gate-sub {{ color:var(--text2); font-size:14px; margin:0 0 24px; line-height:1.6; }}
    .gate-code {{ display:block; margin-top:8px; padding:10px 12px; background:var(--bg); border:1px solid var(--border);
        border-radius:6px; font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--text2); }}

    .warn-box {{ border:1px solid var(--border); border-left:3px solid {T['warn']}; border-radius:6px;
        padding:12px 14px; margin-bottom:16px; background:var(--surface); }}
    .warn-title {{ font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.06em; color:var(--text); margin-bottom:4px; }}
    .warn-text {{ font-size:13px; color:var(--text2); line-height:1.5; }}

    .steps {{ display:flex; margin-bottom:24px; border:1px solid var(--border); border-radius:8px; overflow:hidden; }}
    .step {{ flex:1; text-align:center; padding:16px 8px; border-right:1px solid var(--border); background:var(--surface); }}
    .step:last-child {{ border-right:none; }}
    .step.active {{ background:var(--surface2); }}
    .step.done {{ background:var(--surface); }}
    .step-num {{ width:28px; height:28px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center;
        font-weight:600; font-size:12px; border:1px solid var(--border); margin-bottom:6px; color:var(--muted); }}
    .step.active .step-num {{ border-color:var(--text); color:var(--text); }}
    .step.done .step-num {{ background:var(--text); color:var(--bg); border-color:var(--text); }}
    .step-lbl {{ font-size:10px; font-weight:500; letter-spacing:.04em; text-transform:uppercase; color:var(--muted); }}

    .stButton>button {{ background:var(--surface)!important; border:1px solid var(--border)!important;
        color:var(--text)!important; border-radius:6px!important; min-height:40px!important; font-weight:500!important; box-shadow:none!important; }}
    .stButton>button:hover {{ background:var(--surface2)!important; border-color:var(--border-hi)!important; color:var(--text)!important; }}
    [data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea {{
        background:var(--surface)!important; border:1px solid var(--border)!important;
        border-radius:6px!important; color:var(--text)!important; }}
    div[data-testid="stProgressBar"]>div {{ background:var(--surface2)!important; height:3px!important; border-radius:2px!important; }}
    div[data-testid="stProgressBar"]>div>div {{ background:var(--border-hi)!important; border-radius:2px!important; }}
    [data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap:0; border-bottom:1px solid var(--border); }}
    [data-testid="stTabs"] button {{ font-weight:500!important; font-size:13px!important; color:var(--muted)!important; padding:8px 16px!important; }}
    [data-testid="stTabs"] [aria-selected="true"] {{ color:var(--text)!important; border-bottom:2px solid var(--text)!important; background:transparent!important; }}
    [data-testid="stAlert"], .stAlert {{ border-radius:6px!important; border:1px solid var(--border)!important; background:var(--surface)!important; }}
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


def build_chart(values, height=140, title="CPU 60s"):
    fig = go.Figure()
    y = list(values) if values else [0]
    fig.add_trace(go.Scatter(
        x=list(range(len(y))), y=y, fill="tozeroy",
        fillcolor="rgba(255,255,255,0.04)",
        line=dict(color="#a3a3a3", width=1.5),
        mode="lines",
    ))
    fig.update_layout(
        height=height,
        title=dict(text=title, font=dict(size=11, color=T["muted"], family="Inter"), x=0),
        margin=dict(l=36, r=8, t=32, b=24),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(gridcolor="rgba(255,255,255,0.06)", zeroline=False, range=[0, 100], ticksuffix="%", nticks=4, tickfont=dict(size=10, color=T["muted"])),
        showlegend=False, hovermode="x",
    )
    return fig


def render_metric_bar(label: str, val: float) -> str:
    pct = max(0, min(100, val))
    fill_cls = " mfill-warn" if val >= 90 else ""
    return f"""<div class="mrow">
    <div class="mrow-head"><span>{html.escape(label)}</span><span>{val:.1f}%</span></div>
    <div class="mtrack"><div class="mfill{fill_cls}" style="width:{pct}%"></div></div></div>"""


def render_stat_row(nodes: int, peers: int, avg_cpu: float, avg_ram: float, uptime: str):
    items = [("Nodi attivi", str(nodes)), ("Peer UDP", str(peers)), ("CPU media", f"{avg_cpu}%"), ("RAM media", f"{avg_ram}%"), ("Uptime", uptime)]
    cards = "".join(f'<div class="stat"><div class="stat-lbl">{html.escape(lbl)}</div><div class="stat-val">{html.escape(val)}</div></div>' for lbl, val in items)
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
    badges = []
    if demo:
        badges.append('<span class="badge">Demo</span>')
    if status:
        badges.append(f'<span class="badge badge-ok"><span class="dot"></span>{html.escape(status)}</span>')
    if live:
        badges.append(f'<span class="badge badge-live"><span class="dot"></span>{html.escape(live)}</span>')
    badge_html = f'<div class="badges">{"".join(badges)}</div>' if badges else ""
    st.markdown(f"""
    <div class="topbar"><div>
    <p class="kicker">{CODENAME} · {VERSION}</p>
    <h1 class="topbar-title">{html.escape(title)}</h1>
    <p class="topbar-sub">{html.escape(subtitle)}</p></div>{badge_html}</div>
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
    status = "Simulated" if demo else "Online"
    bars = "".join(render_metric_bar(lbl, v) for lbl, v in [("CPU", cpu), ("RAM", ram), ("Disco", disk)])
    with st.container(border=True):
        st.markdown(f"""<div class="node-head">
        <div><div class="node-name">{html.escape(d['host'])}</div>
        <div class="node-id">{html.escape(nid)}</div></div>
        <span class="tag tag-ok">{status}</span></div>
        <div class="node-tags">
        <span class="tag">{html.escape(meta.get('os', '?'))}</span>
        <span class="tag">{html.escape(meta.get('arch', ''))}</span></div>
        <div class="metrics">{bars}</div>
        <div class="node-foot">
        <span>{html.escape(d['ip'])}</span><span>{threads} threads</span>
        </div>""", unsafe_allow_html=True)
        if d["history"]:
            st.plotly_chart(build_chart(d["history"], title=f"{d['host']} · CPU"), width="stretch", key=f"c_{nid}", config={"displayModeBar": False})


@st.fragment(run_every=timedelta(seconds=REFRESH_SEC))
def live_master(m, demo: bool = False):
    active, pending = m.get_active_nodes(), m.get_pending_peers()
    avg_cpu = round(sum(n["stats"].get("cpu", 0) for n in active.values()) / max(len(active), 1), 1)
    avg_ram = round(sum(n["stats"].get("ram", 0) for n in active.values()) / max(len(active), 1), 1)

    render_stat_row(len(active), len(pending), avg_cpu, avg_ram, m.uptime())

    if demo:
        st.markdown('<div class="notice"><strong>Demo mode</strong> — nodi simulati, telemetria live, terminal remoto. Comandi: fastfetch, ls, cat, whoami, dir.</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="notice">Auto-discovery UDP attivo · refresh ogni {REFRESH_SEC}s</div>', unsafe_allow_html=True)

    if pending:
        chips = "".join(f'<span class="peer">{html.escape(p["host"])} · {html.escape(ip)}</span>' for ip, p in pending.items())
        st.markdown(f'<div class="section">Peer in rete</div><div class="peers">{chips}</div>', unsafe_allow_html=True)

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
            st.markdown(f'<div class="panel"><div class="panel-bar">events.log</div><div class="panel-body">{"<br>".join(lines)}</div></div>', unsafe_allow_html=True)
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
        st.markdown('<div class="section">Comandi rapidi</div>', unsafe_allow_html=True)
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
    st.markdown(f'<div class="panel"><div class="panel-bar">remote.shell</div><div class="panel-body tall">{body}</div></div>', unsafe_allow_html=True)


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
        st.markdown(f'<div class="notice"><strong>Mobile</strong> · {html.escape(urls["network"])} · stessa WiFi, reload sicuro</div>', unsafe_allow_html=True)
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
        st.markdown(f'<div class="notice">Connesso a <strong>{html.escape(st.session_state.target_ip)}</strong></div>', unsafe_allow_html=True)
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
        st.markdown(f'<p style="font-size:15px;font-weight:600;color:{T["text"]};margin:0 0 2px">{CODENAME}</p><p style="font-size:11px;color:{T["muted"]};margin:0 0 16px">{VERSION}</p>', unsafe_allow_html=True)
        st.caption(f"{mode.upper()}" + (" · demo" if demo else ""))
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
