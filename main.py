import sys, time, json, uuid, socket, threading, hashlib, hmac
import psutil
import streamlit as st
import plotly.graph_objects as go
import zmq
from datetime import datetime
from collections import deque

# --- CORE SYSTEM SETTINGS ---
VERSION = "V2.2.0"
CODENAME = "HYDRA"
SECRET_KEY = b"HYDRA_SINGULARITY_ENCRYPT_2026"
TCP_PORT = 5555
UDP_PORT = 5556
BT_SSID = "HYDRA_COMMAND_CENTER"
NODE_TIMEOUT_SEC = 10
REFRESH_MS = 2000

NEON = "#00ff88"
NEON_DIM = "#00cc6a"
BG = "#030303"
PANEL = "#0a0a0a"
BORDER = "#1e1e1e"
TEXT = "#e8e8e8"
MUTED = "#666"
WARN = "#ff6b35"
ERROR = "#ff3366"


def apply_styles():
    st.set_page_config(
        page_title=f"{CODENAME} {VERSION}",
        page_icon="🐉",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&family=Space+Grotesk:wght@400;500;700&display=swap');

        :root {{
            --neon: {NEON};
            --neon-dim: {NEON_DIM};
            --bg: {BG};
            --panel: {PANEL};
            --border: {BORDER};
            --text: {TEXT};
            --muted: {MUTED};
        }}

        html, body, [class*="css"] {{
            background-color: var(--bg) !important;
            color: var(--text);
            font-family: 'Space Grotesk', sans-serif;
        }}

        #MainMenu, footer, header {{ visibility: hidden; }}

        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #0d0d0d 0%, #050505 100%);
            border-right: 1px solid var(--border);
        }}
        [data-testid="stSidebar"] .block-container {{ padding-top: 2rem; }}

        .hero {{
            background: linear-gradient(135deg, #0a0a0a 0%, #111 50%, #0a0a0a 100%);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 2rem 2.5rem;
            margin-bottom: 1.5rem;
            position: relative;
            overflow: hidden;
        }}
        .hero::before {{
            content: '';
            position: absolute;
            top: -50%; right: -20%;
            width: 400px; height: 400px;
            background: radial-gradient(circle, rgba(0,255,136,0.08) 0%, transparent 70%);
            pointer-events: none;
        }}
        .hero-title {{
            font-size: 2.8rem;
            font-weight: 700;
            letter-spacing: -2px;
            color: white;
            margin: 0;
            line-height: 1.1;
        }}
        .hero-sub {{
            color: var(--neon);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            letter-spacing: 4px;
            text-transform: uppercase;
            margin-top: 0.5rem;
        }}
        .hero-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(0,255,136,0.1);
            border: 1px solid var(--neon);
            color: var(--neon);
            padding: 6px 14px;
            border-radius: 50px;
            font-size: 0.7rem;
            font-weight: 600;
            letter-spacing: 1px;
            margin-top: 1rem;
        }}
        .pulse-dot {{
            width: 8px; height: 8px;
            background: var(--neon);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; box-shadow: 0 0 0 0 rgba(0,255,136,0.5); }}
            50% {{ opacity: 0.7; box-shadow: 0 0 0 8px rgba(0,255,136,0); }}
        }}

        [data-testid="stMetric"] {{
            background: linear-gradient(160deg, #0f0f0f, #080808);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 1.25rem !important;
            transition: border-color 0.3s, transform 0.2s;
        }}
        [data-testid="stMetric"]:hover {{
            border-color: rgba(0,255,136,0.3);
            transform: translateY(-2px);
        }}
        [data-testid="stMetricLabel"] {{
            color: var(--muted) !important;
            font-size: 0.7rem !important;
            letter-spacing: 2px;
            text-transform: uppercase;
        }}
        [data-testid="stMetricValue"] {{
            color: white !important;
            font-weight: 700 !important;
        }}

        .node-card {{
            background: linear-gradient(160deg, #0f0f0f 0%, #080808 100%);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            transition: border-color 0.3s, box-shadow 0.3s;
        }}
        .node-card:hover {{
            border-color: rgba(0,255,136,0.25);
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        }}
        .node-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.25rem;
        }}
        .node-host {{
            font-size: 1.1rem;
            font-weight: 600;
            color: white;
        }}
        .node-id {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.65rem;
            color: var(--muted);
            background: #111;
            padding: 4px 10px;
            border-radius: 6px;
        }}
        .status-pill {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(0,255,136,0.12);
            color: var(--neon);
            padding: 4px 12px;
            border-radius: 50px;
            font-size: 0.65rem;
            font-weight: 700;
            letter-spacing: 1px;
            border: 1px solid rgba(0,255,136,0.3);
            margin-right: 10px;
        }}
        .status-pill .dot {{
            width: 6px; height: 6px;
            background: var(--neon);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }}

        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1rem;
        }}
        .metric-item {{ text-align: center; }}
        .metric-label {{
            font-size: 0.65rem;
            color: var(--muted);
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-bottom: 4px;
        }}
        .metric-value {{
            font-size: 1.6rem;
            font-weight: 700;
            color: var(--neon);
            line-height: 1;
        }}
        .metric-bar {{
            height: 4px;
            background: #1a1a1a;
            border-radius: 2px;
            margin-top: 8px;
            overflow: hidden;
        }}
        .metric-bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--neon-dim), var(--neon));
            border-radius: 2px;
            transition: width 0.5s ease;
        }}

        .log-terminal {{
            background: #000;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            line-height: 1.7;
            height: 420px;
            overflow-y: auto;
            white-space: pre-wrap;
        }}
        .log-terminal::-webkit-scrollbar {{ width: 6px; }}
        .log-terminal::-webkit-scrollbar-thumb {{
            background: var(--border);
            border-radius: 3px;
        }}
        .log-ok {{ color: var(--neon); }}
        .log-warn {{ color: {WARN}; }}
        .log-err {{ color: {ERROR}; }}
        .log-muted {{ color: var(--muted); }}

        .section-title {{
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 3px;
            text-transform: uppercase;
            color: var(--muted);
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
        }}

        .empty-state {{
            text-align: center;
            padding: 3rem 2rem;
            border: 1px dashed var(--border);
            border-radius: 14px;
            color: var(--muted);
        }}
        .empty-icon {{
            font-size: 3rem;
            margin-bottom: 1rem;
            opacity: 0.4;
        }}

        .step-track {{
            display: flex;
            gap: 0;
            margin-bottom: 2rem;
        }}
        .step-item {{
            flex: 1;
            text-align: center;
            padding: 1rem;
            position: relative;
        }}
        .step-num {{
            width: 36px; height: 36px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.85rem;
            margin-bottom: 0.5rem;
            border: 2px solid var(--border);
            color: var(--muted);
            transition: all 0.3s;
        }}
        .step-item.active .step-num {{
            border-color: var(--neon);
            background: rgba(0,255,136,0.15);
            color: var(--neon);
            box-shadow: 0 0 20px rgba(0,255,136,0.2);
        }}
        .step-item.done .step-num {{
            border-color: var(--neon);
            background: var(--neon);
            color: #000;
        }}
        .step-label {{
            font-size: 0.7rem;
            letter-spacing: 2px;
            text-transform: uppercase;
            color: var(--muted);
        }}
        .step-item.active .step-label {{ color: var(--neon); }}

        .link-banner {{
            background: linear-gradient(90deg, rgba(0,255,136,0.1), rgba(0,255,136,0.03));
            border: 1px solid rgba(0,255,136,0.3);
            border-radius: 12px;
            padding: 1rem 1.5rem;
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 1.5rem;
        }}
        .link-banner .icon {{ font-size: 1.5rem; }}
        .link-banner .text {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            color: var(--neon);
        }}

        .stButton>button {{
            background: transparent !important;
            border: 1px solid var(--neon) !important;
            color: var(--neon) !important;
            font-weight: 600 !important;
            border-radius: 10px !important;
            height: 3rem !important;
            letter-spacing: 1px !important;
            transition: all 0.3s !important;
        }}
        .stButton>button:hover {{
            background: var(--neon) !important;
            color: #000 !important;
            box-shadow: 0 0 24px rgba(0,255,136,0.4) !important;
        }}

        .sidebar-brand {{
            font-size: 1.4rem;
            font-weight: 700;
            color: white;
            margin-bottom: 0.25rem;
        }}
        .sidebar-version {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.65rem;
            color: var(--neon);
            letter-spacing: 2px;
        }}
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


