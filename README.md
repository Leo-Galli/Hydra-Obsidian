<p align="center">
<pre align="center">
██╗  ██╗██╗   ██╗██████╗ ██████╗  █████╗ 
██║  ██║╚██╗ ██╔╝██╔══██╗██╔══██╗██╔══██╗
███████║ ╚████╔╝ ██║  ██║██████╔╝███████║
██╔══██║  ╚██╔╝  ██║  ██║██╔══██╗██╔══██║
██║  ██║   ██║   ██████╔╝██║  ██║██║  ██║
╚═╝  ╚═╝   ╚═╝   ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
</pre>
</p>

<h1 align="center">🐉 HYDRA OBSIDIAN v2.0.0</h1>

<p align="center">
  <strong>Decentralized Intelligence</strong> • 
  <strong>Event-Horizon Engine</strong> • 
  <strong>Absolute Mesh Dominance</strong>
</p>

<p align="center">
  <a href="https://github.com/Leo-Galli/Hydra-Obsidian">
    <img src="https://img.shields.io/badge/ACCESS-GRANTED-00ff88?style=for-the-badge&logo=opsgenie&logoColor=black">
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/SECURITY-HMAC--256-blueviolet?style=for-the-badge&logo=fortinet&logoColor=white">
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/NETWORK-ZEROMQ-orange?style=for-the-badge&logo=mqttpublish&logoColor=white">
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/github/stars/Leo-Galli/Hydra-Obsidian?style=flat-square&color=00ff88&label=STARS">
  <img src="https://img.shields.io/github/forks/Leo-Galli/Hydra-Obsidian?style=flat-square&color=00ff88&label=FORKS">
  <img src="https://img.shields.io/github/license/Leo-Galli/Hydra-Obsidian?style=flat-square&color=00ff88&label=LICENSE">
  <img src="https://img.shields.io/github/last-commit/Leo-Galli/Hydra-Obsidian?style=flat-square&color=00ff88&label=LAST%20PULSE">
</p>

---

## ⚡ Technical Core & HUD

> **HYDRA** is a high-fidelity distributed monitoring ecosystem. It uses a custom **Obsidian Supremacy** UI theme to visualize real-time telemetry from remote nodes with sub-millisecond latency.

<p align="center">
  <img src="https://skillicons.dev/icons?i=py,linux,windows,git,docker">
</p>

### 🛰️ Connectivity Stack
* **Transport Layer:** ZeroMQ (`ROUTER`/`DEALER` pattern) for high-throughput asynchronous messaging.
* **Discovery Protocol:** UDP Beacon Broadcasting (Port `5556`) for zero-config node linking.
* **Security Layer:** `HMAC-SHA256` packet signing to prevent unauthorized data injection.
* **Interface:** Streamlit powered "Event-Horizon" HUD with custom CSS injection.

---

## 🧩 Architecture Highlights



| Component | Capability | Role |
| :--- | :--- | :--- |
| **👑 Overlord** | Master Controller | Aggregates data, hosts HUD, broadcasts beacons |
| **🕵️ Infiltrator** | Worker Node | Collects PSUtil metrics, signs packets, connects to Master |
| **🔐 Singularity** | Security Key | HMAC-256 pre-shared key for cluster integrity |
| **📈 Telemetry** | Plotly Engine | Real-time time-series visualization of CPU/RAM load |

---

## 📂 System Layout

```text
HYDRA_OBSIDIAN/
├── main.py              # The Monolith (Hybrid Master/Worker logic)
├── requirements.txt     # Python dependencies
├── .env                 # Security Key & Port configurations
└── README.md            # System Documentation
````

-----

## 🚀 Deployment Protocol

### 1. Initialize Neural Link

Ensure your environment meets the minimum requirements for the Event-Horizon engine.

```bash
git clone [https://github.com/Leo-Galli/Hydra-Obsidian.git](https://github.com/Leo-Galli/Hydra-Obsidian.git)
cd Hydra-Obsidian
pip install streamlit pandas numpy plotly zmq psutil
```

### 2. Boot Master Node (Overlord)

Launch the primary command center on your monitoring station.

```bash
streamlit run main.py -- master
```

### 3. Deploy Worker Nodes (Infiltrators)

Execute on any machine within the same LAN or via Loopback.

```bash
streamlit run main.py -- worker
```

-----

## 🔐 Security Governance

  * **Handshake Success:** Only nodes with the matching `SECRET_KEY` can establish a link.
  * **Discovery Pulse:** The master broadcasts its IP; workers listen and engage automatically.
  * **Integrity Check:** Every JSON payload is hashed. Altered packets are discarded by the Overlord.

-----

## 🌍 Target Operations

  * 🤖 **Compute Grids:** Monitoring AI/ML training clusters.
  * ⚙️ **DevOps HUD:** Live infrastructure health dashboard.
  * 🎮 **Resource Tracking:** High-density workload visualization.

-----

<p align="center">
<b>HYDRA OBSIDIAN</b><br>
<sub>High-Performance Distributed Compute Engine</sub><br><br>
<img src="https://www.google.com/search?q=https://img.shields.io/badge/System_Status-Online-00ff88%3Fstyle%3Dflat-square"><br>
<sub>© Leonardo Galli · 2026</sub>
</p>