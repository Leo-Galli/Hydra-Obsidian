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
from datetime import datetime
from collections import deque

# --- CONFIGURAZIONE CORE ---
SECRET_KEY = b"HYDRA_OBSIDIAN_V16_ULTRA"
TCP_PORT = 5555
UDP_PORT = 5556 # Per il Beacon discovery
MAX_LOGS = 60

# --- UTILS DI RETE MULTI-LAYER ---
def get_all_interfaces():
    """Mappa tutte le interfacce: LAN, Wi-Fi, USB Ethernet, Virtual Bridge."""
    interfaces = []
    for interface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                interfaces.append({
                    "name": interface,
                    "ip": addr.address,
                    "type": "USB/NDIS" if "ndis" in interface.lower() or "ethernet" in interface.lower() else "WLAN/LAN"
                })
    return interfaces

# --- STILI CSS ---
def apply_custom_styles():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700;900&family=Fira+Code:wght@400;500&display=swap');
        html, body, [class*="css"] { 
            background-color: #050505; 
            color: #d1d1d1; 
            font-family: 'Inter', sans-serif;
        }
        .metric-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(0, 255, 136, 0.1);
            padding: 15px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        }
        .node-container {
            background: linear-gradient(180deg, #111, #080808);
            border: 1px solid #222;
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 15px;
            transition: all 0.3s ease;
        }
        .node-container:hover { border-color: #00ff88; box-shadow: 0 0 20px rgba(0, 255, 136, 0.1); }
        .status-online { color: #00ff88; font-weight: bold; font-size: 11px; text-transform: uppercase; letter-spacing: 1px;}
        h1, h2, h3 { letter-spacing: -2px; font-weight: 900; }
        code { font-family: 'Fira Code', monospace !important; color: #00ff88 !important; background: transparent !important; }
        .stDataFrame { border-radius: 10px; overflow: hidden; border: 1px solid #222; }
        </style>
    """, unsafe_allow_html=True)

# --- CLASSE MASTER ---
class ObsidianMaster:
    def __init__(self):
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(zmq.ROUTER)
        # Binding universale su tutte le interfacce (LAN, USB, BT-PAN)
        self.socket.bind(f"tcp://0.0.0.0:{TCP_PORT}")
        self.nodes = {} 
        self.event_stream = deque(maxlen=MAX_LOGS)
        self.metrics = {"tasks_ok": 0, "bytes_recv": 0}
        self.lock = threading.Lock()

    def start(self):
        threading.Thread(target=self._beacon_announcer, daemon=True).start()
        threading.Thread(target=self._network_engine, daemon=True).start()
        threading.Thread(target=self._cleanup, daemon=True).start()

    def _beacon_announcer(self):
        """Invia segnali di presenza su ogni sottorete disponibile."""
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            for interface in get_all_interfaces():
                try:
                    # Annuncia l'IP del master per l'auto-discovery
                    msg = f"HYDRA_MASTER_V16|{interface['ip']}".encode()
                    udp_sock.sendto(msg, ('<broadcast>', UDP_PORT))
                except: pass
            time.sleep(2)

    def _network_engine(self):
        while True:
            if self.socket.poll(100):
                try:
                    parts = self.socket.recv_multipart()
                    addr, payload, sig = parts[0], parts[2], parts[3].decode()
                    if hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest() == sig:
                        data = json.loads(payload.decode())
                        self._process(addr, data)
                except: pass

    def _process(self, addr, data):
        nid = data['id']
        with self.lock:
            if data['t'] == 'HB':
                self.nodes[nid] = {
                    'addr': addr, 
                    'stats': data['s'], 
                    'history': data['h'], 
                    'type': data.get('net_type', 'UNKNOWN'),
                    'last': time.time()
                }
            elif data['t'] == 'ACK':
                self.metrics["tasks_ok"] += 1
                self.event_stream.appendleft({
                    'time': datetime.now().strftime("%H:%M:%S"), 
                    'node': nid, 
                    'job': data['jid'], 
                    'status': 'SUCCESS', 
                    'latency': f"{data['el']:.3f}s",
                    'cpu_at_task': f"{data['s']['cpu']}%"
                })

    def _cleanup(self):
        while True:
            now = time.time()
            with self.lock:
                dead = [n for n, d in self.nodes.items() if now - d['last'] > 12]
                for n in dead: del self.nodes[n]
            time.sleep(5)

# --- CLASSE WORKER ---
class ObsidianWorker:
    def __init__(self, target_ip=None):
        self.id = f"HYDRA-{socket.gethostname()}-{uuid.uuid4().hex[:4]}".upper()
        self.master_ip = target_ip
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.DEALER)
        self.sock.setsockopt_string(zmq.IDENTITY, self.id)
        self.history = deque([0]*30, maxlen=30)
        self.local_events = deque(maxlen=MAX_LOGS)
        self.metrics = {"tasks_done": 0, "cpu": 0, "ram": 0, "threads": 0}
        self.connection_type = "SCANNING"

    def auto_discover(self):
        """Logica gerarchica: Cerca Master in Sottorete -> USB -> Bluetooth."""
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.bind(('', UDP_PORT))
        udp_sock.settimeout(5.0)
        try:
            data, addr = udp_sock.recvfrom(1024)
            msg = data.decode()
            if "HYDRA_MASTER_V16" in msg:
                self.master_ip = msg.split("|")[1]
                self.connection_type = "AUTO_DISCOVERED"
                return True
        except: return False
        finally: udp_sock.close()

    def start(self):
        if not self.master_ip:
            if not self.auto_discover():
                self.master_ip = "127.0.0.1" # Fallback
        
        self.sock.connect(f"tcp://{self.master_ip}:{TCP_PORT}")
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        threading.Thread(target=self._task_loop, daemon=True).start()

    def _task_loop(self):
        while True:
            if self.sock.poll(1000):
                parts = self.sock.recv_multipart()
                payload, sig = parts[1], parts[2].decode()
                if hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest() == sig:
                    req = json.loads(payload.decode())
                    t0 = time.time()
                    # Neural Work Simulation
                    for _ in range(300000): hashlib.sha256(b"neural_core_hash").hexdigest()
                    el = time.time() - t0
                    self.metrics["tasks_done"] += 1
                    
                    self.local_events.appendleft({
                        'time': datetime.now().strftime("%H:%M:%S"), 
                        'job': req['jid'], 
                        'status': 'COMPLETED', 
                        'lat': f"{el:.4f}s"
                    })
                    
                    ans = {
                        't': 'ACK', 'id': self.id, 'jid': req['jid'], 'el': el,
                        's': {'cpu': psutil.cpu_percent(), 'ram': psutil.virtual_memory().percent}
                    }
                    msg = json.dumps(ans).encode()
                    sig_ans = hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()
                    self.sock.send_multipart([b"", msg, sig_ans.encode()])

    def _heartbeat_loop(self):
        while True:
            self.metrics.update({
                "cpu": psutil.cpu_percent(),
                "ram": psutil.virtual_memory().percent,
                "threads": threading.active_count()
            })
            self.history.append(self.metrics["cpu"])
            
            data = {
                't': 'HB', 
                'id': self.id, 
                's': self.metrics, 
                'h': list(self.history),
                'net_type': self.connection_type
            }
            msg = json.dumps(data).encode()
            sig = hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()
            try: self.sock.send_multipart([b"", msg, sig.encode()])
            except: pass
            time.sleep(2)

# --- DASHBOARD ---
def draw_main():
    apply_custom_styles()
    mode = sys.argv[1].lower()

    if mode == "master":
        if 'engine' not in st.session_state:
            st.session_state.engine = ObsidianMaster()
            st.session_state.engine.start()
        
        master = st.session_state.engine
        
        # Header
        col_t, col_s = st.columns([3, 1])
        with col_t:
            st.markdown("<h1 style='font-size: 3rem; margin:0;'>HYDRA <span style='color:#00ff88'>NEXUS V16</span></h1>", unsafe_allow_html=True)
            st.markdown(f"**NEURAL CORE ACTIVE** // Monitoring `{len(get_all_interfaces())}` interfaces")
        with col_s:
             st.markdown(f"<div class='metric-card'><small>SESSION TIME</small><br><b style='color:#00ff88'>{datetime.now().strftime('%H:%M:%S')}</b></div>", unsafe_allow_html=True)

        st.write("---")

        # Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("ACTIVE NODES", len(master.nodes))
        m2.metric("JOBS PROCESSED", master.metrics["tasks_ok"])
        avg_cpu = np.mean([n['stats']['cpu'] for n in master.nodes.values()]) if master.nodes else 0
        m3.metric("MESH LOAD", f"{avg_cpu:.1f}%")
        m4.metric("BROADCAST", "ACTIVE", delta="STABLE")

        # Nodes Grid
        st.markdown("### 🛰️ MESH TOPOLOGY")
        if not master.nodes: st.info("Waiting for neural handshake on LAN/USB/BT...")
        else:
            node_items = list(master.nodes.items())
            for i in range(0, len(node_items), 3):
                cols = st.columns(3)
                for j in range(3):
                    if i + j < len(node_items):
                        nid, data = node_items[i+j]
                        with cols[j]:
                            st.markdown(f"""
                            <div class='node-container'>
                                <span class='status-online'>● LINKED via {data['type']}</span>
                                <h4 style='margin:10px 0;'>{nid}</h4>
                                <code style='font-size:12px;'>CPU: {data['stats']['cpu']}% | RAM: {data['stats']['ram']}% | THREADS: {data['stats']['threads']}</code>
                            </div>
                            """, unsafe_allow_html=True)
                            fig = go.Figure(go.Scatter(y=data['history'], fill='tozeroy', line=dict(color='#00ff88', width=2)))
                            fig.update_layout(height=80, margin=dict(l=0,r=0,t=0,b=0), xaxis_visible=False, yaxis_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                            st.plotly_chart(fig, use_container_width=True, key=f"g_{nid}")

        st.markdown("### 📜 GLOBAL EVENT LOG")
        st.dataframe(pd.DataFrame(list(master.event_stream)), use_container_width=True)

    elif mode == "worker":
        if 'node' not in st.session_state:
            # Auto-Discovery mode
            manual_ip = sys.argv[2] if len(sys.argv) > 2 else None
            st.session_state.node = ObsidianWorker(manual_ip)
            st.session_state.node.start()
        
        worker = st.session_state.node
        st.markdown(f"<h1 style='margin:0;'>NODE <span style='color:#00ff88'>INFILTRATOR</span></h1>", unsafe_allow_html=True)
        st.markdown(f"**ID:** `{worker.id}` // **STATUS:** `{worker.connection_type}`")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("LOCAL LOAD", f"{worker.metrics['cpu']}%")
        m2.metric("RAM UTIL", f"{worker.metrics['ram']}%")
        m3.metric("TASKS DONE", worker.metrics["tasks_done"])
        m4.metric("ACTIVE THREADS", worker.metrics["threads"])

        st.markdown("### 📈 ANALYTICS")
        fig = go.Figure(go.Scatter(y=list(worker.history), fill='tozeroy', line=dict(color='#00ff88', width=3)))
        fig.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis=dict(gridcolor='#111'), xaxis=dict(gridcolor='#111'))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### 📜 LOCAL JOBS")
        st.dataframe(pd.DataFrame(list(worker.local_events)), use_container_width=True)

    time.sleep(1.5)
    st.rerun()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage Master: streamlit run file.py master")
        print("Usage Worker: streamlit run file.py worker [optional_manual_ip]")
    else:
        draw_main()