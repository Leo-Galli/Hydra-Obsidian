import sys, os, time, json, uuid, socket, threading, hashlib, hmac, atexit, subprocess, platform, html
from datetime import datetime, timedelta
import psutil
import streamlit as st
import plotly.graph_objects as go
import zmq
from collections import deque

VERSION = "V3.2.0"
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
    "bg": "#09090b",
    "surface": "#18181b",
    "surface2": "#27272a",
    "border": "#3f3f46",
    "primary": "#3b82f6",
    "primary_dim": "#2563eb",
    "primary_glow": "rgba(59,130,246,0.12)",
    "accent": "#22c55e",
    "accent_glow": "rgba(34,197,94,0.12)",
    "text": "#fafafa",
    "text2": "#a1a1aa",
    "muted": "#71717a",
    "warn": "#eab308",
    "error": "#ef4444",
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
        key = sys.argv[2].strip()
        if len(key) >= MIN_KEY_LEN:
            return key.encode("utf-8")
    return None


def get_cluster_key():
    return st.session_state.get("cluster_key")


def set_cluster_key(key: bytes):
    st.session_state.cluster_key = key


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
    html,body,[class*="css"] {{ background:var(--bg)!important; color:var(--text); font-family:'Inter',system-ui,sans-serif; }}
    #MainMenu,footer,header {{ visibility:hidden; }}
    .block-container {{ padding:32px 40px 48px; max-width:1360px; }}
    [data-testid="stSidebar"] {{ background:var(--surface); border-right:1px solid var(--border); }}

    .shell-card {{ background:var(--surface); border:1px solid var(--border); border-radius:16px; padding:32px; margin-bottom:24px; }}
    .shell-eyebrow {{ font-size:12px; font-weight:600; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin-bottom:8px; }}
    .shell-title {{ font-size:28px; font-weight:700; letter-spacing:-.02em; margin:0 0 8px; }}
    .shell-sub {{ color:var(--text2); font-size:14px; margin:0; }}
    .shell-row {{ display:flex; align-items:center; justify-content:space-between; gap:24px; flex-wrap:wrap; }}
    .pill {{ display:inline-flex; align-items:center; gap:8px; padding:8px 14px; border-radius:999px; font-size:12px; font-weight:600; border:1px solid; }}
    .pill-ok {{ color:var(--accent); background:{T['accent_glow']}; border-color:rgba(34,197,94,.35); }}
    .pill-live {{ color:var(--primary); background:{T['primary_glow']}; border-color:rgba(59,130,246,.35); }}
    .dot {{ width:8px; height:8px; border-radius:50%; background:currentColor; }}
    .dot-pulse {{ animation:pulse 2s ease-in-out infinite; }}
    @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.35}} }}
    @media(prefers-reduced-motion:reduce){{ .dot-pulse{{animation:none}} }}

    [data-testid="stMetric"] {{ background:var(--surface)!important; border:1px solid var(--border)!important; border-radius:12px!important; padding:16px!important; }}
    [data-testid="stMetricLabel"] {{ font-size:11px!important; font-weight:600!important; letter-spacing:.06em!important; text-transform:uppercase!important; color:var(--muted)!important; }}
    [data-testid="stMetricValue"] {{ font-size:24px!important; font-weight:700!important; }}
    [data-testid="stMetricDelta"] {{ display:none; }}
    [data-testid="stVerticalBlockBorderWrapper"] {{ background:var(--surface)!important; border:1px solid var(--border)!important; border-radius:12px!important; padding:8px!important; margin-bottom:16px!important; }}

    .section {{ font-size:12px; font-weight:600; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin:0 0 16px; padding-bottom:8px; border-bottom:1px solid var(--border); }}
    .node-top {{ display:flex; justify-content:space-between; align-items:center; gap:16px; padding:12px 8px 16px; border-bottom:1px solid var(--border); margin-bottom:8px; }}
    .node-left {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
    .tag {{ font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; padding:4px 8px; border-radius:6px; border:1px solid var(--border); color:var(--text2); }}
    .tag-live {{ color:var(--accent); border-color:rgba(34,197,94,.35); background:{T['accent_glow']}; }}
    .node-title {{ font-size:16px; font-weight:600; }}
    .kpi-label {{ font-size:11px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); margin:0 0 4px; }}
    .kpi-value {{ font-size:20px; font-weight:700; margin:0 0 8px; }}
    .kpi-value.primary {{ color:var(--primary); }}
    .kpi-mono {{ font-family:'JetBrains Mono',monospace; font-size:12px; color:var(--text2); margin:0; }}

    .panel {{ border:1px solid var(--border); border-radius:12px; overflow:hidden; background:var(--surface); }}
    .panel-bar {{ display:flex; align-items:center; gap:8px; padding:12px 16px; background:var(--surface2); border-bottom:1px solid var(--border); }}
    .panel-title {{ font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); margin-left:8px; }}
    .panel-body {{ padding:16px; font-family:'JetBrains Mono',monospace; font-size:12px; line-height:1.7; color:var(--text2); overflow-y:auto; height:400px; }}
    .panel-body.tall {{ height:480px; }}
    .log-ok{{color:{T['accent']}}} .log-warn{{color:{T['warn']}}} .log-err{{color:{T['error']}}} .log-info{{color:{T['primary']}}}

    .banner {{ display:flex; align-items:center; gap:12px; padding:16px 24px; border:1px solid var(--border); border-radius:12px; background:var(--surface); margin-bottom:24px; }}
    .banner-text {{ font-size:14px; color:var(--text2); }}
    .banner-text strong {{ color:var(--text); }}
    .peer {{ display:inline-flex; align-items:center; gap:8px; padding:8px 12px; margin:4px 8px 4px 0; border-radius:8px; border:1px solid var(--border); background:var(--surface2); font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--text2); }}

    .gate {{ max-width:520px; margin:48px auto; padding:40px; background:var(--surface); border:1px solid var(--border); border-radius:16px; }}
    .gate-title {{ font-size:24px; font-weight:700; margin:0 0 8px; }}
    .gate-sub {{ color:var(--text2); font-size:14px; margin:0 0 24px; line-height:1.6; }}
    .gate-code {{ display:block; margin-top:16px; padding:12px 16px; background:var(--surface2); border:1px solid var(--border); border-radius:8px; font-family:'JetBrains Mono',monospace; font-size:12px; color:var(--primary); }}

    .warn-box {{ background:rgba(239,68,68,.06); border:1px solid rgba(239,68,68,.25); border-radius:12px; padding:16px 24px; margin-bottom:24px; }}
    .warn-title {{ font-size:12px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:{T['error']}; margin-bottom:8px; }}
    .warn-text {{ font-size:13px; color:var(--text2); line-height:1.6; }}

    .steps {{ display:flex; margin-bottom:32px; border:1px solid var(--border); border-radius:12px; overflow:hidden; background:var(--surface); }}
    .step {{ flex:1; text-align:center; padding:16px; border-right:1px solid var(--border); }}
    .step:last-child {{ border-right:none; }}
    .step.active {{ background:{T['primary_glow']}; }}
    .step.done {{ background:rgba(34,197,94,.05); }}
    .step-num {{ width:32px; height:32px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; font-weight:700; border:2px solid var(--border); margin-bottom:8px; }}
    .step.active .step-num {{ border-color:var(--primary); color:var(--primary); }}
    .step.done .step-num {{ border-color:var(--accent); background:var(--accent); color:#09090b; }}
    .step-lbl {{ font-size:11px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); }}

    .stButton>button {{ background:var(--surface2)!important; border:1px solid var(--border)!important; color:var(--text)!important; border-radius:8px!important; min-height:44px!important; font-weight:600!important; }}
    .stButton>button:hover {{ border-color:var(--primary)!important; color:var(--primary)!important; background:{T['primary_glow']}!important; }}
    [data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea {{ background:var(--surface2)!important; border:1px solid var(--border)!important; border-radius:8px!important; color:var(--text)!important; min-height:44px; }}
    div[data-testid="stProgressBar"]>div {{ background:var(--surface2)!important; height:6px!important; border-radius:4px!important; }}
    div[data-testid="stProgressBar"]>div>div {{ background:linear-gradient(90deg,{T['primary_dim']},{T['primary']})!important; border-radius:4px!important; }}
    </style>
    """, unsafe_allow_html=True)


def get_local_ip() -> str:
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"


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


def build_chart(values, height=160, title="CPU 60s"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(range(len(values))), y=list(values), fill="tozeroy", fillcolor="rgba(59,130,246,0.12)", line=dict(color=T["primary"], width=2), mode="lines"))
    fig.update_layout(height=height, title=dict(text=title, font=dict(size=11, color=T["muted"]), x=0), margin=dict(l=32, r=8, t=28, b=24), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=T["surface2"], xaxis=dict(visible=False), yaxis=dict(gridcolor="rgba(255,255,255,0.05)", range=[0, 100], ticksuffix="%"), showlegend=False)
    return fig


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


def render_header(title: str, subtitle: str, status: str = "", live: str = ""):
    status_html = f'<span class="pill pill-ok"><span class="dot"></span>{html.escape(status)}</span>' if status else ""
    live_html = f'<span class="pill pill-live"><span class="dot dot-pulse"></span>{html.escape(live)}</span>' if live else ""
    st.markdown(f"""
    <div class="shell-card"><div class="shell-row"><div>
    <div class="shell-eyebrow">Infrastructure Control Plane</div>
    <h1 class="shell-title">{html.escape(title)}</h1>
    <p class="shell-sub">{html.escape(subtitle)}</p></div>
    <div style="display:flex;flex-direction:column;gap:8px;align-items:flex-end">{status_html}{live_html}</div></div></div>
    """, unsafe_allow_html=True)


def render_key_gate(mode: str):
    st.markdown(f"""
    <div class="gate">
    <h2 class="gate-title">Configura chiave cluster</h2>
    <p class="gate-sub">La chiave non e piu nel codice sorgente. Usa la stessa password su Master e Worker.
    Minimo {MIN_KEY_LEN} caratteri.</p></div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        key = st.text_input("Chiave cluster", type="password", placeholder="Inserisci la tua chiave segreta")
        if st.button("Avvia " + mode.upper(), width="stretch"):
            if len(key.strip()) >= MIN_KEY_LEN:
                set_cluster_key(key.strip().encode("utf-8"))
                st.rerun()
            else:
                st.error(f"Chiave troppo corta (min {MIN_KEY_LEN} caratteri).")
        st.markdown(f"""
        <span class="gate-code">streamlit run main.py -- {mode} TUA_CHIAVE</span>
        <span class="gate-code">set HYDRA_SECRET=TUA_CHIAVE</span>
        """, unsafe_allow_html=True)
    st.stop()


def ensure_cluster_key(mode: str) -> bytes:
    if "cluster_key" not in st.session_state:
        argv_key = resolve_key_from_argv()
        env_key = resolve_key_from_env()
        if argv_key:
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
            self.events.appendleft(f"[{self._ts()}] Master attivo su :{TCP_PORT}")
        except Exception as e:
            self.events.appendleft(f"[{self._ts()}] ERRORE bind :{e}")

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


def render_node(nid, d):
    stats, meta = d["stats"], d.get("meta", {})
    cpu, ram, disk = float(stats.get("cpu", 0)), float(stats.get("ram", 0)), float(stats.get("disk", 0))
    with st.container(border=True):
        st.markdown(f"""<div class="node-top"><div class="node-left">
        <span class="tag tag-live">Online</span><span class="node-title">{html.escape(d['host'])}</span>
        <span class="tag">{html.escape(meta.get('os', '?'))}</span></div>
        <span class="tag">{html.escape(nid)}</span></div>""", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        for col, lbl, val in [(c1, "CPU", cpu), (c2, "RAM", ram), (c3, "Disco", disk)]:
            with col:
                st.markdown(f'<p class="kpi-label">{lbl}</p><p class="kpi-value primary">{val:.1f}%</p>', unsafe_allow_html=True)
                st.progress(min(val / 100, 1.0))
        with c4:
            st.markdown(f'<p class="kpi-label">Rete</p><p class="kpi-mono">{html.escape(d["ip"])}</p><p class="kpi-label" style="margin-top:8px">Threads</p><p class="kpi-value" style="font-size:18px">{stats.get("threads", 0)}</p>', unsafe_allow_html=True)
        if d["history"]:
            st.plotly_chart(build_chart(d["history"], title=d["host"]), width="stretch", key=f"c_{nid}")


@st.fragment(run_every=timedelta(seconds=REFRESH_SEC))
def live_master(m: HydraMaster):
    active, pending = m.get_active_nodes(), m.get_pending_peers()
    avg_cpu = round(sum(n["stats"].get("cpu", 0) for n in active.values()) / max(len(active), 1), 1)
    avg_ram = round(sum(n["stats"].get("ram", 0) for n in active.values()) / max(len(active), 1), 1)

    r = st.columns(5)
    r[0].metric("Nodi", len(active))
    r[1].metric("Peer UDP", len(pending))
    r[2].metric("CPU media", f"{avg_cpu}%")
    r[3].metric("RAM media", f"{avg_ram}%")
    r[4].metric("Uptime", m.uptime())

    st.markdown(f'<div class="banner"><span class="dot dot-pulse" style="background:{T["primary"]}"></span><div class="banner-text"><strong>Auto-discovery attivo</strong> — aggiornamento ogni {REFRESH_SEC}s via beacon UDP (no TCP scan)</div></div>', unsafe_allow_html=True)

    if pending:
        chips = "".join(f'<span class="peer"><span class="dot dot-pulse"></span>{html.escape(p["host"])} @ {html.escape(ip)}</span>' for ip, p in pending.items())
        st.markdown(f'<div class="section">Peer in rete</div>{chips}', unsafe_allow_html=True)

    t1, t2 = st.tabs(["Monitoraggio", "Terminal remoto"])
    with t1:
        left, right = st.columns([1.6, 1])
        with left:
            st.markdown('<div class="section">Topologia</div>', unsafe_allow_html=True)
            if not active:
                st.info("Nessun nodo connesso. Avvia worker con la stessa chiave cluster.")
            for nid, d in active.items():
                render_node(nid, d)
        with right:
            st.markdown('<div class="section">Eventi</div>', unsafe_allow_html=True)
            lines = [format_log_line(l) for l in list(m.events)] if m.events else ["In attesa..."]
            st.markdown(f'<div class="panel"><div class="panel-bar"><span class="panel-title">events.log</span></div><div class="panel-body">{"<br>".join(lines)}</div></div>', unsafe_allow_html=True)
    with t2:
        render_terminal(m, active)


def render_terminal(m: HydraMaster, active: dict):
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
    cmd = st.text_area("Comando", placeholder="whoami / hostname / dir / ls -la", height=80)
    if st.button("Esegui", width="stretch") and cmd.strip():
        m.send_command_all(cmd.strip()) if target == "Tutti" else m.send_command(opts[target], cmd.strip())
    entries = m.get_terminal_log()
    body = "".join(f'<span class="log-info">[{html.escape(e["ts"])}] {html.escape(e["host"])} $ {html.escape(e["command"])}</span><br><span class="log-ok">{html.escape(e.get("stdout",""))}</span><br><span class="log-err">{html.escape(e.get("stderr",""))}</span><br><br>' for e in entries) if entries else "Nessun output."
    st.markdown(f'<div class="panel"><div class="panel-bar"><span class="panel-title">remote.shell</span></div><div class="panel-body tall">{body}</div></div>', unsafe_allow_html=True)


def render_master(m: HydraMaster):
    render_header("HYDRA OVERLORD", f"{VERSION} / TCP {TCP_PORT} / UDP {UDP_PORT}", "ACTIVE", f"Live {REFRESH_SEC}s")
    if not m._socket_ok:
        st.error(f"Porta {TCP_PORT} occupata.")
        return
    live_master(m)


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
    with st.sidebar:
        st.markdown(f"**{CODENAME}** `{VERSION}`")
        st.caption(f"Mode: {mode.upper()}")
        st.code(f"streamlit run main.py -- {mode} CHIAVE", language="bash")
        st.caption("Chiave caricata. Stessa chiave su tutti i nodi.")
    if mode == "master":
        if "master" not in st.session_state or st.session_state.get("master_key") != key:
            if "master" in st.session_state:
                st.session_state.master.shutdown()
            master = HydraMaster(key)
            master.launch()
            st.session_state.master = master
            st.session_state.master_key = key
            atexit.register(master.shutdown)
        render_master(st.session_state.master)
    elif mode == "worker":
        render_worker(key)
    else:
        st.error("Usa: master o worker")


if __name__ == "__main__":
    main()
