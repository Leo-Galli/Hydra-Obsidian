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

# --- CONFIGURAZIONE DI ELITE ---
SECRET_KEY = b"HYDRA_OBSIDIAN_V12_ULTRA_2026"
TCP_PORT = 5555
UDP_PORT = 5556
BEACON_STR = "HYDRA_SERVER_ANNOUNCE_V12"
MAX_LOGS = 100

# --- SISTEMA DI RETE AVANZATO ---
def get_network_map():
    """Mappa tutte le schede di rete attive per il binding."""
    map_data = []
    for interface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                map_data.append({"int": interface, "ip": addr.address})
    return map_data

def force_hotspot_start():
    """
    Tenta di forzare l'attivazione dell'hotspot Windows.
    Se netsh fallisce, avvisa l'utente di attivare l'Hotspot Mobile manualmente 
    dalle impostazioni di Windows.
    """
    try:
        # Configura
        subprocess.run('netsh wlan set hostednetwork mode=allow ssid=HYDRA_NEXUS key=obsidian2026', shell=True, capture_output=True)
        # Avvia
        res = subprocess.run('netsh wlan start hostednetwork', shell=True, capture_output=True)
        if res.returncode != 0:
            return False, "Hardware non supporta netsh. Attiva 'Hotspot Mobile' manualmente nelle impostazioni di Windows."
        return True, "Hotspot HYDRA_NEXUS avviato con successo."
    except Exception as e:
        return False, str(e)

