import os
import sys
import time
import json
import uuid
import socket
import threading
import hashlib
import hmac
import sqlite3
import logging
import psutil
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import zmq
from datetime import datetime
from collections import deque

SECRET_KEY = b"HYDRA_OBSIDIAN_V5_2026"
PORT = 5555
MAX_LOGS = 50
AUTO_DISTRIBUTE_MS = 2000

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("HYDRA")

class ObsidianMaster:
    def __init__(self):
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(zmq.ROUTER)
        self.socket.setsockopt(zmq.RCVHWM, 1000)
        self.socket.bind(f"tcp://*:{PORT}")
        
        self.nodes = {} 
        self.event_stream = deque(maxlen=MAX_LOGS)
        self.is_active = True
        self.lock = threading.Lock()
        self.metrics = {"tasks_ok": 0, "avg_lat": 0.0}

    def start_services(self):
        threading.Thread(target=self._network_engine, daemon=True).start()
        threading.Thread(target=self._auto_orchestrator, daemon=True).start()
        threading.Thread(target=self._cleanup_zombies, daemon=True).start()
        logger.info(f"OBSIDIAN MASTER READY ON PORT {PORT}")

    def _network_engine(self):
        while self.is_active:
            if self.socket.poll(100):
                try:
                    parts = self.socket.recv_multipart()
                    if len(parts) < 4: continue
                    addr, _, payload, sig = parts[0], parts[1], parts[2], parts[3].decode()
                    
                    if hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest() == sig:
                        data = json.loads(payload.decode())
                        self._process_incoming(addr, data)
                except Exception: pass

    def _process_incoming(self, addr, data):
        nid = data['id']
        with self.lock:
            if data['t'] == 'HEARTBEAT':
                self.nodes[nid] = {
                    'addr': addr, 'stats': data['s'], 'history': data['h'],
                    'last_seen': time.time(), 'health': 100 - data['s']['cpu']
                }
            elif data['t'] == 'ACK':
                self.metrics["tasks_ok"] += 1
                self.event_stream.appendleft({
                    'time': datetime.now().strftime("%H:%M:%S"),
                    'node': nid, 'job': data['jid'], 'status': 'COMPLETED', 'lat': f"{data['el']:.2f}s"
                })

    def _auto_orchestrator(self):
        while self.is_active:
            time.sleep(AUTO_DISTRIBUTE_MS / 1000)
            with self.lock:
                ready_nodes = [n for n, d in self.nodes.items() if d['health'] > 40]
            
            for node_id in ready_nodes:
                self._send_task(node_id)

    def _send_task(self, node_id):
        jid = f"Z-{uuid.uuid4().hex[:4].upper()}"
        payload = {'t': 'TASK', 'jid': jid}
        msg = json.dumps(payload).encode()
        sig = hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()
        with self.lock:
            if node_id in self.nodes:
                self.socket.send_multipart([self.nodes[node_id]['addr'], b"", msg, sig.encode()])

    def _cleanup_zombies(self):
        while self.is_active:
            now = time.time()
            with self.lock:
                dead = [n for n, d in self.nodes.items() if now - d['last_seen'] > 10]
                for n in dead: del self.nodes[n]
            time.sleep(5)

class ObsidianWorker:
    def __init__(self, master_ip):
        self.id = f"HYDRA-{socket.gethostname()}-{uuid.uuid4().hex[:3]}".upper()
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.DEALER)
        self.sock.setsockopt_string(zmq.IDENTITY, self.id)
        self.sock.connect(f"tcp://{master_ip}:{PORT}")
        self.history = deque([0]*25, maxlen=25)

    def run(self):
        threading.Thread(target=self._heartbeat, daemon=True).start()
        logger.info(f"WORKER {self.id} ONLINE")
        while True:
            parts = self.sock.recv_multipart()
            payload, sig = parts[1], parts[2].decode()
            if hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest() == sig:
                req = json.loads(payload.decode())
                self._execute_payload(req)

    def _execute_payload(self, req):
        t0 = time.time()
        for _ in range(100000): hashlib.sha256(b"work").hexdigest()
        
        ans = {'t': 'ACK', 'id': self.id, 'jid': req['jid'], 'el': time.time()-t0}
        msg = json.dumps(ans).encode()
        sig = hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()
        self.sock.send_multipart([b"", msg, sig.encode()])

    def _heartbeat(self):
        while True:
            cpu = psutil.cpu_percent()
            self.history.append(cpu)
            data = {'t': 'HEARTBEAT', 'id': self.id, 's': {'cpu': cpu, 'ram': psutil.virtual_memory().percent}, 'h': list(self.history)}
            msg = json.dumps(data).encode()
            sig = hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()
            try: self.sock.send_multipart([b"", msg, sig.encode()])
            except: pass
            time.sleep(2.5)

