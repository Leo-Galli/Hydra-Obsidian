import sys, os, time, json, uuid, socket, threading, hashlib, hmac, atexit, subprocess, platform, html
import psutil
import streamlit as st
import plotly.graph_objects as go
import zmq
from datetime import datetime
from collections import deque

# --- CORE ---
VERSION = "V3.0.0"
CODENAME = "HYDRA"
SECRET_KEY = b"HYDRA_SINGULARITY_ENCRYPT_2026"
ADMIN_KEY = SECRET_KEY
TCP_PORT = 5555
UDP_PORT = 5556
BT_SSID = "HYDRA_COMMAND_CENTER"
NODE_TIMEOUT_SEC = 10
REFRESH_MS = 2000
CMD_TIMEOUT_SEC = 30
CMD_MAX_LEN = 4096
EXEC_RESULT_TTL = 60

C = {
    "bg": "#08080c",
    "surface": "#0f0f14",
    "surface2": "#14141b",
    "border": "rgba(255,255,255,0.07)",
    "border_hi": "rgba(16,185,129,0.35)",
    "accent": "#10b981",
    "accent_dim": "#059669",
    "accent_glow": "rgba(16,185,129,0.12)",
    "text": "#f1f5f9",
    "text2": "#94a3b8",
    "muted": "#64748b",
    "warn": "#f59e0b",
    "error": "#ef4444",
}


