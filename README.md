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

<h1 align="center">HYDRA OBSIDIAN v2.1.0</h1>

<p align="center">
  <strong>Decentralized Intelligence</strong> &nbsp;•&nbsp;
  <strong>Event-Horizon Engine</strong> &nbsp;•&nbsp;
  <strong>Real-Time Mesh Monitoring</strong>
</p>

<p align="center">
  <a href="https://github.com/Leo-Galli/Hydra-Obsidian">
    <img src="https://img.shields.io/badge/ACCESS-GRANTED-00ff88?style=for-the-badge&logoColor=black">
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/SECURITY-HMAC--256-blueviolet?style=for-the-badge&logoColor=white">
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/NETWORK-ZEROMQ-orange?style=for-the-badge&logoColor=white">
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/UI-STREAMLIT-ff4b4b?style=for-the-badge&logoColor=white">
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/github/stars/Leo-Galli/Hydra-Obsidian?style=flat-square&color=00ff88&label=STARS">
  <img src="https://img.shields.io/github/forks/Leo-Galli/Hydra-Obsidian?style=flat-square&color=00ff88&label=FORKS">
  <img src="https://img.shields.io/github/license/Leo-Galli/Hydra-Obsidian?style=flat-square&color=00ff88&label=LICENSE">
  <img src="https://img.shields.io/github/last-commit/Leo-Galli/Hydra-Obsidian?style=flat-square&color=00ff88&label=LAST%20PULSE">
  <img src="https://img.shields.io/badge/python-3.9%2B-blue?style=flat-square">
  <img src="https://img.shields.io/badge/status-active-00ff88?style=flat-square">
</p>

---

## Overview

**HYDRA** è un sistema distribuito di monitoraggio telemetrico real-time con architettura Master/Worker.  
Il nodo **Master** aggrega dati di sistema da tutti i Worker connessi in rete e li visualizza su una dashboard live con grafici e log eventi.  
I nodi **Worker** si autenticano con firma HMAC-256 e trasmettono CPU, RAM, disco e thread ogni secondo.

<p align="center">
  <img src="https://skillicons.dev/icons?i=py,linux,windows,git,docker">
</p>

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     HYDRA MASTER                        │
│  ┌──────────────┐   ┌──────────────┐  ┌─────────────┐  │
│  │  ZMQ ROUTER  │   │  UDP Beacon  │  │  Dashboard  │  │
│  │  tcp:5555    │   │  udp:5556    │  │  Streamlit  │  │
│  └──────┬───────┘   └──────────────┘  └─────────────┘  │
└─────────┼───────────────────────────────────────────────┘
          │ HMAC-256 signed JSON
   ┌──────┴──────────────────────┐
   │                             │
┌──▼──────────┐          ┌───────▼─────┐
│ HYDRA WORKER│          │ HYDRA WORKER│
│  PC locale  │          │  LAN remoto │
└─────────────┘          └─────────────┘
```

| Componente | Ruolo |
|:---|:---|
| **👑 Overlord (Master)** | Aggrega dati, ospita la dashboard, emette beacon UDP |
| **🕵️ Infiltrator (Worker)** | Raccoglie metriche psutil, firma i pacchetti, si connette al Master |
| **🔐 Singularity Key** | Chiave HMAC-256 pre-condivisa per integrità del cluster |
| **📈 Telemetry Engine** | Visualizzazione time-series CPU/RAM con Plotly in real-time |

---

## Stack Tecnologico

| Categoria | Tecnologia |
|:---|:---|
| UI & Dashboard | [Streamlit](https://streamlit.io/) |
| Messaggistica asincrona | [ZeroMQ](https://zeromq.org/) — pattern `ROUTER/DEALER` |
| Discovery di rete | UDP Broadcast socket (`socket.SO_BROADCAST`) |
| Sicurezza | `HMAC-SHA256` con `hmac.compare_digest` (timing-safe) |
| Telemetria sistema | [psutil](https://github.com/giampaolo/psutil) |
| Grafici live | [Plotly](https://plotly.com/python/) — Scatter fill |
| Threading | `threading.Thread` + `collections.deque` |
| Serializzazione | JSON over TCP |
| Runtime | Python 3.9+ |

---

## Struttura del Progetto

```text
HYDRA_OBSIDIAN/
├── main.py              # Entry point — logica Master e Worker unificata
├── requirements.txt     # Dipendenze Python
├── .env                 # Configurazione chiave e porte (non committare!)
└── README.md            # Documentazione
```

---

## Installazione

### Prerequisiti

- Python 3.9 o superiore
- Rete LAN condivisa tra Master e Worker (oppure stesso PC via loopback)

### 1. Clona il repository

```bash
git clone https://github.com/Leo-Galli/Hydra-Obsidian.git
cd Hydra-Obsidian
```

### 2. Installa le dipendenze

```bash
pip install streamlit pandas numpy plotly pyzmq psutil
```

oppure con requirements.txt:

```bash
pip install -r requirements.txt
```

---

## Avvio

### Master Node (Overlord)

Avvia il nodo centrale di controllo sulla macchina di monitoraggio.

```bash
streamlit run main.py -- master
```

> La dashboard sarà disponibile su `http://localhost:8501`

