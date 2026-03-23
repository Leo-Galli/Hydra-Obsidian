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

# --- CONFIGURAZIONE CORE ---
SSID = "HYDRA_NEXUS"
PASS = "obsidian2026"
SECRET_KEY = b"HYDRA_V13_ULTRA_SECURE_2026"
TCP_PORT = 5555
UDP_PORT = 5556
MAX_LOGS = 100

# --- SISTEMA DI COMANDO WIFI (WINDOWS) ---
class WiFiManager:
    @staticmethod
    def create_ap():
        """Tenta di creare l'Access Point Hydra."""
        commands = [
            f'netsh wlan set hostednetwork mode=allow ssid={SSID} key={PASS}',
            'netsh wlan start hostednetwork',
            # Forza abilitazione se su Win10/11 moderno tramite PowerShell
            f'powershell.exe -Command "Start-Process powershell -ArgumentList \'Set-NetIPv4Protocol -InterfaceAlias \\"Wi-Fi\\" -ConfiguredUpperLayerMtu 1500\' -Verb RunAs"'
        ]
        results = []
        for cmd in commands:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            results.append(res.stdout)
        return results

    @staticmethod
    def connect_to_ap():
        """Il Worker tenta di forzare la connessione al WiFi del Master."""
        # Crea profilo XML temporaneo per la connessione automatica
        xml_profile = f"""<?xml version="1.0"?>
        <WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
            <name>{SSID}</name>
            <SSIDConfig><SSID><name>{SSID}</name></SSID></SSIDConfig>
            <connectionType>ESS</connectionType>
            <connectionMode>auto</connectionMode>
            <MSM><security><authEncryption><authentication>WPA2PSK</authentication>
            <encryption>AES</encryption><useOneX>false</useOneX></authEncryption>
            <sharedKey><keyType>passPhrase</keyType><protected>false</protected>
            <keyMaterial>{PASS}</keyMaterial></sharedKey></security></MSM>
        </WLANProfile>"""
        
        with open("hydra_prof.xml", "w") as f: f.write(xml_profile)
        subprocess.run(f'netsh wlan add profile filename="hydra_prof.xml"', shell=True)
        subprocess.run(f'netsh wlan connect name={SSID}', shell=True)
        os.remove("hydra_prof.xml")

