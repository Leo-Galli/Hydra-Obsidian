<p align="center">
<pre align="center">
██╗  ██╗██╗   ██╗██████╗ ██████╗  █████╗ 
██║  ██║╚██╗ ██╔╝██╔══██╗██╔══██╗██╔══██╗
███████║ ╚████╔╝ ██║  ██║██████╔╝███████║
██╔══██║  ╚██╔╝  ██║  ██║██╔══██╗██╔══██║
██║  ██║   ██║   ██████╔╝██║  ██║██║  ██║
╚═╝  ╚═╝   ╚═╝   ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
     OBSIDIAN · Distributed Telemetry
</pre>
</p>

<h1 align="center">HYDRA OBSIDIAN v2.2.0</h1>

<p align="center">
  Monitoraggio distribuito in tempo reale · Dashboard live · Sicurezza HMAC-256
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-blue?style=flat-square">
  <img src="https://img.shields.io/badge/UI-Streamlit-ff4b4b?style=flat-square">
  <img src="https://img.shields.io/badge/Network-ZeroMQ-orange?style=flat-square">
  <img src="https://img.shields.io/badge/status-active-00ff88?style=flat-square">
  <img src="https://img.shields.io/github/license/Leo-Galli/Hydra-Obsidian?style=flat-square">
</p>

---

## Indice