# --- STILI CSS OBSIDIAN (DEEP MODE) ---
def apply_nexus_styles():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700&family=Fira+Code:wght@400;500&display=swap');
        
        /* Sfondo e Testo Base */
        html, body, [class*="css"] { 
            background-color: #050505; 
            color: #d1d1d1; 
            font-family: 'Inter', sans-serif;
        }
        
        /* Container Nodi */
        .node-box {
            background: linear-gradient(180deg, #111 0%, #080808 100%);
            border: 1px solid #222;
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 20px;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        .node-box:hover {
            border-color: #00ff88;
            box-shadow: 0 0 30px rgba(0, 255, 136, 0.15);
            transform: translateY(-5px);
        }
        
        /* Titoli e Decorazioni */
        .glitch-title {
            font-size: 3.5rem;
            font-weight: 800;
            letter-spacing: -3px;
            background: linear-gradient(to right, #fff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .status-tag {
            background: rgba(0, 255, 136, 0.1);
            color: #00ff88;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 10px;
            font-weight: bold;
            text-transform: uppercase;
        }

        /* Metrics */
        [data-testid="stMetricValue"] { color: #00ff88 !important; font-family: 'Fira Code', monospace; }
        
        /* Scrollbar */
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: #050505; }
        ::-webkit-scrollbar-thumb { background: #222; border-radius: 10px; }
        </style>
    """, unsafe_allow_html=True)

# --- CLASSE MASTER CORE ---
class NexusMaster:
    def __init__(self):
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(zmq.ROUTER)
        self.socket.setsockopt(zmq.SNDHWM, 5000)
        self.socket.bind(f"tcp://0.0.0.0:{TCP_PORT}")
        
        self.nodes = {}
        self.event_stream = deque(maxlen=MAX_LOGS)
        self.metrics = {"jobs_total": 0, "uptime": time.time()}
        self.lock = threading.Lock()

    def start(self):
        # Thread 1: Beacon Broadcast (Per far trovare l'IP ai worker)
        threading.Thread(target=self._run_beacon, daemon=True).start()
        # Thread 2: Ricezione Dati ZMQ
        threading.Thread(target=self._run_engine, daemon=True).start()
        # Thread 3: Monitoraggio Nodi
        threading.Thread(target=self._run_monitor, daemon=True).start()

    def _run_beacon(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            interfaces = get_network_map()
            for entry in interfaces:
                msg = f"{BEACON_STR}|{entry['ip']}".encode()
                try: sock.sendto(msg, ('<broadcast>', UDP_PORT))
                except: pass
            time.sleep(1.5)

    def _run_engine(self):
        while True:
            if self.socket.poll(100):
                try:
                    parts = self.socket.recv_multipart()
                    if len(parts) < 4: continue
                    identity, payload, signature = parts[0], parts[2], parts[3]
                    
                    # Security Check
                    expected_sig = hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest().encode()
                    if hmac.compare_digest(expected_sig, signature):
                        data = json.loads(payload.decode())
                        self._handle_data(identity, data)
                except: pass

    def _handle_data(self, identity, data):
        nid = data['id']
        with self.lock:
            if data['type'] == 'HB': # Heartbeat
                self.nodes[nid] = {
                    'identity': identity,
                    'stats': data['stats'],
                    'history': data['history'],
                    'last_seen': time.time()
                }
            elif data['type'] == 'RESULT': # Task Completion
                self.metrics["jobs_total"] += 1
                self.event_stream.appendleft({
                    'clock': datetime.now().strftime("%H:%M:%S"),
                    'node': nid,
                    'task_id': data['task_id'],
                    'latency': f"{data['elapsed']:.3f}s"
                })

    def _run_monitor(self):
        while True:
            now = time.time()
            with self.lock:
                dead_nodes = [n for n, d in self.nodes.items() if now - d['last_seen'] > 12]
                for n in dead_nodes: del self.nodes[n]
            time.sleep(5)

    def dispatch_task(self):
        """Invia un job di test a tutti i nodi connessi."""
        with self.lock:
            for nid, d in self.nodes.items():
                task_id = f"JOB-{uuid.uuid4().hex[:4].upper()}"
                payload = json.dumps({'type': 'TASK', 'task_id': task_id}).encode()
                sig = hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest().encode()
                self.socket.send_multipart([d['identity'], b"", payload, sig])

# --- CLASSE WORKER CORE ---
class NexusWorker:
    def __init__(self, master_ip):
        self.id = f"HYDRA-{socket.gethostname()}-{uuid.uuid4().hex[:4].upper()}"
        self.master_ip = master_ip
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.DEALER)
        self.sock.setsockopt_string(zmq.IDENTITY, self.id)
        
        self.history = deque([0]*40, maxlen=40)
        self.logs = deque(maxlen=MAX_LOGS)
        self.stats = {"cpu": 0, "ram": 0, "done": 0}
        self.running = False

    def start(self):
        self.sock.connect(f"tcp://{self.master_ip}:{TCP_PORT}")
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self.running:
            # 1. Update Metrics
            self.stats['cpu'] = psutil.cpu_percent()
            self.stats['ram'] = psutil.virtual_memory().percent
            self.history.append(self.stats['cpu'])
            
            # 2. Send Heartbeat
            payload = json.dumps({'type': 'HB', 'id': self.id, 'stats': self.stats, 'history': list(self.history)}).encode()
            sig = hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest().encode()
            self.sock.send_multipart([b"", payload, sig])
            
            # 3. Listen for Tasks
            if self.sock.poll(1000):
                parts = self.sock.recv_multipart()
                payload, signature = parts[1], parts[2]
                if hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest().encode() == signature:
                    req = json.loads(payload.decode())
                    if req['type'] == 'TASK':
                        t0 = time.time()
                        # Simulazione carico (Hashing intensivo)
                        for _ in range(300000): hashlib.sha256(b"nexus_payload").hexdigest()
                        elapsed = time.time() - t0
                        self.stats['done'] += 1
                        
                        # Send Result
                        res_p = json.dumps({'type': 'RESULT', 'id': self.id, 'task_id': req['task_id'], 'elapsed': elapsed, 'stats': self.stats}).encode()
                        res_s = hmac.new(SECRET_KEY, res_p, hashlib.sha256).hexdigest().encode()
                        self.sock.send_multipart([b"", res_p, res_s])
            time.sleep(1)

# --- DASHBOARD UI ---
def main():
    apply_nexus_styles()
    
    if len(sys.argv) < 2:
        st.error("ERRORE: Devi specificare 'master' o 'worker' come argomento.")
        return

    mode = sys.argv[1].lower()

    if mode == "master":
        if 'master_node' not in st.session_state:
            st.session_state.master_node = NexusMaster()
            st.session_state.master_node.start()
        
        m = st.session_state.master_node
        
        # Header
        st.markdown("<h1 class='glitch-title'>HYDRA NEXUS</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color:#666; margin-top:-20px;'>Decentralized Mesh Engine // Obsidian Series</p>", unsafe_allow_html=True)
        
        # Dashboard Metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("NODES ONLINE", len(m.nodes))
        c2.metric("JOBS COMPLETED", m.metrics["jobs_total"])
        c3.metric("MESH HEALTH", "OPTIMAL" if len(m.nodes) > 0 else "IDLE")
        c4.metric("BROADCAST", "ACTIVE")

        # Control Panel
        st.write("---")
        col_ctrl1, col_ctrl2 = st.columns([1, 2])
        with col_ctrl1:
            if st.button("🚀 DISPATCH TEST JOBS"):
                m.dispatch_task()
                st.success("Tasks sent to all nodes.")
            
            if st.button("📡 RESET HOTSPOT"):
                ok, msg = force_hotspot_start()
                if ok: st.success(msg)
                else: st.warning(msg)

        with col_ctrl2:
            with st.expander("🌐 Network Interface Map"):
                st.table(get_network_map())

        # Grid dei Nodi
        st.markdown("### 🛰️ CONNECTED MESH NODES")
        node_list = list(m.nodes.items())
        if not node_list:
            st.info("In attesa di connessioni... Assicurati che i Worker siano nella stessa rete o connessi via USB.")
        else:
            for i in range(0, len(node_list), 3):
                cols = st.columns(3)
                for j in range(3):
                    if i + j < len(node_list):
                        nid, data = node_list[i+j]
                        with cols[j]:
                            st.markdown(f"""
                                <div class='node-box'>
                                    <span class='status-tag'>● Verified Node</span>
                                    <h3 style='margin:10px 0;'>{nid}</h3>
                                    <p style='color:#666; font-size:12px;'>CPU: {data['stats']['cpu']}% | RAM: {data['stats']['ram']}%</p>
                                </div>
                            """, unsafe_allow_html=True)
                            fig = go.Figure(go.Scatter(y=data['history'], fill='tozeroy', line=dict(color='#00ff88', width=2)))
                            fig.update_layout(height=100, margin=dict(l=0,r=0,t=0,b=0), xaxis_visible=False, yaxis_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                            st.plotly_chart(fig, use_container_width=True, key=nid)

        st.markdown("### 📜 GLOBAL EVENT LOG")
        st.dataframe(pd.DataFrame(list(m.event_stream)), use_container_width=True)
        
        time.sleep(1)
        st.rerun()

    elif mode == "worker":
        st.markdown("<h1 class='glitch-title'>HYDRA NODE</h1>", unsafe_allow_html=True)
        
        if 'worker_node' not in st.session_state:
            st.markdown("<div class='node-box'>", unsafe_allow_html=True)
            st.subheader("📡 Infiltration Setup")
            
            if st.button("🔍 AUTO-SCAN FOR NEXUS HUB"):
                with st.spinner("Ascolto Beacon UDP su porta 5556..."):
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.bind(('', UDP_PORT))
                    sock.settimeout(6.0)
                    try:
                        data, addr = sock.recvfrom(1024)
                        if data.startswith(BEACON_STR.encode()):
                            st.session_state.hub_ip = data.decode().split("|")[1]
                            st.success(f"Nexus Hub Rilevato: {st.session_state.hub_ip}")
                    except:
                        st.error("Nessun Hub rilevato. Attiva Hotspot Mobile o usa USB Tethering.")
                    finally: sock.close()
            
            target = st.text_input("Hub IP Address:", st.session_state.get('hub_ip', ''))
            if st.button("🔗 ESTABLISH CONNECTION"):
                st.session_state.worker_node = NexusWorker(target)
                st.session_state.worker_node.start()
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            w = st.session_state.worker_node
            
            # Metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("NODE ID", w.id[:12])
            m2.metric("TASKS DONE", w.stats['done'])
            m3.metric("LOAD", f"{w.stats['cpu']}%")

            # Chart
            fig = go.Figure(go.Scatter(y=list(w.history), fill='tozeroy', line=dict(color='#00ff88', width=3)))
            fig.update_layout(height=350, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis=dict(gridcolor='#111'), xaxis=dict(gridcolor='#111'))
            st.plotly_chart(fig, use_container_width=True)
            
            st.caption(f"Connected to Nexus at: {w.master_ip}")
            time.sleep(1)
            st.rerun()

if __name__ == "__main__":
    main()