### Worker Node (Infiltrator)

Esegui su qualsiasi macchina nella stessa LAN o in loopback sulla stessa PC.

```bash
streamlit run main.py -- worker
```

> Il Worker cercherà automaticamente il Master via UDP beacon.  
> In alternativa, usa la modalità **IP manuale** o **scansione subnet**.

---

## Discovery del Master — Modalità

Il Worker supporta tre strategie per trovare il Master:

| Modalità | Descrizione |
|:---|:---|
| **Automatico** | Ascolta il beacon UDP broadcast (porta 5556), poi controlla il loopback |
| **Scansione subnet** | Scansiona l'intero subnet locale (`x.x.x.1–254`) sulla porta TCP 5555 |
| **IP manuale** | Inserisci direttamente l'IP del Master |

---

## Sicurezza

```
[Worker] → genera payload JSON
        → firma con HMAC-SHA256(SECRET_KEY, payload)
        → invia [identity | "" | payload | signature]

[Master] → riceve il frame
        → ricalcola firma attesa
        → confronta con hmac.compare_digest() ← timing-safe
        → accetta o scarta il pacchetto
```

- Ogni pacchetto è firmato — payload alterati vengono **scartati**
- Il confronto usa `hmac.compare_digest` per prevenire timing attacks
- La `SECRET_KEY` deve essere identica su Master e Worker

> ⚠️ Non esporre la `SECRET_KEY` in repository pubblici. Usare `.env` e aggiungere al `.gitignore`.

---

## Dashboard — Funzionalità

- **Metriche live** per ogni nodo: CPU %, RAM %, Disco %, Thread attivi
- **Grafico time-series** CPU degli ultimi 60 secondi per nodo
- **Log eventi** con timestamp: handshake, connessioni, errori
- **Rilevamento nodi offline** automatico (timeout 10 secondi)
- **Auto-refresh** ogni 2 secondi tramite JS injection

---

## Casi d'Uso

- 🤖 **Cluster AI/ML** — Monitoraggio nodi di training distribuito
- ⚙️ **DevOps HUD** — Dashboard salute infrastruttura in tempo reale
- 🎮 **Workload tracking** — Visualizzazione carichi ad alta densità
- 🏠 **Home Lab** — Controllo di più PC sulla stessa rete domestica

---

## Changelog

### v2.1.0 — Bug Fix Release
- ✅ Fix firma HMAC: `.digest()` (bytes) invece di `.hexdigest()` + `compare_digest` timing-safe
- ✅ Fix bug critico **IP manuale**: `st.text_input` spostato fuori dal blocco `if st.button`
- ✅ Rimosso loop aggressivo `time.sleep(1) + st.rerun()` — sostituito con JS `setTimeout`
- ✅ Rimossa rinomina PC automatica (`subprocess` rename) — invasiva e non necessaria
- ✅ Collector ZMQ più robusto: `NOBLOCK` + catch `zmq.Again`
- ✅ `get_active_nodes()` thread-safe con lock in lettura

### v2.0.0 — Event-Horizon
- Architettura Master/Worker unificata in un singolo file
- Discovery UDP Beacon multi-destinazione (broadcast + loopback)
- Tema Obsidian Supremacy con CSS injection

---

## Contribuire

Pull request benvenute. Per modifiche sostanziali, apri prima una issue per discutere la direzione.

```bash
# Fork → branch → commit → PR
git checkout -b feature/nome-feature
git commit -m "feat: descrizione"
git push origin feature/nome-feature
```

---

## Licenza

Distribuito sotto licenza MIT. Vedi [`LICENSE`](LICENSE) per i dettagli.

---

<p align="center">
  <b>HYDRA OBSIDIAN</b><br>
  <sub>High-Performance Distributed Telemetry Engine</sub><br><br>
  <img src="https://img.shields.io/badge/System_Status-ONLINE-00ff88?style=flat-square"><br><br>
  <sub>© Leonardo Galli · 2026</sub>
</p>
