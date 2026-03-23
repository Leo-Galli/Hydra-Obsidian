import os
import sys
import time
import json
import uuid
import socket
import threading
import hashlib
import hmac
import psutil
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import zmq
import subprocess
from datetime import datetime
from collections import deque

# --- CONFIGURAZIONE ELITE V19 ---
PROJ_ID = "HYDRA_OVERLORD_V19"
TCP_PORT = 5555
UDP_PORT = 5556
SECRET_KEY = b"HYDRA_V19_ULTRA_SECRET"
MAX_LOGS = 150

# --- STILI CSS "DEEP OBSIDIAN" ---
def apply_elite_styles():
    st.set_page_config(page_title=PROJ_ID, layout="wide", initial_sidebar_state="expanded")
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;700&family=Inter:wght@300;400;900&display=swap');
        
        :root { --neon: #00ff88; --bg: #030303; --card: #0a0a0a; }
        
        html, body, [class*="css"] { 
            background-color: var(--bg); 
            color: #ffffff; 
            font-family: 'Inter', sans-serif;
        }
        
        .stMetric { 
            background: var(--card); 
            border: 1px solid #1a1a1a; 
            border-radius: 10px; 
            padding: 20px !important;
            box-shadow: 0 4px 10px rgba(0,0,0,0.5);
        }
        
        .main-title {
            font-size: 4.5rem;
            font-weight: 900;
            letter-spacing: -5px;
            background: linear-gradient(180deg, #fff 0%, #444 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0;
        }

        .console-box {
            background: #000;
            border: 1px solid #222;
            padding: 15px;
            border-radius: 5px;
            font-family: 'Fira Code', monospace;
            font-size: 12px;
            color: var(--neon);
            height: 200px;
            overflow-y: scroll;
            margin-bottom: 20px;
        }

        .node-card-active {
            background: linear-gradient(145deg, #0d0d0d, #050505);
            border-left: 5px solid var(--neon);
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 20px;
            border-right: 1px solid #1a1a1a;
            border-top: 1px solid #1a1a1a;
            border-bottom: 1px solid #1a1a1a;
        }

        .status-pulse {
            height: 12px; width: 12px; background: var(--neon);
            border-radius: 50%; display: inline-block;
            box-shadow: 0 0 15px var(--neon);
            animation: pulse 2s infinite;
        }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }
        
        .stButton>button {
            width: 100%;
            background: #111;
            border: 1px solid var(--neon);
            color: var(--neon);
            font-weight: bold;
            height: 50px;
            transition: 0.3s;
        }
        .stButton>button:hover { background: var(--neon); color: #000; box-shadow: 0 0 20px var(--neon); }
        </style>
    """, unsafe_allow_html=True)

# --- CORE LOGIC: MASTER ---
class HydraMaster:
    def __init__(self):
        self.nodes = {}
        self.raw_logs = deque(maxlen=MAX_LOGS)
        self.debug_stream = deque(maxlen=20)
        self.lock = threading.Lock()
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(zmq.ROUTER)
        self.socket.setsockopt(zmq.RCVTIMEO, 1000)
        self.socket.bind(f"tcp://0.0.0.0:{TCP_PORT}")
        self.start_time = time.time()

    def add_debug(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.debug_stream.appendleft(f"[{ts}] {msg}")

    def run_engine(self):
        # UDP Beacon per farsi trovare dai client
        threading.Thread(target=self._udp_beacon, daemon=True).start()
        # Thread ricezione ZMQ
        threading.Thread(target=self._recv_worker, daemon=True).start()

    def _udp_beacon(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.add_debug("UDP Beacon iniziato sulla porta 5556")
        while True:
            try:
                # Recupera tutti gli IP locali per gridare su ogni rete
                for interface, addrs in psutil.net_if_addrs().items():
                    for addr in addrs:
                        if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                            msg = f"HYDRA_V19_BEACON|{addr.address}".encode()
                            sock.sendto(msg, ('<broadcast>', UDP_PORT))
            except: pass
            time.sleep(2)

    def _recv_worker(self):
        self.add_debug(f"ZMQ ROUTER pronto sulla porta {TCP_PORT}")
        while True:
            try:
                parts = self.socket.recv_multipart()
                if len(parts) < 4: continue
                
                identity, _, payload, sig = parts
                # Validazione HMAC
                calc_sig = hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest().encode()
                if sig == calc_sig:
                    data = json.loads(payload.decode())
                    self._process_node_data(identity, data)
                else:
                    self.add_debug(f"Rifiutato pacchetto da {identity.decode()}: Firma non valida")
            except zmq.Again: pass
            except Exception as e: self.add_debug(f"Errore Recv: {str(e)}")

    def _process_node_data(self, identity, data):
        nid = data['id']
        with self.lock:
            # Se è un nuovo nodo, logga
            if nid not in self.nodes:
                self.add_debug(f"NUOVO NODO RILEVATO: {nid}")
            
            self.nodes[nid] = {
                'id_zmq': identity,
                'hostname': data.get('host', 'N/A'),
                'stats': data['s'],
                'history': data['h'],
                'last': time.time(),
                'ip': data.get('ip', 'Unknown')
            }
            self.raw_logs.appendleft({
                'Time': datetime.now().strftime("%H:%M:%S"),
                'Node': nid,
                'CPU': f"{data['s']['cpu']}%",
                'RAM': f"{data['s']['ram']}%",
                'IO_Disk': f"{data['s'].get('disk', 0)}%"
            })

# --- CORE LOGIC: WORKER ---
class HydraWorker:
    def __init__(self, target_ip):
        self.id = f"HYDRA-NODE-{socket.gethostname()}-{uuid.uuid4().hex[:4].upper()}"
        self.master_ip = target_ip
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.DEALER)
        self.sock.setsockopt_string(zmq.IDENTITY, self.id)
        self.history = deque([0]*50, maxlen=50)
        self.connected = False

    def start_sync(self):
        try:
            self.sock.connect(f"tcp://{self.master_ip}:{TCP_PORT}")
            self.connected = True
            threading.Thread(target=self._loop, daemon=True).start()
            return True
        except: return False

    def _loop(self):
        while True:
            # Telemetria Avanzata
            stats = {
                'cpu': psutil.cpu_percent(),
                'ram': psutil.virtual_memory().percent,
                'disk': psutil.disk_usage('/').percent,
                'net_sent': psutil.net_io_counters().bytes_sent
            }
            self.history.append(stats['cpu'])
            
            payload = {
                'id': self.id,
                'host': socket.gethostname(),
                'ip': socket.gethostbyname(socket.gethostname()),
                's': stats,
                'h': list(self.history)
            }
            
            msg = json.dumps(payload).encode()
            sig = hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest().encode()
            
            try:
                self.sock.send_multipart([b"", msg, sig])
            except: self.connected = False
            time.sleep(1)

# --- DASHBOARD UI ---
def main():
    apply_elite_styles()
    
    if len(sys.argv) < 2:
        st.error("Lancio: streamlit run file.py [master/worker]")
        return

    role = sys.argv[1].lower()

    if role == "master":
        # Inizializzazione Master
        if 'master_obj' not in st.session_state:
            st.session_state.master_obj = HydraMaster()
            st.session_state.master_obj.run_engine()
        
        m = st.session_state.master_obj

        st.markdown(f"<h1 class='main-title'>HYDRA <span style='color:var(--neon)'>OVERLORD</span></h1>", unsafe_allow_html=True)
        st.write(f"**SERVER STATUS:** ONLINE | **PORT:** {TCP_PORT} | **ID:** {PROJ_ID}")
        
        # Sidebar Control
        with st.sidebar:
            st.header("⚡ SYSTEM CONTROL")
            if st.button("🛰️ CREATE WIFI AP (ADMIN)"):
                res = subprocess.run(f'netsh wlan set hostednetwork mode=allow ssid=HYDRA_V19 key=obsidian123', shell=True, capture_output=True)
                subprocess.run('netsh wlan start hostednetwork', shell=True)
                st.write(res.stdout.decode())
            st.info("Se non appare nulla, assicurati che il Client abbia l'IP corretto del Master.")

        # Top Bar Metrics
        c1, c2, c3, c4 = st.columns(4)
        with m.lock:
            n_nodes = len(m.nodes)
            m_logs = len(m.raw_logs)
            c1.metric("NODES ONLINE", n_nodes)
            c2.metric("TOTAL PKTS", m_logs)
            c3.metric("UPTIME", f"{int(time.time() - m.start_time)}s")
            c4.metric("SECURITY", "HMAC-SHA256")

        # Live Debug Console
        st.write("### 🖥️ SYSTEM DEBUG CONSOLE")
        debug_txt = "\n".join(list(m.debug_stream))
        st.markdown(f"<div class='console-box'>{debug_txt}</div>", unsafe_allow_html=True)

        # Node Monitoring
        st.write("### 🛰️ CONNECTED NEURAL NODES")
        if n_nodes == 0:
            st.warning("NESSUN NODO RILEVATO. In attesa di segnale...")
        else:
            with m.lock:
                node_list = list(m.nodes.items())
            for i in range(0, len(node_list), 2):
                cols = st.columns(2)
                for j in range(2):
                    if i+j < len(node_list):
                        nid, data = node_list[i+j]
                        with cols[j]:
                            st.markdown(f"""
                                <div class='node-card-active'>
                                    <div class='status-pulse'></div> <b style='font-size:20px;'>{data['hostname']}</b><br>
                                    <small style='color:#666;'>UID: {nid} | IP: {data['ip']}</small>
                                    <div style='margin-top:15px;'>
                                        <b>CPU: {data['stats']['cpu']}%</b> | 
                                        RAM: {data['stats']['ram']}% | 
                                        DISK: {data['stats']['disk']}%
                                    </div>
                                </div>
                            """, unsafe_allow_html=True)
                            fig = go.Figure(go.Scatter(y=data['history'], fill='tozeroy', line=dict(color='#00ff88', width=3)))
                            fig.update_layout(height=120, margin=dict(l=0,r=0,t=0,b=0), xaxis_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                            st.plotly_chart(fig, use_container_width=True, key=nid)

        st.write("### 📜 DATA STREAM")
        st.dataframe(pd.DataFrame(list(m.raw_logs)), use_container_width=True)

    elif role == "worker":
        st.markdown(f"<h1 class='main-title'>HYDRA <span style='color:var(--neon)'>WORKER</span></h1>", unsafe_allow_html=True)
        
        if 'worker_obj' not in st.session_state:
            st.subheader("📡 Handshake Iniziale")
            
            # Scansione automatica
            if st.button("🔍 SCAN RETE PER MASTER"):
                with st.spinner("Ascolto Beacon..."):
                    scanner = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    scanner.bind(('', UDP_PORT))
                    scanner.settimeout(5.0)
                    try:
                        data, addr = scanner.recvfrom(1024)
                        if "HYDRA_V19_BEACON" in data.decode():
                            st.session_state.found_ip = data.decode().split("|")[1]
                            st.success(f"Master trovato a: {st.session_state.found_ip}")
                    except: st.error("Nessun Master trovato. Inserisci IP manualmente.")
                    finally: scanner.close()

            target = st.text_input("MASTER IP:", st.session_state.get('found_ip', ''))
            if st.button("🚀 INFILTRATE MESH"):
                w = HydraWorker(target)
                if w.start_sync():
                    st.session_state.worker_obj = w
                    st.rerun()
        else:
            w = st.session_state.worker_obj
            st.metric("CONNECTION STATUS", "ESTABLISHED" if w.connected else "LOST")
            st.write(f"**NODE ID:** `{w.id}`")
            st.write(f"**MASTER TARGET:** `{w.master_ip}`")
            
            fig = go.Figure(go.Scatter(y=list(w.history), fill='tozeroy', line=dict(color='#00ff88', width=4)))
            fig.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
            
            if st.button("🔌 DISCONNECT"):
                del st.session_state.worker_obj
                st.rerun()

    time.sleep(1)
    st.rerun()

if __name__ == "__main__":
    main()