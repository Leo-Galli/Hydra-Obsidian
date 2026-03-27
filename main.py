import os, sys, time, json, uuid, socket, threading, hashlib, hmac, psutil, subprocess
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import zmq
from datetime import datetime
from collections import deque

# --- CORE SYSTEM SETTINGS V30 ---
VERSION = "V2.0.0 EVENT-HORIZON"
CODENAME = "HYDRA"
SECRET_KEY = b"HYDRA_SINGULARITY_ENCRYPT_2026"
TCP_PORT = 5555   # Data Ingestion Port
UDP_PORT = 5556   # Discovery Beacon Port
BT_SSID = "HYDRA_COMMAND_CENTER"

# --- UI ARCHITECTURE: OBSIDIAN SUPREMACY ---
def apply_event_horizon_styles():
    st.set_page_config(page_title=f"{CODENAME} {VERSION}", layout="wide", initial_sidebar_state="expanded")
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;500;800&family=Inter:wght@400;900&display=swap');
        
        :root {{ --neon: #00ff88; --bg: #050505; --panel: #0d0d0d; --border: #1a1a1a; }}
        
        html, body, [class*="css"] {{ 
            background-color: var(--bg); 
            color: #dcdcdc; 
            font-family: 'Inter', sans-serif;
        }}
        
        .main-title {{ font-size: 3.5rem; font-weight: 900; letter-spacing: -3px; color: white; margin-bottom: 0px; }}
        .sub-title {{ color: var(--neon); font-family: 'JetBrains Mono'; font-size: 0.8rem; letter-spacing: 5px; text-transform: uppercase; margin-bottom: 40px; }}
        
        .stMetric {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 20px !important; }}
        
        .node-card {{
            background: linear-gradient(160deg, #0f0f0f, #050505);
            border: 1px solid var(--border);
            border-left: 5px solid var(--neon);
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 20px;
            transition: all 0.3s ease-in-out;
        }}
        .node-card:hover {{ border-color: var(--neon); transform: scale(1.01); box-shadow: 0 10px 40px rgba(0,255,136,0.1); }}

        .log-terminal {{
            background: #000;
            border: 1px solid var(--border);
            padding: 15px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: #555;
            height: 350px;
            overflow-y: auto;
            border-radius: 8px;
        }}

        .stButton>button {{
            background: transparent; border: 1px solid var(--neon); color: var(--neon);
            font-weight: 800; border-radius: 8px; height: 3.5rem; transition: 0.4s; width: 100%;
            text-transform: uppercase; letter-spacing: 2px;
        }}
        .stButton>button:hover {{ background: var(--neon); color: black; box-shadow: 0 0 30px var(--neon); }}
        
        .status-pill {{ background: #1a1a1a; padding: 5px 12px; border-radius: 50px; font-size: 0.65rem; color: var(--neon); font-weight: bold; border: 1px solid var(--neon); }}
        </style>
    """, unsafe_allow_html=True)

# --- MASTER CORE: OVERLORD ENGINE ---
class HydraMaster:
    def __init__(self):
        self.nodes = {}
        self.events = deque(maxlen=200)
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(zmq.ROUTER)
        self.socket.setsockopt(zmq.LINGER, 0)
        
        try:
            # Bind to 0.0.0.0 to accept LAN, WiFi, and Localhost traffic
            self.socket.bind(f"tcp://0.0.0.0:{TCP_PORT}")
        except Exception as e:
            st.error(f"CRITICAL: Port {TCP_PORT} is locked. Terminate existing Python processes. Error: {e}")
            
        self.lock = threading.Lock()
        self.active = True

    def launch(self):
        # 1. UDP Discovery Beacon
        threading.Thread(target=self._discovery_beacon, daemon=True).start()
        # 2. Data Stream Collector
        threading.Thread(target=self._data_collector, daemon=True).start()
        # 3. Rename Device for Bluetooth identity
        try: subprocess.run(f'powershell -Command "Rename-Computer -NewName \'{BT_SSID}\' -Force"', shell=True)
        except: pass

    def _discovery_beacon(self):
        """Sends broadcast pulses and direct localhost pulses."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            while self.active:
                # Get current machine IP
                local_ip = socket.gethostbyname(socket.gethostname())
                msg = f"HYDRA_BEACON|{BT_SSID}|{local_ip}".encode()
                # Broadcast to LAN
                try: s.sendto(msg, ('<broadcast>', UDP_PORT))
                except: pass
                # Direct to Localhost (for same-PC connection)
                try: s.sendto(msg, ('127.0.0.1', UDP_PORT))
                except: pass
                time.sleep(2)

    def _data_collector(self):
        """Asynchronously receives telemetry and verifies signatures."""
        while self.active:
            if self.socket.poll(1000):
                try:
                    parts = self.socket.recv_multipart()
                    identity, _, payload, sig = parts
                    # Security Check
                    if hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest().encode() == sig:
                        data = json.loads(payload.decode())
                        self._sync_node(identity, data)
                except: pass

    def _sync_node(self, identity, data):
        nid = data['id']
        with self.lock:
            if nid not in self.nodes:
                self.events.appendleft(f"[{datetime.now().strftime('%H:%M:%S')}] HANDSHAKE SUCCESS: {nid} via {data['ip']}")
            self.nodes[nid] = {
                'host': data['host'], 'ip': data['ip'], 'stats': data['s'],
                'history': data['h'], 'last': time.time()
            }

# --- WORKER CORE: INFILTRATOR ENGINE ---
class HydraWorker:
    def __init__(self, target_ip):
        self.id = f"HYDRA-NODE-{uuid.uuid4().hex[:6].upper()}"
        self.target = target_ip
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.DEALER)
        self.sock.setsockopt(zmq.LINGER, 0)
        self.sock.setsockopt_string(zmq.IDENTITY, self.id)
        self.cpu_history = deque([0]*60, maxlen=60)
        self.connected = False

    def engage_link(self):
        try:
            self.sock.connect(f"tcp://{self.target}:{TCP_PORT}")
            self.connected = True
            threading.Thread(target=self._telemetry_stream, daemon=True).start()
            return True
        except: return False

    def _telemetry_stream(self):
        while self.connected:
            stats = {
                'cpu': psutil.cpu_percent(),
                'ram': psutil.virtual_memory().percent,
                'disk': psutil.disk_usage('/').percent,
                'threads': threading.active_count()
            }
            self.cpu_history.append(stats['cpu'])
            payload = {
                'id': self.id, 'host': socket.gethostname(), 'ip': self.target,
                's': stats, 'h': list(self.cpu_history)
            }
            raw_data = json.dumps(payload).encode()
            signature = hmac.new(SECRET_KEY, raw_data, hashlib.sha256).hexdigest().encode()
            try:
                self.sock.send_multipart([b"", raw_data, signature])
            except: self.connected = False
            time.sleep(1)

# --- APP ROUTING & UI ---
def main():
    apply_event_horizon_styles()
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "master"

    if mode == "master":
        if 'master' not in st.session_state:
            st.session_state.master = HydraMaster()
            st.session_state.master.launch()
        
        m = st.session_state.master
        
        st.markdown("<div class='main-title'>HYDRA OVERLORD</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='sub-title'>{VERSION} // BT_SSID: {BT_SSID}</div>", unsafe_allow_html=True)
        
        # Metrics Top Bar
        active_nodes = {k: v for k, v in m.nodes.items() if time.time() - v['last'] < 10}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("NODES LINKED", len(active_nodes))
        c2.metric("ACTIVE PORT", TCP_PORT)
        c3.metric("ENCRYPTION", "HMAC-256")
        c4.metric("BROADCASTING", "ENABLED")

        st.write("---")

        col_left, col_right = st.columns([2, 1])
        
        with col_left:
            st.subheader(" GLOBAL NODE TOPOLOGY")
            if not active_nodes:
                st.info("Scanning for incoming handshake requests on loopback and LAN...")
            for nid, d in active_nodes.items():
                with st.container():
                    st.markdown(f"""
                        <div class='node-card'>
                            <div style='display:flex; justify-content:space-between; align-items:center;'>
                                <span><span class='status-pill'>ONLINE</span> <b>{d['host']}</b></span>
                                <code style='color:#555;'>{nid}</code>
                            </div>
                            <div style='display:grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap:20px; margin-top:20px;'>
                                <div><small>CPU USAGE</small><br><b style='color:var(--neon); font-size:1.5rem;'>{d['stats']['cpu']}%</b></div>
                                <div><small>RAM LOAD</small><br><b style='color:var(--neon); font-size:1.5rem;'>{d['stats']['ram']}%</b></div>
                                <div><small>THREADS</small><br><b style='color:var(--neon); font-size:1.5rem;'>{d['stats']['threads']}</b></div>
                                <div><small>LOCAL IP</small><br><b>{d['ip']}</b></div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    # Real-time Graph
                    fig = go.Figure(go.Scatter(y=d['history'], fill='tozeroy', line=dict(color='#00ff88', width=2)))
                    fig.update_layout(height=120, margin=dict(l=0,r=0,t=0,b=0), xaxis_visible=False, yaxis_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig, use_container_width=True, key=nid)

        with col_right:
            st.subheader(" MASTER COMMAND LOG")
            log_content = "\n".join(list(m.events)) if m.events else "Listening for handshake signals..."
            st.markdown(f"<div class='log-terminal'>{log_content}</div>", unsafe_allow_html=True)
            if st.button("RELOAD LOGS"): st.rerun()

    elif mode == "worker":
        st.markdown("<div class='main-title'>HYDRA WORKER</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='sub-title'>INFILTRATION MODULE // {VERSION}</div>", unsafe_allow_html=True)

        if 'step' not in st.session_state: st.session_state.step = 1

        # Interactive Step Guide
        s1, s2, s3 = st.columns(3)
        s1.markdown(f"<div style='text-align:center; color:{'#00ff88' if st.session_state.step >= 1 else '#444'};'>[ 1. SIGNAL ]</div>", unsafe_allow_html=True)
        s2.markdown(f"<div style='text-align:center; color:{'#00ff88' if st.session_state.step >= 2 else '#444'};'>[ 2. AUTH ]</div>", unsafe_allow_html=True)
        s3.markdown(f"<div style='text-align:center; color:{'#00ff88' if st.session_state.step >= 3 else '#444'};'>[ 3. STREAM ]</div>", unsafe_allow_html=True)

        st.write("---")

        if st.session_state.step == 1:
            st.subheader("Locate Master Controller")
            method = st.radio("Discovery Strategy:", ["Automatic (Beacon + Localhost)", "Aggressive Sweep (Subnet)", "Manual Static IP"])
            
            if st.button("INITIATE DISCOVERY"):
                if method == "Automatic (Beacon + Localhost)":
                    with st.spinner("Listening for Master pulses..."):
                        try:
                            # Try UDP Beacon first
                            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                                s.bind(('', UDP_PORT))
                                s.settimeout(3.0)
                                data, addr = s.recvfrom(1024)
                                raw = data.decode().split("|")
                                if raw[0] == "HYDRA_BEACON":
                                    st.session_state.target_ip = raw[2]
                                    st.session_state.step = 2; st.rerun()
                        except:
                            # If no beacon, check if Master is on the same PC
                            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                                s.settimeout(0.5)
                                if s.connect_ex(('127.0.0.1', TCP_PORT)) == 0:
                                    st.session_state.target_ip = "127.0.0.1"
                                    st.session_state.step = 2; st.rerun()
                            st.error("No Master detected on Localhost or LAN. Is the Master script running?")

                elif method == "Aggressive Sweep (Subnet)":
                    with st.spinner("Sweeping local subnet for Hydra Master..."):
                        local_ip = socket.gethostbyname(socket.gethostname())
                        base_ip = ".".join(local_ip.split('.')[:-1])
                        for i in range(1, 255):
                            target = f"{base_ip}.{i}"
                            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                                s.settimeout(0.01)
                                if s.connect_ex((target, TCP_PORT)) == 0:
                                    st.session_state.target_ip = target
                                    st.session_state.step = 2; st.rerun()
                        st.error("Aggressive sweep failed.")

                elif method == "Manual Static IP":
                    ip_in = st.text_input("Enter Master IP Address:")
                    if ip_in: st.session_state.target_ip = ip_in; st.session_state.step = 2; st.rerun()

        elif st.session_state.step == 2:
            st.success(f"Master Target Identified: {st.session_state.target_ip}")
            key_in = st.text_input("Security Access Key:", type="password")
            if st.button("AUTHORIZE TUNNEL"):
                if key_in.encode() == SECRET_KEY:
                    st.session_state.worker = HydraWorker(st.session_state.target_ip)
                    if st.session_state.worker.engage_link():
                        st.session_state.step = 3; st.rerun()
                else: st.error("Access Denied: Invalid Security Signature.")

        elif st.session_state.step == 3:
            w = st.session_state.worker
            st.markdown(f"<div class='node-card'>SECURE LINK STABILIZED: {st.session_state.target_ip}</div>", unsafe_allow_html=True)
            st.metric("NODE UNIQUE IDENTIFIER", w.id)
            
            # Telemetry Visualization
            fig = go.Figure(go.Scatter(y=list(w.cpu_history), fill='tozeroy', line=dict(color='#00ff88', width=3)))
            fig.update_layout(height=450, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)
            
            if st.button("TERMINATE CONNECTION"):
                st.session_state.step = 1
                del st.session_state.worker
                st.rerun()

    time.sleep(1); st.rerun()

if __name__ == "__main__":
    main()