1. [Cos'è HYDRA](#cosè-hydra)
2. [Come funziona](#come-funziona)
3. [Requisiti](#requisiti)
4. [Installazione rapida](#installazione-rapida)
5. [Guida passo-passo (prima volta)](#guida-passo-passo-prima-volta)
6. [Architettura di rete](#architettura-di-rete)
7. [Configurazione](#configurazione)
8. [Dashboard Master](#dashboard-master)
9. [Dashboard Worker](#dashboard-worker)
10. [Sicurezza](#sicurezza)
11. [Risoluzione problemi](#risoluzione-problemi)
12. [FAQ](#faq)
13. [Changelog](#changelog)

---

## Cos'è HYDRA

**HYDRA Obsidian** è un sistema di monitoraggio telemetrico distribuito scritto in Python. Permette di osservare in tempo reale le risorse di più computer (CPU, RAM, disco, thread) da un'unica dashboard centralizzata.

Il sistema è composto da due tipi di nodi:

| Nodo | Ruolo | Comando |
|:---|:---|:---|
| **Master (Overlord)** | Riceve dati, mostra la dashboard, emette beacon di rete | `streamlit run main.py -- master` |
| **Worker (Infiltrator)** | Raccoglie metriche locali e le invia al Master | `streamlit run main.py -- worker` |

> **Caso d'uso tipico:** hai 2–3 PC in casa o in ufficio e vuoi vedere da un unico schermo quanto CPU/RAM sta consumando ciascuno, senza installare agenti complessi.

---

## Come funziona

```
┌──────────────────────────────────────────────────────────────┐
│                        MASTER (Overlord)                     │
│                                                              │
│   ┌─────────────┐   ┌──────────────┐   ┌────────────────┐  │
│   │ ZMQ ROUTER  │   │ UDP Beacon   │   │ Dashboard UI   │  │
│   │ tcp :5555   │   │ udp :5556    │   │ (Streamlit)    │  │
│   └──────┬──────┘   └──────────────┘   └────────────────┘  │
└──────────┼───────────────────────────────────────────────────┘
           │
           │  Ogni secondo: JSON firmato HMAC-SHA256
           │
     ┌─────┴─────┐
     │           │
┌────▼────┐ ┌────▼────┐
│ Worker 1│ │ Worker 2│   ... altri PC sulla stessa LAN
│ PC casa │ │ Laptop  │
└─────────┘ └─────────┘
```

**Flusso dati (semplificato):**

1. Il **Master** si avvia e apre la porta TCP `5555` (dati) e UDP `5556` (beacon).
2. Ogni 2 secondi il Master invia un **beacon UDP** broadcast: `"HYDRA_BEACON|SSID|IP"`.
3. Il **Worker** trova il Master (beacon, scansione subnet o IP manuale).
4. Il Worker si autentica con la **chiave segreta condivisa**.
5. Ogni secondo il Worker invia un pacchetto JSON con CPU, RAM, disco, thread — firmato con HMAC-256.
6. Il Master verifica la firma, aggiorna la dashboard e mostra grafici live.

---

## Requisiti

| Requisito | Dettaglio |
|:---|:---|
| **Python** | 3.9 o superiore |
| **Rete** | Master e Worker devono essere raggiungibili tra loro (stessa LAN, VPN, o stesso PC via `127.0.0.1`) |
| **Porte libere** | TCP `5555` e UDP `5556` non devono essere occupate |
| **OS** | Windows, Linux, macOS |

---

## Installazione rapida

```bash
# 1. Clona il repository
git clone https://github.com/Leo-Galli/Hydra-Obsidian.git
cd Hydra-Obsidian

# 2. (Consigliato) Crea un virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. Installa le dipendenze
pip install -r requirements.txt
```

**Dipendenze installate:**

| Pacchetto | Scopo |
|:---|:---|
| `streamlit` | Interfaccia web (dashboard) |
| `pyzmq` | Messaggistica asincrona Master ↔ Worker |
| `psutil` | Lettura metriche di sistema |
| `plotly` | Grafici CPU in tempo reale |
| `pandas`, `numpy` | Supporto interno Streamlit/Plotly |

---

## Guida passo-passo (prima volta)

### Scenario A — Tutto sullo stesso PC (test locale)

Apri **due terminali** nella cartella del progetto.

**Terminale 1 — Master:**
```bash
streamlit run main.py -- master
```
→ Si apre il browser su `http://localhost:8501` con la dashboard Overlord.

**Terminale 2 — Worker:**
```bash
streamlit run main.py -- worker
```
→ Si apre un secondo browser (porta `8502` se la 8501 è occupata).

**Nel Worker:**
1. Seleziona **"Automatico (Beacon + Localhost)"**
2. Clicca **"Avvia scoperta"** → trova il Master su `127.0.0.1`
3. Inserisci la chiave: `HYDRA_SINGULARITY_ENCRYPT_2026`
4. Clicca **"Autorizza tunnel sicuro"**
5. Vedi lo streaming attivo con grafico CPU

**Nel Master:** compare una card con il nome del PC, metriche live e grafico.

---

### Scenario B — PC diversi sulla stessa rete (LAN)

**Sul PC che farà da Master** (es. `192.168.1.100`):

```bash
streamlit run main.py -- master
```

Annota l'IP del Master. Puoi trovarlo con:
```bash
# Windows
ipconfig
# Linux/macOS
hostname -I
```

**Su ogni PC Worker** (es. `192.168.1.101`, `192.168.1.102`):

```bash
streamlit run main.py -- worker
```

Nel Worker, scegli uno dei tre metodi:

| Metodo | Quando usarlo |
|:---|:---|
| **Automatico** | Rete domestica/ufficio normale — ascolta il beacon UDP |
| **Scansione subnet** | Il beacon non funziona (firewall, VLAN) — scansiona `x.x.x.1–254` |
| **IP manuale** | Conosci già l'IP del Master — inserisci es. `192.168.1.100` |

Poi autenticati con la stessa chiave segreta del Master.

---

## Architettura di rete

### Porte utilizzate

| Porta | Protocollo | Direzione | Scopo |
|:---|:---|:---|:---|
| `5555` | TCP | Worker → Master | Trasmissione telemetria (ZeroMQ ROUTER/DEALER) |
| `5556` | UDP | Master → broadcast | Beacon di discovery ("sono qui, connettiti") |
| `8501` | TCP | Browser → Streamlit | Dashboard web (default Streamlit) |

### Formato pacchetto Worker → Master

```json
{
  "id": "HYDRA-NODE-A1B2C3",
  "host": "DESKTOP-PC",
  "ip": "192.168.1.101",
  "s": { "cpu": 23.5, "ram": 61.2, "disk": 45.0, "threads": 12 },
  "h": [10, 12, 15, 23, ...]
}
```

- `s` = statistiche istantanee
- `h` = storico CPU ultimi 60 secondi (per il grafico)

Il payload JSON viene firmato con `HMAC-SHA256(SECRET_KEY, payload_bytes)` e inviato come frame ZeroMQ:

```
[identity | "" | payload_bytes | signature_bytes]
```

### Timeout nodi

Un Worker viene considerato **offline** se non invia dati per **10 secondi** (`NODE_TIMEOUT_SEC`). Scompare automaticamente dalla dashboard Master.

---

## Configurazione

Le impostazioni principali sono in cima a `main.py`:

```python
SECRET_KEY = b"HYDRA_SINGULARITY_ENCRYPT_2026"  # Chiave condivisa Master/Worker
TCP_PORT = 5555                                   # Porta dati ZMQ
UDP_PORT = 5556                                   # Porta beacon discovery
NODE_TIMEOUT_SEC = 10                             # Secondi prima di marcare offline
REFRESH_MS = 2000                                 # Refresh dashboard (ms)
```

> **Importante:** Master e Worker devono usare la **stessa `SECRET_KEY`**. Se cambi la chiave, aggiornala su entrambi i nodi.

Per ambienti di produzione, considera di spostare `SECRET_KEY` in una variabile d'ambiente o file `.env` (non committare segreti nel repository).

---

## Dashboard Master

La dashboard Overlord mostra:

| Sezione | Contenuto |
|:---|:---|
| **Header** | Nome, versione, porte attive, badge stato |
| **Metriche globali** | Nodi online, CPU media cluster, uptime, crittografia, beacon |
| **Topologia nodi** | Card per ogni Worker con CPU/RAM/Disco/Thread + barre di progresso |
| **Grafico CPU** | Sparkline ultimi 60 secondi per ogni nodo |
| **Log eventi** | Handshake, errori firma, bind porta — con colori per severità |
| **Sidebar** | Porte, sicurezza, comandi rapidi |

La dashboard si aggiorna automaticamente ogni **2 secondi**.

---

## Dashboard Worker

Il Worker segue un wizard in 3 step:

```
[ 1. Scoperta ] → [ 2. Autenticazione ] → [ 3. Streaming ]
```

| Step | Cosa fa |
|:---|:---|
| **1. Scoperta** | Trova il Master (beacon UDP, scansione subnet, o IP manuale) |
| **2. Autenticazione** | Verifica la chiave segreta condivisa |
| **3. Streaming** | Invia telemetria ogni secondo, mostra metriche locali e grafico CPU |

---

## Sicurezza

```
Worker                          Master
  │                               │
  ├─ genera payload JSON          │
  ├─ firma: HMAC-SHA256(key, data)│
  ├─ invia [id|""|data|sig] ─────►│
  │                               ├─ ricalcola firma attesa
  │                               ├─ confronta con compare_digest()
  │                               └─ accetta ✓ o scarta ✗
```

- Ogni pacchetto è **firmato** — payload alterati vengono scartati
- Il confronto usa `hmac.compare_digest()` (resistente a timing attacks)
- La chiave è pre-condivisa: Worker e Master devono conoscerla entrambi
- **Non esporre `SECRET_KEY` in repository pubblici**

---

## Risoluzione problemi

| Problema | Causa probabile | Soluzione |
|:---|:---|:---|
| `ERRORE BIND porta 5555` | Porta già in uso | Chiudi altri processi Python/Streamlit. Su Windows: `netstat -ano \| findstr 5555` |
| `Master non trovato` | Firewall blocca UDP/TCP | Apri porte 5555 (TCP) e 5556 (UDP). Prova IP manuale |
| `Chiave non valida` | SECRET_KEY diversa | Verifica che Master e Worker usino la stessa chiave in `main.py` |
| Worker sparisce dalla dashboard | Timeout 10s | Il Worker ha perso connessione. Riavvia il terminale Worker |
| Dashboard non si aggiorna | JS refresh bloccato | Ricarica manualmente il browser (F5) |
| Scansione subnet lenta | Normale (~30s) | Usa IP manuale se conosci l'indirizzo del Master |
| Due Master sulla stessa rete | Conflitto porte | Avvia un solo Master per rete |

### Verifica connessione manuale

```bash
# Dal PC Worker, verifica che la porta TCP del Master risponda:
# Windows PowerShell:
Test-NetConnection -ComputerName 192.168.1.100 -Port 5555

# Linux/macOS:
nc -zv 192.168.1.100 5555
```

---

## FAQ

**Posso monitorare PC su reti diverse (Internet)?**
Sì, se configuri port forwarding o VPN. HYDRA è pensato per LAN locale; per Internet serve esporre la porta TCP 5555 (sconsigliato senza tunnel VPN).

**Quanti Worker posso connettere?**
Non c'è un limite hardcoded. Il Master gestisce tutti i nodi in un dizionario thread-safe. Performance ottimali fino a ~20 nodi su hardware consumer.

**Funziona su Windows?**
Sì. Il disco viene letto da `C:\` su Windows e `/` su Linux/macOS.

**Devo installare qualcosa sui Worker oltre Python?**
Solo le dipendenze di `requirements.txt`. Nessun servizio di sistema, nessuna installazione permanente.

**La dashboard Master e Worker possono girare insieme sullo stesso PC?**
Sì, è il modo più semplice per testare. Usa due terminali separati.

**Come cambio la chiave segreta?**
Modifica `SECRET_KEY` in `main.py` su **tutti** i nodi (Master e Worker). Riavvia entrambi.

---

## Struttura del progetto

```
Hydra-Obsidian/
├── main.py              # Entry point unico — logica Master + Worker + UI
├── requirements.txt     # Dipendenze Python
├── README.md            # Questa documentazione
└── LICENSE              # Licenza MIT
```

---

## Changelog

### v2.2.0 — UI Overhaul & Docs
- Redesign completo dashboard Obsidian (hero, card, barre progresso, log colorati)
- Sidebar informativa con porte e comandi
- Wizard Worker con stepper visuale
- Fix IP Worker (ora riporta IP locale, non IP del Master)
- Fix disco su Windows (`C:\` invece di `/`)
- README riscritto con guida passo-passo, FAQ e troubleshooting

### v2.1.0 — Bug Fix Release
- Fix firma HMAC: `.digest()` + `compare_digest` timing-safe
- Fix IP manuale nel Worker
- Auto-refresh via JS invece di `time.sleep + st.rerun()`
- Collector ZMQ robusto con `NOBLOCK`

### v2.0.0 — Event-Horizon
- Architettura Master/Worker unificata
- Discovery UDP Beacon multi-destinazione
- Tema Obsidian con CSS injection

---

## Contribuire

Pull request benvenute. Per modifiche sostanziali, apri prima una issue.

```bash
git checkout -b feat/nome-feature
git commit -m "feat: descrizione"
git push origin feat/nome-feature
```

---

## Licenza

Distribuito sotto licenza [MIT](LICENSE).

---

<p align="center">
  <b>HYDRA OBSIDIAN</b><br>
  <sub>High-Performance Distributed Telemetry Engine</sub><br><br>
  <img src="https://img.shields.io/badge/System_Status-ONLINE-00ff88?style=flat-square"><br><br>
  <sub>© Leonardo Galli · 2026</sub>
</p>