def apply_styles():
    st.set_page_config(page_title=f"{CODENAME} {VERSION}", layout="wide", initial_sidebar_state="expanded")
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
    :root {{
        --bg:{C['bg']}; --surface:{C['surface']}; --surface2:{C['surface2']};
        --border:{C['border']}; --accent:{C['accent']}; --text:{C['text']};
        --text2:{C['text2']}; --muted:{C['muted']};
    }}
    html,body,[class*="css"] {{ background:var(--bg)!important; color:var(--text); font-family:'IBM Plex Sans',sans-serif; }}
    #MainMenu,footer,header {{ visibility:hidden; }}
    .block-container {{ padding:2rem 2.5rem 3rem; max-width:1440px; }}
    [data-testid="stSidebar"] {{ background:var(--surface); border-right:1px solid var(--border); }}
    [data-testid="stSidebar"] .block-container {{ padding-top:1.5rem; }}

    .hero {{ background:var(--surface); border:1px solid var(--border); border-radius:16px; padding:28px 32px; margin-bottom:24px; display:flex; align-items:center; justify-content:space-between; gap:24px; }}
    .hero-eyebrow {{ font-family:'IBM Plex Mono',monospace; font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); margin-bottom:6px; }}
    .hero-title {{ font-size:32px; font-weight:700; letter-spacing:-.03em; color:var(--text); margin:0; line-height:1.15; }}
    .hero-meta {{ font-family:'IBM Plex Mono',monospace; font-size:12px; color:var(--text2); margin:8px 0 0; }}
    .hero-status {{ display:flex; align-items:center; gap:10px; background:{C['accent_glow']}; border:1px solid {C['border_hi']}; border-radius:999px; padding:10px 18px; font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:500; letter-spacing:.08em; color:var(--accent); white-space:nowrap; }}
    .status-dot {{ width:8px; height:8px; background:var(--accent); border-radius:50%; box-shadow:0 0 8px var(--accent); animation:blink 2.4s ease-in-out infinite; }}
    @keyframes blink {{ 0%,100%{{opacity:1}} 50%{{opacity:.35}} }}
    @media(prefers-reduced-motion:reduce){{ .status-dot{{animation:none}} }}

    [data-testid="stMetric"] {{ background:var(--surface)!important; border:1px solid var(--border)!important; border-radius:12px!important; padding:18px 20px!important; }}
    [data-testid="stMetricLabel"] {{ font-family:'IBM Plex Mono',monospace!important; font-size:10px!important; letter-spacing:.12em!important; text-transform:uppercase!important; color:var(--muted)!important; }}
    [data-testid="stMetricValue"] {{ font-size:26px!important; font-weight:600!important; color:var(--text)!important; }}
    [data-testid="stMetricDelta"] {{ display:none; }}

    [data-testid="stVerticalBlockBorderWrapper"] {{ background:var(--surface)!important; border:1px solid var(--border)!important; border-radius:14px!important; padding:4px 8px 8px!important; margin-bottom:16px!important; box-shadow:0 4px 24px rgba(0,0,0,.25); }}
    [data-testid="stVerticalBlockBorderWrapper"]:hover {{ border-color:{C['border_hi']}!important; }}

    .node-head {{ display:flex; align-items:center; justify-content:space-between; padding:12px 8px 16px; border-bottom:1px solid var(--border); margin-bottom:4px; }}
    .node-head-left {{ display:flex; align-items:center; gap:12px; flex-wrap:wrap; }}
    .node-badge {{ font-family:'IBM Plex Mono',monospace; font-size:10px; font-weight:500; letter-spacing:.1em; color:var(--accent); background:{C['accent_glow']}; border:1px solid {C['border_hi']}; border-radius:6px; padding:4px 10px; }}
    .node-os {{ font-family:'IBM Plex Mono',monospace; font-size:10px; color:var(--muted); background:var(--surface2); border:1px solid var(--border); border-radius:6px; padding:4px 10px; }}
    .node-name {{ font-size:18px; font-weight:600; color:var(--text); }}
    .node-id {{ font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--muted); background:var(--surface2); border:1px solid var(--border); border-radius:6px; padding:5px 10px; }}
    .stat-label {{ font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); margin:0 0 4px; }}
    .stat-num {{ font-size:22px; font-weight:600; color:var(--text); margin:0 0 10px; }}
    .stat-num.accent {{ color:var(--accent); }}
    .stat-sub {{ font-family:'IBM Plex Mono',monospace; font-size:13px; color:var(--text2); margin:0 0 4px; }}
    div[data-testid="stProgressBar"]>div {{ background:var(--surface2)!important; border-radius:4px!important; height:6px!important; }}
    div[data-testid="stProgressBar"]>div>div {{ background:linear-gradient(90deg,{C['accent_dim']},{C['accent']})!important; border-radius:4px!important; }}

    .terminal-wrap {{ border:1px solid var(--border); border-radius:12px; overflow:hidden; background:#060608; }}
    .terminal-bar {{ display:flex; align-items:center; gap:7px; padding:10px 14px; background:var(--surface2); border-bottom:1px solid var(--border); }}
    .tb-dot {{ width:10px; height:10px; border-radius:50%; }}
    .tb-dot.r {{ background:#ef4444; }} .tb-dot.y {{ background:#f59e0b; }} .tb-dot.g {{ background:#10b981; }}
    .tb-title {{ margin-left:8px; font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--muted); }}
    .log-body {{ padding:16px; font-family:'IBM Plex Mono',monospace; font-size:12px; line-height:1.75; height:420px; overflow-y:auto; color:var(--muted); }}
    .log-body.tall {{ height:520px; }}
    .log-body::-webkit-scrollbar {{ width:5px; }}
    .log-body::-webkit-scrollbar-thumb {{ background:#2a2a35; border-radius:3px; }}
    .log-ok {{ color:{C['accent']}; }} .log-warn {{ color:{C['warn']}; }} .log-err {{ color:{C['error']}; }}
    .log-cmd {{ color:#60a5fa; }} .log-out {{ color:#cbd5e1; }}

    .section-head {{ font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:500; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); margin:0 0 16px; padding-bottom:10px; border-bottom:1px solid var(--border); }}
    .empty-box {{ text-align:center; padding:48px 32px; border:1px dashed var(--border); border-radius:14px; color:var(--muted); background:var(--surface); }}
    .empty-box strong {{ color:var(--text2); display:block; margin-bottom:8px; font-size:15px; }}
    .empty-box code {{ font-family:'IBM Plex Mono',monospace; font-size:12px; color:var(--accent); background:{C['accent_glow']}; padding:4px 10px; border-radius:6px; }}

    .admin-warn {{ background:rgba(239,68,68,.08); border:1px solid rgba(239,68,68,.35); border-radius:10px; padding:16px 20px; margin-bottom:20px; }}
    .admin-warn-title {{ font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:{C['error']}; margin-bottom:8px; }}
    .admin-warn-text {{ font-size:13px; color:var(--text2); line-height:1.6; }}

    .steps {{ display:flex; margin-bottom:32px; background:var(--surface); border:1px solid var(--border); border-radius:12px; overflow:hidden; }}
    .step {{ flex:1; text-align:center; padding:20px 12px; border-right:1px solid var(--border); }}
    .step:last-child {{ border-right:none; }}
    .step.active {{ background:{C['accent_glow']}; }}
    .step.done {{ background:rgba(16,185,129,.06); }}
    .step-num {{ width:32px; height:32px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; font-size:13px; font-weight:600; border:2px solid var(--border); color:var(--muted); margin-bottom:8px; }}
    .step.active .step-num {{ border-color:var(--accent); color:var(--accent); background:{C['accent_glow']}; }}
    .step.done .step-num {{ border-color:var(--accent); background:var(--accent); color:#000; }}
    .step-lbl {{ font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); }}
    .step.active .step-lbl {{ color:var(--accent); }}
    .link-strip {{ display:flex; align-items:center; gap:12px; background:{C['accent_glow']}; border:1px solid {C['border_hi']}; border-radius:10px; padding:14px 20px; margin-bottom:20px; font-family:'IBM Plex Mono',monospace; font-size:13px; color:var(--accent); }}

    .stButton>button {{ background:transparent!important; border:1px solid var(--border)!important; color:var(--text2)!important; font-weight:500!important; border-radius:8px!important; height:42px!important; font-size:13px!important; }}
    .stButton>button:hover {{ border-color:var(--accent)!important; color:var(--accent)!important; background:{C['accent_glow']}!important; }}
    [data-testid="stRadio"] label,[data-testid="stTextInput"] label,[data-testid="stTextArea"] label,[data-testid="stSelectbox"] label {{ font-size:13px!important; color:var(--text2)!important; }}
    [data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea {{ background:var(--surface2)!important; border:1px solid var(--border)!important; border-radius:8px!important; color:var(--text)!important; font-family:'IBM Plex Mono',monospace!important; }}

    .sb-brand {{ font-size:20px; font-weight:700; color:var(--text); margin-bottom:2px; }}
    .sb-ver {{ font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--accent); letter-spacing:.06em; }}
    .sb-block {{ background:var(--surface2); border:1px solid var(--border); border-radius:8px; padding:12px 14px; margin-bottom:12px; }}
    .sb-block-title {{ font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); margin-bottom:8px; }}
    [data-testid="stTabs"] button {{ font-family:'IBM Plex Mono',monospace; font-size:12px; letter-spacing:.06em; }}
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
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=CMD_TIMEOUT_SEC,
            executable=shell_exe,
            cwd=os.path.expanduser("~"),
        )
        return {
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "exit_code": proc.returncode,
            "os": platform.system(),
            "shell": shell_exe,
            "error": None,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Timeout ({CMD_TIMEOUT_SEC}s)", "exit_code": -1, "os": platform.system(), "shell": shell_exe, "error": "timeout"}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": -1, "os": platform.system(), "shell": shell_exe, "error": str(e)}


def build_chart(values, height=180, title="CPU Load — 60s"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(len(values))), y=list(values), fill="tozeroy",
        fillcolor="rgba(16,185,129,0.1)", line=dict(color=C["accent"], width=2, shape="spline"), mode="lines",
    ))
    fig.update_layout(
        height=height,
        title=dict(text=title, font=dict(size=11, color=C["muted"], family="IBM Plex Mono"), x=0, xanchor="left"),
        margin=dict(l=36, r=12, t=32, b=28),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=C["surface2"],
        font=dict(family="IBM Plex Mono", color=C["muted"], size=10),
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(gridcolor="rgba(255,255,255,0.04)", range=[0, 100], ticksuffix="%", nticks=5, zeroline=False),
        showlegend=False,
    )
    fig.update_xaxes(showline=False)
    fig.update_yaxes(showline=False)
    return fig


def format_log_line(line: str) -> str:
    if any(k in line for k in ("ERRORE", "INVALIDA", "negato", "RIFIUTATO")):
        return f'<span class="log-err">{html.escape(line)}</span>'
    if "HANDSHAKE" in line or "EXEC OK" in line:
        return f'<span class="log-ok">{html.escape(line)}</span>'
    if "EXEC" in line or "WARN" in line:
        return f'<span class="log-warn">{html.escape(line)}</span>'
    return html.escape(line)


def format_terminal_entry(entry: dict) -> str:
    ts = html.escape(entry.get("ts", ""))
    host = html.escape(entry.get("host", "?"))
    cmd = html.escape(entry.get("command", ""))
    exit_code = entry.get("exit_code", "?")
    stdout = html.escape(entry.get("stdout", "") or "")
    stderr = html.escape(entry.get("stderr", "") or "")
    block = f'<span class="log-cmd">[{ts}] {host} $ {cmd}</span><br>'
    block += f'<span class="log-muted">exit {exit_code}</span><br>'
    if stdout:
        block += f'<span class="log-out">{stdout.replace(chr(10), "<br>")}</span><br>'
    if stderr:
        block += f'<span class="log-err">{stderr.replace(chr(10), "<br>")}</span><br>'
    block += '<br>'
    return block


def inject_refresh():
    st.markdown(f"<script>setTimeout(function(){{ window.location.reload(); }}, {REFRESH_MS});</script>", unsafe_allow_html=True)


def render_hero(title: str, subtitle: str, status: str = ""):
    status_html = f'<div class="hero-status"><span class="status-dot"></span>{status}</div>' if status else ""
    st.markdown(f"""
    <div class="hero">
        <div>
            <div class="hero-eyebrow">Home Lab &amp; Datacenter Control Plane</div>
            <div class="hero-title">{title}</div>
            <div class="hero-meta">{subtitle}</div>
        </div>
        {status_html}
    </div>
    """, unsafe_allow_html=True)


def render_sidebar(mode: str):
    with st.sidebar:
        st.markdown(f"<div class='sb-brand'>{CODENAME}</div><div class='sb-ver'>{VERSION} / {mode.upper()}</div>", unsafe_allow_html=True)
        st.divider()
        st.markdown(f"""
        <div class="sb-block"><div class="sb-block-title">Network</div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:{C['text2']}">TCP {TCP_PORT} data<br>UDP {UDP_PORT} beacon</div></div>
        <div class="sb-block"><div class="sb-block-title">Security</div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:{C['text2']}">HMAC-SHA256<br>Admin exec gate</div></div>
        <div class="sb-block"><div class="sb-block-title">Targets</div>
        <div style="font-size:12px;color:{C['text2']}">Home lab, ufficio,<br>rack datacenter</div></div>
        """, unsafe_allow_html=True)
        st.markdown("**Launch**")
        st.code("streamlit run main.py -- master", language="bash")
        st.code("streamlit run main.py -- worker", language="bash")


def render_node_card(nid: str, host: str, ip: str, stats: dict, history: list, meta: dict):
    cpu, ram, disk = float(stats.get("cpu", 0)), float(stats.get("ram", 0)), float(stats.get("disk", 0))
    threads = stats.get("threads", 0)
    os_label = f"{meta.get('os', '?')} {meta.get('release', '')}".strip()

    with st.container(border=True):
        st.markdown(f"""
        <div class="node-head">
            <div class="node-head-left">
                <span class="node-badge">ONLINE</span>
                <span class="node-name">{html.escape(host)}</span>
                <span class="node-os">{html.escape(os_label)}</span>
            </div>
            <span class="node-id">{html.escape(nid)}</span>
        </div>
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
            st.markdown(
                f'<p class="stat-label">Rete</p><p class="stat-sub">{html.escape(ip)}</p>'
                f'<p class="stat-label" style="margin-top:12px">Threads</p><p class="stat-num" style="font-size:18px">{threads}</p>',
                unsafe_allow_html=True,
            )
        if history:
            st.plotly_chart(build_chart(history, title=f"{host} — CPU 60s"), width="stretch", key=f"chart_{nid}")


class HydraMaster:
    def __init__(self):
        self.nodes = {}
        self.events = deque(maxlen=300)
        self.terminal_log = deque(maxlen=200)
        self.exec_results = {}
        self.pending_exec = {}
        self.lock = threading.Lock()
        self.active = True
        self._socket_ok = False
        self.started_at = datetime.now()
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
        self.events.appendleft(f"[{self._ts()}] Beacon UDP + collector ZMQ avviati")

    def _discovery_beacon(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            while self.active:
                msg = f"HYDRA_BEACON|{BT_SSID}|{get_local_ip()}".encode()
                for dest in [("<broadcast>", UDP_PORT), ("127.0.0.1", UDP_PORT)]:
                    try:
                        s.sendto(msg, dest)
                    except Exception:
                        pass
                time.sleep(2)

    def _data_collector(self):
        while self.active:
            try:
                if self.socket.poll(1000, zmq.POLLIN):
                    parts = self.socket.recv_multipart(flags=zmq.NOBLOCK)
                    if len(parts) < 4:
                        continue
                    identity, _, payload, sig = parts[0], parts[1], parts[2], parts[3]
                    if not verify_signature(payload, sig):
                        self.events.appendleft(f"[{self._ts()}] FIRMA INVALIDA — pacchetto scartato")
                        continue
                    data = json.loads(payload.decode("utf-8"))
                    msg_type = data.get("t", "tel")
                    if msg_type == "tel":
                        self._sync_node(identity, data)
                    elif msg_type == "exec_result":
                        self._store_exec_result(data)
            except zmq.Again:
                pass
            except Exception as e:
                self.events.appendleft(f"[{self._ts()}] Errore collector: {e}")
            self._expire_pending()

    def _sync_node(self, identity, data):
        nid = data.get("id", "UNKNOWN")
        with self.lock:
            is_new = nid not in self.nodes
            self.nodes[nid] = {
                "host": data.get("host", "?"),
                "ip": data.get("ip", "?"),
                "stats": data.get("s", {}),
                "history": data.get("h", []),
                "meta": data.get("meta", {}),
                "identity": identity,
                "last": time.time(),
            }
            if is_new:
                os_info = data.get("meta", {}).get("os", "?")
                self.events.appendleft(
                    f"[{self._ts()}] HANDSHAKE OK: {data.get('host', '?')} ({nid}) @ {data.get('ip', '?')} [{os_info}]"
                )

    def _store_exec_result(self, data):
        cmd_id = data.get("cmd_id", "")
        entry = {
            "cmd_id": cmd_id,
            "node_id": data.get("id", "?"),
            "host": data.get("host", "?"),
            "command": data.get("command", ""),
            "stdout": data.get("stdout", ""),
            "stderr": data.get("stderr", ""),
            "exit_code": data.get("exit_code", -1),
            "os": data.get("os", "?"),
            "ts": self._ts(),
        }
        with self.lock:
            self.exec_results[cmd_id] = entry
            self.terminal_log.appendleft(entry)
            self.pending_exec.pop(cmd_id, None)
        self.events.appendleft(
            f"[{self._ts()}] EXEC OK: {entry['host']} exit={entry['exit_code']} cmd={entry['command'][:60]}"
        )

    def _expire_pending(self):
        now = time.time()
        with self.lock:
            expired = [k for k, v in self.pending_exec.items() if now - v["sent_at"] > EXEC_RESULT_TTL]
            for cmd_id in expired:
                p = self.pending_exec.pop(cmd_id)
                self.events.appendleft(f"[{self._ts()}] EXEC TIMEOUT: {p['host']} cmd={p['command'][:60]}")

    def send_command(self, node_id: str, command: str):
        command = command.strip()
        if not command or len(command) > CMD_MAX_LEN:
            return None
        cmd_id = uuid.uuid4().hex[:12]
        with self.lock:
            node = self.nodes.get(node_id)
            if not node or "identity" not in node:
                return None
            identity = node["identity"]
            host = node["host"]
        payload_obj = {"t": "exec", "cmd_id": cmd_id, "command": command}
        raw = json.dumps(payload_obj).encode("utf-8")
        try:
            self.socket.send_multipart([identity, b"", raw, make_signature(raw)])
        except Exception as e:
            self.events.appendleft(f"[{self._ts()}] EXEC SEND ERR: {e}")
            return None
        with self.lock:
            self.pending_exec[cmd_id] = {"node_id": node_id, "host": host, "command": command, "sent_at": time.time()}
        self.events.appendleft(f"[{self._ts()}] EXEC SENT: {host} ({node_id}) cmd={command[:60]}")
        return cmd_id

    def send_command_all(self, command: str) -> list[str]:
        active = self.get_active_nodes()
        return [cid for nid in active if (cid := self.send_command(nid, command))]

    def get_active_nodes(self):
        now = time.time()
        with self.lock:
            return {k: dict(v) for k, v in self.nodes.items() if now - v["last"] < NODE_TIMEOUT_SEC}

    def get_terminal_log(self) -> list:
        with self.lock:
            return list(self.terminal_log)

    def uptime(self) -> str:
        delta = datetime.now() - self.started_at
        h, rem = divmod(int(delta.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

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

    def _send_signed(self, payload_obj: dict):
        raw = json.dumps(payload_obj).encode("utf-8")
        with self.sock_lock:
            self.sock.send_multipart([b"", raw, make_signature(raw)])

    def _handle_exec(self, data: dict):
        command = str(data.get("command", "")).strip()[:CMD_MAX_LEN]
        cmd_id = data.get("cmd_id", "")
        if not command or not cmd_id:
            return
        result = run_shell_command(command)
        self._send_signed({
            "t": "exec_result",
            "cmd_id": cmd_id,
            "id": self.id,
            "host": socket.gethostname(),
            "command": command,
            "stdout": result["stdout"][:65536],
            "stderr": result["stderr"][:65536],
            "exit_code": result["exit_code"],
            "os": result["os"],
        })

    def _worker_loop(self):
        psutil.cpu_percent(interval=None)
        disk_path = "C:\\" if sys.platform == "win32" else "/"
        last_telemetry = 0.0
        while self.connected:
            try:
                with self.sock_lock:
                    events = self.sock.poll(100, zmq.POLLIN)
                if events:
                    with self.sock_lock:
                        parts = self.sock.recv_multipart(flags=zmq.NOBLOCK)
                    if len(parts) >= 3:
                        payload, sig = parts[-2], parts[-1]
                        if verify_signature(payload, sig):
                            msg = json.loads(payload.decode("utf-8"))
                            if msg.get("t") == "exec":
                                self._handle_exec(msg)
                now = time.time()
                if now - last_telemetry >= 1.0:
                    stats = {
                        "cpu": psutil.cpu_percent(interval=None),
                        "ram": psutil.virtual_memory().percent,
                        "disk": psutil.disk_usage(disk_path).percent,
                        "threads": threading.active_count(),
                    }
                    self.last_stats = stats
                    self.cpu_history.append(stats["cpu"])
                    self._send_signed({
                        "t": "tel",
                        "id": self.id,
                        "host": socket.gethostname(),
                        "ip": get_local_ip(),
                        "s": stats,
                        "h": list(self.cpu_history),
                        "meta": self.meta,
                    })
                    last_telemetry = now
            except zmq.ZMQError:
                self.connected = False
                break
            except Exception:
                pass


def render_monitor_tab(m: HydraMaster, active: dict):
    col_nodes, col_log = st.columns([1.6, 1])
    with col_nodes:
        st.markdown("<div class='section-head'>Topologia nodi</div>", unsafe_allow_html=True)
        if not active:
            st.markdown("""
            <div class="empty-box"><strong>Nessun worker connesso</strong>
            Avvia un worker su ogni macchina target<br><br>
            <code>streamlit run main.py -- worker</code></div>
            """, unsafe_allow_html=True)
        for nid, d in active.items():
            render_node_card(nid, d["host"], d["ip"], d["stats"], d["history"], d.get("meta", {}))
    with col_log:
        st.markdown("<div class='section-head'>Log eventi</div>", unsafe_allow_html=True)
        lines = [format_log_line(l) for l in list(m.events)] if m.events else ["In attesa di segnali..."]
        st.markdown(f"""
        <div class="terminal-wrap"><div class="terminal-bar">
        <span class="tb-dot r"></span><span class="tb-dot y"></span><span class="tb-dot g"></span>
        <span class="tb-title">hydra-events.log</span></div>
        <div class="log-body">{"<br>".join(lines)}</div></div>
        """, unsafe_allow_html=True)


def render_terminal_tab(m: HydraMaster, active: dict):
    st.markdown("""
    <div class="admin-warn">
        <div class="admin-warn-title">Privilegi amministratore richiesti</div>
        <div class="admin-warn-text">
            I comandi remoti vengono eseguiti con i privilegi dell'utente che avvia il Worker
            (tipicamente amministratore/root). Usare solo su infrastrutture di proprieta.
            Ogni comando e firmato HMAC-SHA256 e richiede la chiave admin.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if "admin_unlocked" not in st.session_state:
        st.session_state.admin_unlocked = False
    if "term_history" not in st.session_state:
        st.session_state.term_history = []

    if not st.session_state.admin_unlocked:
        st.markdown("<div class='section-head'>Sblocco terminal admin</div>", unsafe_allow_html=True)
        admin_key = st.text_input("Chiave admin", type="password", key="admin_key_input")
        confirm = st.checkbox("Confermo di eseguire comandi con privilegi amministratore su nodi remoti")
        if st.button("Sblocca terminal", width="stretch"):
            if admin_key.encode() == ADMIN_KEY and confirm:
                st.session_state.admin_unlocked = True
                m.events.appendleft(f"[{m._ts()}] Terminal admin sbloccato")
                st.rerun()
            else:
                st.error("Chiave admin non valida o conferma mancante.")
        return

    if not active:
        st.info("Nessun nodo online. Connetti almeno un Worker per usare il terminal remoto.")
        return

    st.markdown("<div class='section-head'>Terminal remoto</div>", unsafe_allow_html=True)

    node_options = {f"{d['host']} ({nid})": nid for nid, d in active.items()}
    labels = ["Tutti i nodi"] + list(node_options.keys())
    target_label = st.selectbox("Target", labels)
    command = st.text_area(
        "Comando shell",
        placeholder="Windows: dir & echo ok\nLinux/macOS: ls -la && uname -a",
        height=100,
    )

    os_hints = st.expander("Comandi cross-platform")
    with os_hints:
        st.markdown("""
        | Azione | Windows | Linux / macOS |
        |:---|:---|:---|
        | Lista file | `dir` | `ls -la` |
        | Hostname | `hostname` | `hostname` |
        | Utente | `whoami` | `whoami` |
        | Uptime | `systeminfo` | `uptime` |
        | Processi | `tasklist` | `ps aux` |
        | Disco | `wmic logicaldisk get size,freespace,caption` | `df -h` |
        | Rete | `ipconfig` | `ip addr` o `ifconfig` |
        """)

    bc1, bc2, bc3 = st.columns([2, 2, 1])
    with bc1:
        run_single = st.button("Esegui", width="stretch")
    with bc2:
        run_all = st.button("Esegui su tutti", width="stretch")
    with bc3:
        if st.button("Lock", width="stretch"):
            st.session_state.admin_unlocked = False
            st.rerun()

    if run_single and command.strip():
        if target_label == "Tutti i nodi":
            m.send_command_all(command.strip())
        else:
            m.send_command(node_options[target_label], command.strip())
        time.sleep(0.3)

    if run_all and command.strip():
        m.send_command_all(command.strip())
        time.sleep(0.3)

    entries = m.get_terminal_log()
    if entries:
        term_html = "".join(format_terminal_entry(e) for e in entries)
    else:
        term_html = '<span class="log-muted">Nessun comando eseguito.</span>'

    st.markdown(f"""
    <div class="terminal-wrap"><div class="terminal-bar">
    <span class="tb-dot r"></span><span class="tb-dot y"></span><span class="tb-dot g"></span>
    <span class="tb-title">hydra-remote.shell</span></div>
    <div class="log-body tall">{term_html}</div></div>
    """, unsafe_allow_html=True)


def render_master(m: HydraMaster):
    render_hero("HYDRA OVERLORD", f"{VERSION}  /  TCP {TCP_PORT}  /  UDP {UDP_PORT}", "ACTIVE")
    if not m._socket_ok:
        st.error(f"Impossibile aprire la porta {TCP_PORT}. Chiudi altri processi e riavvia.")
        return

    active = m.get_active_nodes()
    avg_cpu = round(sum(n["stats"].get("cpu", 0) for n in active.values()) / max(len(active), 1), 1)
    avg_ram = round(sum(n["stats"].get("ram", 0) for n in active.values()) / max(len(active), 1), 1)

    r1 = st.columns(5)
    r1[0].metric("Nodi", len(active))
    r1[1].metric("CPU media", f"{avg_cpu}%")
    r1[2].metric("RAM media", f"{avg_ram}%")
    r1[3].metric("Uptime", m.uptime())
    r1[4].metric("Remote exec", "ON")

    tab_mon, tab_term = st.tabs(["Monitoraggio", "Terminal remoto"])
    with tab_mon:
        render_monitor_tab(m, active)
    with tab_term:
        render_terminal_tab(m, active)

    inject_refresh()


def render_stepper(current: int):
    steps = ["Scoperta", "Autenticazione", "Streaming"]
    html_out = '<div class="steps">'
    for i, label in enumerate(steps, 1):
        cls = "done" if i < current else ("active" if i == current else "")
        html_out += f'<div class="step {cls}"><div class="step-num">{i}</div><div class="step-lbl">{label}</div></div>'
    html_out += "</div>"
    st.markdown(html_out, unsafe_allow_html=True)


def render_worker():
    render_hero("HYDRA WORKER", f"Agent Module  /  {VERSION}  /  {platform.system()}", "STANDBY")
    if "step" not in st.session_state:
        st.session_state.step = 1
    render_stepper(st.session_state.step)

    if st.session_state.step == 1:
        st.markdown("<div class='section-head'>Discovery master</div>", unsafe_allow_html=True)
        method = st.radio("Metodo", ["Automatico (Beacon + Localhost)", "Scansione subnet", "IP manuale"], horizontal=True)
        static_ip = st.text_input("IP Master", placeholder="192.168.1.100") if method == "IP manuale" else ""
        if st.button("Avvia scoperta", width="stretch"):
            if method == "Automatico (Beacon + Localhost)":
                found = False
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        s.bind(("", UDP_PORT))
                        s.settimeout(3.0)
                        data, _ = s.recvfrom(1024)
                        parts = data.decode().split("|")
                        if parts[0] == "HYDRA_BEACON":
                            st.session_state.target_ip = parts[2]
                            found = True
                except Exception:
                    pass
                if not found:
                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            s.settimeout(0.5)
                            if s.connect_ex(("127.0.0.1", TCP_PORT)) == 0:
                                st.session_state.target_ip = "127.0.0.1"
                                found = True
                    except Exception:
                        pass
                if found:
                    st.session_state.step = 2
                    st.rerun()
                else:
                    st.error("Master non trovato.")
            elif method == "Scansione subnet":
                found = False
                with st.spinner("Scansione..."):
                    try:
                        base_ip = ".".join(get_local_ip().split(".")[:-1])
                        for i in range(1, 255):
                            target = f"{base_ip}.{i}"
                            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                                s.settimeout(0.02)
                                if s.connect_ex((target, TCP_PORT)) == 0:
                                    st.session_state.target_ip = target
                                    found = True
                                    break
                    except Exception as e:
                        st.error(str(e))
                if found:
                    st.session_state.step = 2
                    st.rerun()
                else:
                    st.error("Nessun Master trovato.")
            elif method == "IP manuale":
                if static_ip.strip():
                    st.session_state.target_ip = static_ip.strip()
                    st.session_state.step = 2
                    st.rerun()
                else:
                    st.error("Inserisci un IP valido.")

    elif st.session_state.step == 2:
        st.info(f"Master: {st.session_state.target_ip}")
        st.markdown("<div class='section-head'>Autenticazione</div>", unsafe_allow_html=True)
        st.caption("Avvia il Worker come amministratore per abilitare l'esecuzione remota dei comandi.")
        key_in = st.text_input("Chiave cluster", type="password")
        ca, cb = st.columns([3, 1])
        with ca:
            if st.button("Connetti", width="stretch"):
                if key_in.encode() == SECRET_KEY:
                    worker = HydraWorker(st.session_state.target_ip)
                    if worker.engage_link():
                        st.session_state.worker = worker
                        st.session_state.step = 3
                        st.rerun()
                    else:
                        st.error(f"Connessione fallita: {worker.error_msg}")
                else:
                    st.error("Chiave non valida.")
        with cb:
            if st.button("Indietro"):
                st.session_state.step = 1
                st.rerun()

    elif st.session_state.step == 3:
        w: HydraWorker = st.session_state.worker
        if not w.connected:
            st.error("Connessione persa.")
            if st.button("Riconnetti"):
                st.session_state.step = 1
                del st.session_state.worker
                st.rerun()
            return
        st.markdown(
            f'<div class="link-strip"><span class="status-dot"></span>SECURE LINK &rarr; {st.session_state.target_ip}</div>',
            unsafe_allow_html=True,
        )
        s = w.last_stats
        with st.container(border=True):
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("CPU", f"{s['cpu']:.1f}%")
            m2.metric("RAM", f"{s['ram']:.1f}%")
            m3.metric("Disco", f"{s['disk']:.1f}%")
            m4.metric("OS", w.meta.get("os", "?"))
            st.plotly_chart(build_chart(list(w.cpu_history), height=320, title="Local CPU — 60s"), width="stretch")
        st.caption("Remote exec attivo — il Master puo inviare comandi shell a questo nodo.")
        if st.button("Disconnetti", width="stretch"):
            w.disconnect()
            st.session_state.step = 1
            del st.session_state.worker
            st.rerun()
        inject_refresh()


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
        st.error("Modalita non valida. Usa master o worker.")


if __name__ == "__main__":
    main()
