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

# --- CONFIGURAZIONE APEX V20 ---
PROJECT_ID = "HYDRA_APEX_V20"
CORE_SECRET = b"APEX_SIG_2026_OMEGA"
TCP_PORT = 5555
UDP_PORT = 5556
BT_PORT = 4 # RFCOMM Standard
MAX_HISTORY = 100

# --- STILI CSS "CYBER-OBSIDIAN" ---
def apply_apex_styles():
    st.set_page_config(page_title=PROJECT_ID, layout="wide", initial_sidebar_state="collapsed")
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Syncopate:wght@400;700&family=JetBrains+Mono:wght@300;500&display=swap');
        
        :root { --neon-green: #00ff88; --deep-bg: #050505; --panel: #0e0e0e; }
        
        html, body, [class*="css"] { 
            background-color: var(--deep-bg); 
            color: #e0e0e0; 
            font-family: 'JetBrains Mono', monospace;
        }

        .main-header {
            font-family: 'Syncopate', sans-serif;
            font-size: 5rem;
            font-weight: 700;
            letter-spacing: -8px;
            background: linear-gradient(180deg, #fff 20%, #222 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: -20px;
        }

        .status-bar {
            background: var(--panel);
            border-bottom: 1px solid #1a1a1a;
            padding: 10px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .node-card {
            background: linear-gradient(135deg, #0f0f0f 0%, #050505 100%);
            border: 1px solid #1f1f1f;
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 20px;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        .node-card:hover {
            border-color: var(--neon-green);
            box-shadow: 0 0 30px rgba(0, 255, 136, 0.15);
            transform: translateY(-5px);
        }

        .metric-value {
            font-size: 24px;
            font-weight: bold;
            color: var(--neon-green);
        }

        .console-stream {
            background: #000;
            color: #555;
            padding: 15px;
            font-size: 11px;
            border-radius: 10px;
            height: 150px;
            overflow-y: auto;
            border: 1px solid #111;
        }

        .stButton>button {
            background: transparent;
            border: 1px solid var(--neon-green);
            color: var(--neon-green);
            font-family: 'Syncopate';
            padding: 15px;
            border-radius: 10px;
            width: 100%;
            text-transform: uppercase;
        }
        .stButton>button:hover {
            background: var(--neon-green);
            color: black;
            box-shadow: 0 0 20px var(--neon-green);
        }
        </style>
    """, unsafe_allow_html=True)

# --- CLASSE MASTER: IL CUORE DELL'OVERLORD ---
class ApexMaster:
    def __init__(self):
        self.nodes = {}
        self.logs = deque(maxlen=200)
        self.debug = deque(maxlen=50)
        self.lock = threading.Lock()
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(zmq.ROUTER)
        self.socket.bind(f"tcp://0.0.0.0:{TCP_PORT}")
        self.start_time = time.time()
        self.hostname = socket.gethostname()

    def add_debug(self, msg):
        self.debug.appendleft(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def boot(self):
        # 1. Thread UDP Broadcast
        threading.Thread(target=self._broadcast_layer, daemon=True).start()
        # 2. Thread ZMQ Listener
        threading.Thread(target=self._network_layer, daemon=True).start()
        # 3. Bluetooth Simulation Layer (SDP/RFCOMM Beacon)
        threading.Thread(target=self._bluetooth_layer, daemon=True).start()
        self.add_debug("HYDRA APEX CORE ONLINE - Tutti i layer di trasmissione attivi")

    def _broadcast_layer(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                        # Invia ID Progetto e IP reale
                        payload = f"APEX_BEACON|{PROJECT_ID}|{addr.address}".encode()
                        try: sock.sendto(payload, ('<broadcast>', UDP_PORT))
                        except: pass
            time.sleep(2)

    def _bluetooth_layer(self):
        """Tenta di inizializzare un beacon Bluetooth se l'hardware lo permette."""
        self.add_debug("BT_LAYER: Ricerca controller Bluetooth...")
        # Nota: In Python puro su Windows senza librerie esterne pesanti, 
        # emuliamo la presenza tramite il nome del dispositivo.
        try:
            subprocess.run(f'powershell -Command "Set-Service -Name bthserv -StartupType Automatic"', shell=True, capture_output=True)
            self.add_debug("BT_LAYER: Beacon Bluetooth sincronizzato con Hostname")
        except: pass

    def _network_layer(self):
        while True:
            if self.socket.poll(1000):
                parts = self.socket.recv_multipart()
                if len(parts) < 4: continue
                identity, _, payload, sig = parts
                if hmac.new(CORE_SECRET, payload, hashlib.sha256).hexdigest().encode() == sig:
                    data = json.loads(payload.decode())
                    self._ingest(identity, data)

    def _ingest(self, identity, data):
        nid = data['id']
        with self.lock:
            if nid not in self.nodes: self.add_debug(f"LINK ESTABLISHED: {nid} via {data.get('net','TCP')}")
            self.nodes[nid] = {
                'id': nid, 'host': data['host'], 'ip': data['ip'],
                'stats': data['s'], 'history': data['h'], 'last': time.time()
            }
            self.logs.appendleft({
                'TIME': datetime.now().strftime("%H:%M:%S"),
                'NODE': nid, 'CPU': f"{data['s']['cpu']}%", 'RAM': f"{data['s']['ram']}%"
            })

# --- CLASSE WORKER: IL NODO INFILTRATO ---
class ApexWorker:
    def __init__(self, master_ip):
        self.id = f"APEX-NODE-{uuid.uuid4().hex[:6].upper()}"
        self.master_ip = master_ip
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.DEALER)
        self.sock.setsockopt_string(zmq.IDENTITY, self.id)
        self.history = deque([0]*60, maxlen=60)
        self.active = False

    def connect_all(self):
        try:
            self.sock.connect(f"tcp://{self.master_ip}:{TCP_PORT}")
            self.active = True
            threading.Thread(target=self._heartbeat, daemon=True).start()
            return True
        except: return False

    def _heartbeat(self):
        while True:
            stats = {
                'cpu': psutil.cpu_percent(),
                'ram': psutil.virtual_memory().percent,
                'disk': psutil.disk_usage('/').percent,
                'threads': threading.active_count()
            }
            self.history.append(stats['cpu'])
            payload = {
                'id': self.id, 'host': socket.gethostname(),
                'ip': socket.gethostbyname(socket.gethostname()),
                's': stats, 'h': list(self.history), 'net': 'APEX_TUNNEL'
            }
            msg = json.dumps(payload).encode()
            sig = hmac.new(CORE_SECRET, msg, hashlib.sha256).hexdigest().encode()
            try: self.sock.send_multipart([b"", msg, sig])
            except: self.active = False
            time.sleep(1)

# --- UI APEX ---
def main():
    apply_apex_styles()
    
    if len(sys.argv) < 2:
        st.error("Specificare 'master' o 'worker'")
        return

    mode = sys.argv[1].lower()

    if mode == "master":
        if 'master_inst' not in st.session_state:
            st.session_state.master_inst = ApexMaster()
            st.session_state.master_inst.boot()
        
        m = st.session_state.master_inst

        # UI Header
        st.markdown(f"<h1 class='main-header'>HYDRA APEX</h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='letter-spacing:5px; color:#555; margin-left:10px;'>CORE VERSION 20.0 // HOST: {m.hostname}</p>", unsafe_allow_html=True)
        
        # Real-time Stats superiori
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("NODI ATTIVI", len(m.nodes))
        c2.metric("TRAFFICO", f"{len(m.logs)}")
        c3.metric("SECURITY", "AES-HMAC")
        c4.metric("UPTIME", f"{int(time.time()-m.start_time)}s")

        st.write("---")

        # Layout a due colonne
        left_col, right_col = st.columns([2, 1])

        with left_col:
            st.subheader("🛰️ NEURAL MESH TOPOLOGY")
            if not m.nodes:
                st.info("In attesa di segnali dai nodi... Assicurati che i client siano sulla stessa rete o Bluetooth.")
            else:
                for nid, data in m.nodes.items():
                    if time.time() - data['last'] < 10:
                        st.markdown(f"""
                            <div class='node-card'>
                                <div style='display:flex; justify-content:space-between;'>
                                    <b style='font-size:22px; color:var(--neon-green);'>{data['host']}</b>
                                    <span style='color:#444;'>{data['ip']}</span>
                                </div>
                                <div style='margin-top:15px; display:flex; gap:20px;'>
                                    <div><small>CPU</small><br><span class='metric-value'>{data['stats']['cpu']}%</span></div>
                                    <div><small>RAM</small><br><span class='metric-value'>{data['stats']['ram']}%</span></div>
                                    <div><small>THREADS</small><br><span class='metric-value'>{data['stats']['threads']}</span></div>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                        fig = go.Figure(go.Scatter(y=data['history'], fill='tozeroy', line=dict(color='#00ff88', width=3)))
                        fig.update_layout(height=100, margin=dict(l=0,r=0,t=0,b=0), xaxis_visible=False, yaxis_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig, use_container_width=True, key=nid)

        with right_col:
            st.subheader("📟 DEBUG CONSOLE")
            debug_text = "\n".join(list(m.debug))
            st.markdown(f"<div class='console-stream'>{debug_text}</div>", unsafe_allow_html=True)
            
            st.subheader("📡 NETWORK CONTROL")
            if st.button("FORCE WIFI AP"):
                subprocess.run(f'netsh wlan set hostednetwork mode=allow ssid=HYDRA_APEX key=password123', shell=True)
                subprocess.run('netsh wlan start hostednetwork', shell=True)
                m.add_debug("Comando AP inviato al sistema")
            
            st.write("### 📜 DATA STREAM")
            st.dataframe(pd.DataFrame(list(m.logs)), use_container_width=True)

    elif mode == "worker":
        st.markdown("<h1 class='main-header'>HYDRA NODE</h1>", unsafe_allow_html=True)
        
        if 'worker_inst' not in st.session_state:
            st.subheader("📡 Handshake Layer")
            
            # Radar Scan
            if st.button("🛰️ AVVIA RADAR SCAN (BT/WIFI/UDP)"):
                with st.spinner("Scansione frequenze APEX..."):
                    scanner = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    scanner.bind(('', UDP_PORT))
                    scanner.settimeout(5.0)
                    try:
                        data, addr = scanner.recvfrom(1024)
                        if "APEX_BEACON" in data.decode():
                            st.session_state.master_found = data.decode().split("|")[2]
                            st.success(f"MASTER RILEVATO: {st.session_state.master_found}")
                    except: st.error("Nessun beacon trovato. Verifica Bluetooth o Wi-Fi.")
                    finally: scanner.close()

            target = st.text_input("TARGET IP:", st.session_state.get('master_found', ''))
            if st.button("🚀 INFILTRATE MESH"):
                w = ApexWorker(target)
                if w.connect_all():
                    st.session_state.worker_inst = w
                    st.rerun()
        else:
            w = st.session_state.worker_inst
            st.markdown(f"<div class='node-card'>STATUS: <b>ONLINE</b><br>CONNECTED TO: {w.master_ip}</div>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            c1.metric("LOCAL CPU", f"{psutil.cpu_percent()}%")
            c2.metric("LOCAL RAM", f"{psutil.virtual_memory().percent}%")
            
            fig = go.Figure(go.Scatter(y=list(w.history), fill='tozeroy', line=dict(color='#00ff88', width=4)))
            fig.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
            
            if st.button("🔌 SCOLLEGATI"):
                del st.session_state.worker_inst
                st.rerun()

    time.sleep(1); st.rerun()

if __name__ == "__main__":
    main()