# --- STILI CSS OBSIDIAN V13 ---
def apply_styles():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700&family=Fira+Code:wght@400;500&display=swap');
        html, body, [class*="css"] { background-color: #0a0a0a; color: #e0e0e0; font-family: 'Inter', sans-serif; }
        .stMetric { background: #111; border: 1px solid #222; padding: 15px; border-radius: 12px; }
        .node-card {
            background: linear-gradient(145deg, #121212, #080808);
            border: 1px solid #1f1f1f;
            padding: 20px;
            border-radius: 18px;
            margin-bottom: 15px;
            border-left: 4px solid #00ff88;
        }
        .main-title { font-size: 3.5rem; font-weight: 800; letter-spacing: -3px; color: #fff; margin-bottom: 0; }
        .accent { color: #00ff88; }
        .stButton>button { background: #1a1a1a; border: 1px solid #333; color: #fff; border-radius: 8px; transition: 0.2s; }
        .stButton>button:hover { border-color: #00ff88; color: #00ff88; box-shadow: 0 0 10px rgba(0,255,136,0.2); }
        </style>
    """, unsafe_allow_html=True)

# --- ENGINE MASTER ---
class HydraMaster:
    def __init__(self):
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(zmq.ROUTER)
        self.socket.bind(f"tcp://0.0.0.0:{TCP_PORT}")
        self.nodes = {}
        self.logs = deque(maxlen=MAX_LOGS)
        self.lock = threading.Lock()
        self.start_time = time.time()

    def start(self):
        threading.Thread(target=self._beacon, daemon=True).start()
        threading.Thread(target=self._listener, daemon=True).start()

    def _beacon(self):
        """Broadcast UDP per annunciare l'IP del Master a chi è già in rete."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            try:
                # Recupera IP primario
                hostname = socket.gethostname()
                ip = socket.gethostbyname(hostname)
                msg = f"HYDRA_V13_HUB|{ip}".encode()
                sock.sendto(msg, ('<broadcast>', UDP_PORT))
            except: pass
            time.sleep(2)

    def _listener(self):
        while True:
            if self.socket.poll(100):
                parts = self.socket.recv_multipart()
                if len(parts) < 4: continue
                identity, payload, sig = parts[0], parts[2], parts[3]
                
                # Verifica HMAC
                if hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest().encode() == sig:
                    data = json.loads(payload.decode())
                    nid = data['id']
                    with self.lock:
                        self.nodes[nid] = {'last': time.time(), 's': data['s'], 'h': data['h']}
                        if data['t'] == 'ACK':
                            self.logs.appendleft({
                                'Timestamp': datetime.now().strftime("%H:%M:%S"),
                                'Node': nid,
                                'Task': data['jid'],
                                'Latency': f"{data['el']:.3f}s"
                            })

    def send_ping(self):
        """Invia un segnale di test a tutti i nodi per triggerare una risposta."""
        with self.lock:
            for nid, info in self.nodes.items():
                jid = f"T-{uuid.uuid4().hex[:4].upper()}"
                payload = json.dumps({'t': 'PING', 'jid': jid}).encode()
                sig = hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest().encode()
                # ZMQ ROUTER richiede [identity, empty, payload, sig]
                # In questo setup semplificato usiamo [identity, empty, payload, sig]
                # ma qui il socket è ROUTER, quindi parts[0] deve essere l'identità del nodo
                # (Inviata dal worker come identity ZMQ)
                pass # Logica gestita dal worker heartbeat in questo script

# --- ENGINE WORKER ---
class HydraWorker:
    def __init__(self, master_ip):
        self.id = f"NODE-{uuid.uuid4().hex[:4].upper()}"
        self.master_ip = master_ip
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.DEALER)
        self.sock.setsockopt_string(zmq.IDENTITY, self.id)
        self.history = deque([0]*30, maxlen=30)
        self.stats = {"cpu": 0, "ram": 0, "tasks": 0}

    def start(self):
        self.sock.connect(f"tcp://{self.master_ip}:{TCP_PORT}")
        threading.Thread(target=self._worker_loop, daemon=True).start()

    def _worker_loop(self):
        while True:
            # Stats Update
            self.stats["cpu"] = psutil.cpu_percent()
            self.stats["ram"] = psutil.virtual_memory().percent
            self.history.append(self.stats["cpu"])
            
            # Send Heartbeat
            payload = json.dumps({'t': 'HB', 'id': self.id, 's': self.stats, 'h': list(self.history)}).encode()
            sig = hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest().encode()
            self.sock.send_multipart([b"", payload, sig])
            
            # Simulazione Task Automatico ogni 5 secondi
            if time.time() % 5 < 1:
                t0 = time.time()
                for _ in range(200000): hashlib.sha256(b"work").hexdigest()
                el = time.time() - t0
                self.stats["tasks"] += 1
                ack_payload = json.dumps({'t': 'ACK', 'id': self.id, 'jid': f"AUTO-{int(t0)}", 'el': el, 's': self.stats, 'h': list(self.history)}).encode()
                ack_sig = hmac.new(SECRET_KEY, ack_payload, hashlib.sha256).hexdigest().encode()
                self.sock.send_multipart([b"", ack_payload, ack_sig])
            
            time.sleep(1.5)

# --- DASHBOARD UI ---
def main():
    apply_styles()
    
    if len(sys.argv) < 2:
        st.error("Lancio: 'streamlit run file.py master' oppure 'streamlit run file.py worker'")
        return

    mode = sys.argv[1].lower()

    if mode == "master":
        if 'master' not in st.session_state:
            st.session_state.master = HydraMaster()
            st.session_state.master.start()
        
        m = st.session_state.master
        st.markdown(f"<h1 class='main-title'>HYDRA <span class='accent'>NEXUS V13</span></h1>", unsafe_allow_html=True)
        
        # Access Point Control
        with st.sidebar:
            st.header("⚙️ Nexus Control")
            if st.button("🛰️ FORZA CREAZIONE AP"):
                res = WiFiManager.create_ap()
                st.write(res)
            st.write(f"SSID: `{SSID}`")
            st.write(f"PASS: `{PASS}`")
            st.write("---")
            st.info("Esegui come Amministratore per l'Access Point.")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("NODES ONLINE", len(m.nodes))
        c2.metric("TRAFFIC", f"{len(m.logs)} msg")
        c3.metric("SECURITY", "HMAC-SHA256")
        c4.metric("UPTIME", f"{int(time.time() - m.start_time)}s")

        st.write("### 📜 LIVE FEED")
        st.dataframe(pd.DataFrame(list(m.logs)), use_container_width=True)

        st.write("### 📡 MESH TOPOLOGY")
        nodes = list(m.nodes.items())
        for i in range(0, len(nodes), 3):
            cols = st.columns(3)
            for j in range(3):
                if i+j < len(nodes):
                    nid, data = nodes[i+j]
                    with cols[j]:
                        st.markdown(f"""
                            <div class='node-card'>
                                <small style='color:#00ff88'>ID: {nid}</small>
                                <h4 style='margin:0;'>Node Active</h4>
                                <p style='color:#888; font-size:12px;'>CPU: {data['s']['cpu']}% | RAM: {data['s']['ram']}%</p>
                            </div>
                        """, unsafe_allow_html=True)
                        fig = go.Figure(go.Scatter(y=data['h'], fill='tozeroy', line=dict(color='#00ff88', width=2)))
                        fig.update_layout(height=100, margin=dict(l=0,r=0,t=0,b=0), xaxis_visible=False, yaxis_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig, use_container_width=True, key=nid)
        
        time.sleep(1); st.rerun()

    elif mode == "worker":
        st.markdown(f"<h1 class='main-title'>HYDRA <span class='accent'>NODE</span></h1>", unsafe_allow_html=True)
        
        if 'worker' not in st.session_state:
            st.markdown("<div class='node-card'>", unsafe_allow_html=True)
            st.subheader("Infiltration Module")
            
            if st.button("📡 AUTO-SCAN & CONNECT TO NEXUS WIFI"):
                with st.spinner("Connessione al Wi-Fi HYDRA_NEXUS..."):
                    WiFiManager.connect_to_ap()
                    time.sleep(3)
                    # Scan UDP per l'IP del Master
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.bind(('', UDP_PORT)); sock.settimeout(5.0)
                    try:
                        data, addr = sock.recvfrom(1024)
                        if data.startswith(b"HYDRA_V13_HUB"):
                            st.session_state.master_ip = data.decode().split("|")[1]
                            st.success(f"Master Rilevato: {st.session_state.master_ip}")
                    except: st.error("Master non trovato. Assicurati che l'Access Point sia attivo.")
                    finally: sock.close()

            ip = st.text_input("Master IP (manuale):", st.session_state.get('master_ip', ''))
            if st.button("🚀 JOIN MESH"):
                st.session_state.worker = HydraWorker(ip)
                st.session_state.worker.start()
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            w = st.session_state.worker
            m1, m2, m3 = st.columns(3)
            m1.metric("NODE ID", w.id)
            m2.metric("TASKS DONE", w.stats["tasks"])
            m3.metric("LOAD", f"{w.stats['cpu']}%")
            
            fig = go.Figure(go.Scatter(y=list(w.history), fill='tozeroy', line=dict(color='#00ff88', width=3)))
            fig.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
            time.sleep(1); st.rerun()

if __name__ == "__main__":
    main()