def build_chart(values, height=140, show_axes=False):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=values,
        fill="tozeroy",
        fillcolor="rgba(0,255,136,0.12)",
        line=dict(color=NEON, width=2, shape="spline"),
        mode="lines",
    ))
    layout = dict(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(
            visible=show_axes,
            gridcolor="#1a1a1a",
            tickfont=dict(color=MUTED, size=10),
            range=[0, 100] if show_axes else None,
        ),
        showlegend=False,
    )
    fig.update_layout(**layout)
    return fig


def render_metric_bar(label, value, unit="%"):
    pct = min(max(float(value), 0), 100)
    return f"""
        <div class="metric-item">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}{unit}</div>
            <div class="metric-bar">
                <div class="metric-bar-fill" style="width:{pct}%"></div>
            </div>
        </div>
    """


def format_log_line(line: str) -> str:
    if "ERRORE" in line or "INVALIDA" in line or "negato" in line.lower():
        return f'<span class="log-err">{line}</span>'
    if "HANDSHAKE" in line or "OK" in line:
        return f'<span class="log-ok">{line}</span>'
    if "WARN" in line:
        return f'<span class="log-warn">{line}</span>'
    return f'<span class="log-muted">{line}</span>'


def inject_refresh():
    st.markdown(
        f"<script>setTimeout(function(){{ window.location.reload(); }}, {REFRESH_MS});</script>",
        unsafe_allow_html=True,
    )