def draw_dashboard(master):
    st.set_page_config(page_title="HYDRA OBSIDIAN", layout="wide", initial_sidebar_state="collapsed")
    
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700&family=Fira+Code:wght@400;500&display=swap');
        
        html, body, [class*="css"] { 
            background-color: #0d0d0d; 
            color: #e0e0e0; 
            font-family: 'Inter', sans-serif;
        }
        
        .metric-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 20px;
            border-radius: 15px;
            text-align: center;
        }
        
        .node-container {
            background: linear-gradient(145deg, #161616, #0f0f0f);
            border: 1px solid #222;
            padding: 20px;
            border-radius: 20px;
            margin-bottom: 15px;
            transition: all 0.3s ease;
        }
        
        .node-container:hover { border-color: #00ff88; box-shadow: 0 0 15px rgba(0, 255, 136, 0.1); }
        
        .status-online { color: #00ff88; font-weight: bold; font-size: 12px; }
        .stTable { background: transparent !important; }
        
        code { font-family: 'Fira Code', monospace !important; color: #00ff88 !important; }
        </style>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([4, 1])
    with c1:
        st.markdown("<h1 style='margin:0; letter-spacing:-2px;'>HYDRA <span style='color:#00ff88'>OBSIDIAN</span></h1>", unsafe_allow_html=True)
        st.markdown("<p style='color:#666;'>Industrial Distributed Computing Core // Autonomous Mode v5.0</p>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='metric-card'><small>SYSTEM CLOCK</small><br><b style='color:#00ff88'>{datetime.now().strftime('%H:%M:%S')}</b></div>", unsafe_allow_html=True)

    st.write("---")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("NODES ACTIVE", len(master.nodes))
    m2.metric("JOBS COMPLETED", master.metrics["tasks_ok"])
    avg_load = np.mean([n['stats']['cpu'] for n in master.nodes.values()]) if master.nodes else 0
    m2.metric("CLUSTER LOAD", f"{avg_load:.1f}%")
    m4.metric("ENGINE STATE", "STABLE", delta="SECURE")

    st.markdown("###  NETWORK NODES")
    if not master.nodes:
        st.info("Searching for active mesh nodes...")
    else:
        node_items = list(master.nodes.items())
        for i in range(0, len(node_items), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(node_items):
                    nid, data = node_items[i+j]
                    with cols[j]:
                        st.markdown(f"""
                        <div class="node-container">
                            <span class="status-online">● ACTIVE</span>
                            <h4 style="margin: 5px 0;">{nid}</h4>
                            <p style="font-size:13px; color:#888;">CPU: {data['stats']['cpu']}% | RAM: {data['stats']['ram']}%</p>
                        </div>
                        """, unsafe_allow_html=True)
                        fig = go.Figure(go.Scatter(y=data['history'], fill='tozeroy', line=dict(color='#00ff88', width=2)))
                        fig.update_layout(height=80, margin=dict(l=0,r=0,t=0,b=0), xaxis_visible=False, yaxis_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig, use_container_width=True, key=f"g_{nid}")

    st.markdown("###  LIVE EVENT STREAM")
    if master.event_stream:
        df = pd.DataFrame(list(master.event_stream))
        st.dataframe(df, use_container_width=True, height=250)
    
    time.sleep(2)
    st.rerun()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: streamlit run main.py -- master | python main.py worker [ip]")
        sys.exit()

    mode = sys.argv[1].lower()
    if mode == "master":
        if 'engine' not in st.session_state:
            st.session_state.engine = ObsidianMaster()
            st.session_state.engine.start_services()
        draw_dashboard(st.session_state.engine)
    else:
        target = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
        ObsidianWorker(target).run()