def render_sidebar(mode: str):
    with st.sidebar:
        st.markdown(
            f"<div class='sidebar-brand'>{CODENAME}</div>"
            f"<div class='sidebar-version'>{VERSION} · {mode.upper()}</div>",
            unsafe_allow_html=True,
        )
        st.divider()
        st.markdown("**Porte di rete**")
        st.code(f"TCP  {TCP_PORT}  (dati)\nUDP  {UDP_PORT}  (beacon)", language=None)
        st.markdown("**Sicurezza**")
        st.caption("HMAC-SHA256 · timing-safe verify")
        st.divider()
        st.markdown("**Comandi**")
        st.code("streamlit run main.py -- master", language="bash")
        st.code("streamlit run main.py -- worker", language="bash")


class HydraMaster:
    def __init__(self):
        self.nodes = {}
        self.events = deque(maxlen=200)
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
                    if verify_signature(payload, sig):
                        self._sync_node(identity, json.loads(payload.decode("utf-8")))
                    else:
                        self.events.appendleft(f"[{self._ts()}] FIRMA INVALIDA — pacchetto scartato")
            except zmq.Again:
                pass
            except Exception as e:
                self.events.appendleft(f"[{self._ts()}] Errore collector: {e}")

    def _sync_node(self, identity, data):
        nid = data.get("id", "UNKNOWN")
        with self.lock:
            is_new = nid not in self.nodes
            self.nodes[nid] = {
                "host": data.get("host", "?"),
                "ip": data.get("ip", "?"),
                "stats": data.get("s", {}),
                "history": data.get("h", []),
                "last": time.time(),
            }
            if is_new:
                self.events.appendleft(
                    f"[{self._ts()}] HANDSHAKE OK: {data.get('host', '?')} ({nid}) @ {data.get('ip', '?')}"
                )

    def get_active_nodes(self):
        now = time.time()
        with self.lock:
            return {k: v for k, v in self.nodes.items() if now - v["last"] < NODE_TIMEOUT_SEC}

    def uptime(self) -> str:
        delta = datetime.now() - self.started_at
        h, rem = divmod(int(delta.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"


class HydraWorker:
    def __init__(self, target_ip):
        self.id = f"HYDRA-NODE-{uuid.uuid4().hex[:6].upper()}"
        self.target = target_ip
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.DEALER)
        self.sock.setsockopt(zmq.LINGER, 0)
        self.sock.setsockopt_string(zmq.IDENTITY, self.id)
        self.cpu_history = deque([0] * 60, maxlen=60)
        self.connected = False
        self.error_msg = ""
        self.last_stats = {"cpu": 0, "ram": 0, "disk": 0, "threads": 0}

    def engage_link(self) -> bool:
        try:
            self.sock.connect(f"tcp://{self.target}:{TCP_PORT}")
            self.connected = True
            threading.Thread(target=self._telemetry_stream, daemon=True).start()
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

    def _telemetry_stream(self):
        psutil.cpu_percent(interval=None)
        while self.connected:
            try:
                stats = {
                    "cpu": psutil.cpu_percent(interval=None),
                    "ram": psutil.virtual_memory().percent,
                    "disk": psutil.disk_usage("/").percent if sys.platform != "win32" else psutil.disk_usage("C:\\").percent,
                    "threads": threading.active_count(),
                }
                self.last_stats = stats
                self.cpu_history.append(stats["cpu"])
                payload_obj = {
                    "id": self.id,
                    "host": socket.gethostname(),
                    "ip": get_local_ip(),
                    "s": stats,
                    "h": list(self.cpu_history),
                }
                raw_data = json.dumps(payload_obj).encode("utf-8")
                self.sock.send_multipart([b"", raw_data, make_signature(raw_data)])
            except zmq.ZMQError:
                self.connected = False
                break
            except Exception:
                pass
            time.sleep(1)


def render_hero(title: str, subtitle: str, badge: str = ""):
    badge_html = f"<div class='hero-badge'><span class='pulse-dot'></span>{badge}</div>" if badge else ""
    st.markdown(f"""
        <div class="hero">
            <div class="hero-title">{title}</div>
            <div class="hero-sub">{subtitle}</div>
            {badge_html}
        </div>
    """, unsafe_allow_html=True)


def render_master(m: HydraMaster):
    render_hero(
        "HYDRA OVERLORD",
        f"{VERSION} · TCP:{TCP_PORT} · UDP:{UDP_PORT}",
        "SISTEMA ATTIVO",
    )

    if not m._socket_ok:
        st.error(f"Impossibile aprire la porta {TCP_PORT}. Chiudi altri processi e riavvia.")
        return

    active = m.get_active_nodes()
    avg_cpu = round(sum(n["stats"].get("cpu", 0) for n in active.values()) / max(len(active), 1), 1)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("NODI ONLINE", len(active))
    c2.metric("CPU MEDIA", f"{avg_cpu}%")
    c3.metric("UPTIME", m.uptime())
    c4.metric("CRITTOGRAFIA", "HMAC-256")
    c5.metric("BEACON UDP", "ON")

    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown("<div class='section-title'>Topologia Nodi</div>", unsafe_allow_html=True)
        if not active:
            st.markdown("""
                <div class="empty-state">
                    <div class="empty-icon">📡</div>
                    <div><b>Nessun worker connesso</b></div>
                    <div style="margin-top:8px;font-size:0.85rem;">
                        Avvia un worker con<br>
                        <code>streamlit run main.py -- worker</code>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        for nid, d in active.items():
            stats = d["stats"]
            st.markdown(f"""
                <div class="node-card">
                    <div class="node-header">
                        <div>
                            <span class="status-pill"><span class="dot"></span>ONLINE</span>
                            <span class="node-host">{d['host']}</span>
                        </div>
                        <span class="node-id">{nid}</span>
                    </div>
                    <div class="metric-grid">
                        {render_metric_bar("CPU", stats.get('cpu', 0))}
                        {render_metric_bar("RAM", stats.get('ram', 0))}
                        {render_metric_bar("DISCO", stats.get('disk', 0))}
                        <div class="metric-item">
                            <div class="metric-label">IP · THREADS</div>
                            <div class="metric-value" style="font-size:1rem;color:white;">{d['ip']}</div>
                            <div style="color:var(--neon);font-size:0.85rem;margin-top:4px;">{stats.get('threads', 0)} thread</div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            if d["history"]:
                st.plotly_chart(build_chart(d["history"]), use_container_width=True, key=f"chart_{nid}")

    with col_right:
        st.markdown("<div class='section-title'>Log Eventi</div>", unsafe_allow_html=True)
        lines = [format_log_line(l) for l in list(m.events)] if m.events else ['<span class="log-muted">In attesa di segnali...</span>']
        st.markdown(f"<div class='log-terminal'>{'<br>'.join(lines)}</div>", unsafe_allow_html=True)
        if st.button("Aggiorna ora", key="refresh_log"):
            st.rerun()

    inject_refresh()


def render_stepper(current: int):
    steps = [("1", "Scoperta"), ("2", "Autenticazione"), ("3", "Streaming")]
    html = '<div class="step-track">'
    for i, (num, label) in enumerate(steps, 1):
        cls = "done" if i < current else ("active" if i == current else "")
        html += f'<div class="step-item {cls}"><div class="step-num">{num}</div><div class="step-label">{label}</div></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_worker():
    render_hero("HYDRA WORKER", f"MODULO TELEMETRIA · {VERSION}", "CLIENT NODE")

    if "step" not in st.session_state:
        st.session_state.step = 1

    render_stepper(st.session_state.step)

    if st.session_state.step == 1:
        st.markdown("<div class='section-title'>Trova il Master Controller</div>", unsafe_allow_html=True)
        method = st.radio(
            "Metodo di scoperta",
            ["Automatico (Beacon + Localhost)", "Scansione subnet", "IP manuale"],
            horizontal=True,
        )
        static_ip = ""
        if method == "IP manuale":
            static_ip = st.text_input("Indirizzo IP del Master", placeholder="192.168.1.100")

        if st.button("Avvia scoperta", use_container_width=True):
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
                    st.error("Master non trovato. Avvia prima il nodo Master sulla stessa rete.")

            elif method == "Scansione subnet":
                found = False
                with st.spinner("Scansione subnet in corso (può richiedere ~30s)..."):
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
                        st.error(f"Errore scansione: {e}")
                if found:
                    st.session_state.step = 2
                    st.rerun()
                else:
                    st.error("Nessun Master trovato sulla subnet locale.")

            elif method == "IP manuale":
                if static_ip.strip():
                    st.session_state.target_ip = static_ip.strip()
                    st.session_state.step = 2
                    st.rerun()
                else:
                    st.error("Inserisci un indirizzo IP valido.")

    elif st.session_state.step == 2:
        st.success(f"Master individuato: **{st.session_state.target_ip}**")
        st.markdown("<div class='section-title'>Autenticazione Cluster</div>", unsafe_allow_html=True)
        st.caption("Inserisci la chiave condivisa configurata sul Master (default nel codice sorgente).")
        key_in = st.text_input("Chiave di accesso", type="password", placeholder="••••••••••••••••")

        col_auth, col_back = st.columns([3, 1])
        with col_auth:
            if st.button("Autorizza tunnel sicuro", use_container_width=True):
                if key_in.encode() == SECRET_KEY:
                    worker = HydraWorker(st.session_state.target_ip)
                    if worker.engage_link():
                        st.session_state.worker = worker
                        st.session_state.step = 3
                        st.rerun()
                    else:
                        st.error(f"Connessione ZMQ fallita: {worker.error_msg}")
                else:
                    st.error("Chiave non valida. Accesso negato.")
        with col_back:
            if st.button("Indietro"):
                st.session_state.step = 1
                st.rerun()

    elif st.session_state.step == 3:
        w: HydraWorker = st.session_state.worker

        if not w.connected:
            st.error("Connessione persa con il Master.")
            if st.button("Riconnetti"):
                st.session_state.step = 1
                del st.session_state.worker
                st.rerun()
            return

        st.markdown(f"""
            <div class="link-banner">
                <span class="icon">🔗</span>
                <span class="text">LINK SICURO ATTIVO → {st.session_state.target_ip}</span>
            </div>
        """, unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)
        s = w.last_stats
        m1.metric("CPU", f"{s['cpu']}%")
        m2.metric("RAM", f"{s['ram']}%")
        m3.metric("DISCO", f"{s['disk']}%")
        m4.metric("ID NODO", w.id)

        st.plotly_chart(build_chart(list(w.cpu_history), height=380, show_axes=True), use_container_width=True)
        st.caption("Grafico CPU — ultimi 60 secondi")

        if st.button("Termina connessione", use_container_width=True):
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
            st.session_state.master = HydraMaster()
            st.session_state.master.launch()
        render_master(st.session_state.master)
    elif mode == "worker":
        render_worker()
    else:
        st.error(f"Modalità non valida: '{mode}'. Usa 'master' o 'worker'.")


if __name__ == "__main__":
    main()
