<p align="center">
<pre align="center">
██╗  ██╗██╗   ██╗██████╗ ██████╗  █████╗ 
██║  ██║╚██╗ ██╔╝██╔══██╗██╔══██╗██╔══██╗
███████║ ╚████╔╝ ██║  ██║██████╔╝███████║
██╔══██║  ╚██╔╝  ██║  ██║██╔══██╗██╔══██║
██║  ██║   ██║   ██████╔╝██║  ██║██║  ██║
╚═╝  ╚═╝   ╚═╝   ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
     OBSIDIAN · Infrastructure Control
</pre>
</p>

<h1 align="center">HYDRA OBSIDIAN v3.0.0</h1>

<p align="center">
  Monitoraggio distribuito · Terminal remoto admin · Home lab &amp; Datacenter
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-blue?style=flat-square">
  <img src="https://img.shields.io/badge/UI-Streamlit-ff4b4b?style=flat-square">
  <img src="https://img.shields.io/badge/Network-ZeroMQ-orange?style=flat-square">
  <img src="https://img.shields.io/badge/Remote_Exec-Cross--OS-10b981?style=flat-square">
  <img src="https://img.shields.io/github/license/Leo-Galli/Hydra-Obsidian?style=flat-square">
</p>

---

## Indice

1. [Cos'e HYDRA](#cosè-hydra)
2. [Per chi e pensato](#per-chi-è-pensato)
3. [Funzionalita](#funzionalità)
4. [Installazione](#installazione)
5. [Avvio rapido](#avvio-rapido)
6. [Terminal remoto admin](#terminal-remoto-admin)
7. [Comandi cross-platform](#comandi-cross-platform)
8. [Architettura](#architettura)
9. [Sicurezza](#sicurezza)
10. [Configurazione](#configurazione)
11. [Troubleshooting](#troubleshooting)
12. [Changelog](#changelog)

---

## Cos'e HYDRA

**HYDRA Obsidian** e una control plane distribuita per infrastrutture fisiche e virtuali. Da un unico Master puoi:

- **Monitorare** CPU, RAM, disco e thread di ogni nodo in tempo reale
- **Eseguire comandi shell remoti** su Windows, Linux e macOS
- **Gestire** home lab, uffici e rack datacenter dalla stessa dashboard

Due tipi di nodi:

| Nodo | Ruolo | Comando |
|:---|:---|:---|
| **Master (Overlord)** | Dashboard, aggregazione metriche, terminal remoto | `streamlit run main.py -- master` |
| **Worker (Agent)** | Telemetria + esecuzione comandi sul host locale | `streamlit run main.py -- worker` |

---

## Per chi e pensato

| Scenario | Esempio |
|:---|:---|
| **Home lab** | 3 PC + NAS — monitoraggio e comandi da un unico schermo |
| **Ufficio SMB** | Workstation e server LAN — health check centralizzato |
| **Datacenter / rack** | Decine di nodi Linux/Windows — telemetry + remote shell firmata |
| **DevOps locale** | Test cluster prima del deploy in produzione |

---

## Funzionalita

### Monitoraggio (tab Monitoraggio)

- Metriche live per nodo: CPU, RAM, disco, thread, IP, OS
- Grafico CPU ultimi 60 secondi
- Log eventi con handshake, exec, errori
- Auto-refresh ogni 2 secondi
- Timeout nodi offline: 10 secondi

### Terminal remoto (tab Terminal remoto)

- Connessione shell ai nodi Worker dal Master
- Target singolo o **broadcast su tutti i nodi**
- Comandi eseguiti via shell nativa del SO (`cmd.exe` su Windows, `/bin/sh` su Unix)
- Output stdout/stderr con exit code
- **Gate admin**: chiave + checkbox obbligatori prima dell'uso

> **IMPORTANTE:** i comandi vengono eseguiti con i privilegi dell'utente che avvia il Worker. Per operazioni admin, avvia il Worker come amministratore (Windows) o root/sudo (Linux).

---

## Installazione

```bash
git clone https://github.com/Leo-Galli/Hydra-Obsidian.git
cd Hydra-Obsidian
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

---

## Avvio rapido

### Test locale (stesso PC)

**Terminale 1 — Master:**
```bash
streamlit run main.py -- master
```

**Terminale 2 — Worker (preferibilmente come admin):**
```bash
# Windows: apri PowerShell/CMD come Amministratore
streamlit run main.py -- worker
```

Nel Worker: discovery automatica → chiave `HYDRA_SINGULARITY_ENCRYPT_2026` → connetti.

Nel Master: tab **Monitoraggio** per metriche, tab **Terminal remoto** per comandi.

### LAN / Datacenter

1. Master su macchina di controllo (es. `10.0.0.1`)
2. Worker su ogni server/VM del rack
3. Apri porte TCP `5555` e UDP `5556` tra i nodi
4. Avvia Worker con privilegi adeguati per i comandi che devi eseguire

---

## Terminal remoto admin

### Flusso

```
1. Master → tab "Terminal remoto"
2. Inserisci chiave admin + conferma checkbox
3. Seleziona nodo (o "Tutti i nodi")
4. Scrivi comando shell → Esegui
5. Worker esegue localmente → risposta firmata HMAC → Master mostra output
```

### Requisiti admin

| Sistema | Come avviare Worker con privilegi |
|:---|:---|
| **Windows** | PowerShell/CMD **Esegui come amministratore** |
| **Linux** | `sudo streamlit run main.py -- worker` o utente root |
| **macOS** | Terminale con utente admin o `sudo` |

### Limiti

- Timeout comando: **30 secondi**
- Lunghezza max comando: **4096 caratteri**
- Output max: **64 KB** per stdout/stderr

---

## Comandi cross-platform

I comandi passano alla shell nativa del nodo. Usa la sintassi corretta per ogni OS:

| Azione | Windows | Linux / macOS |
|:---|:---|:---|
| Lista file | `dir` | `ls -la` |
| Hostname | `hostname` | `hostname` |
| Utente corrente | `whoami` | `whoami` |
| Uptime / info | `systeminfo` | `uptime` |
| Processi | `tasklist` | `ps aux --sort=-%cpu | head` |
| Spazio disco | `wmic logicaldisk get caption,freespace,size` | `df -h` |
| Rete | `ipconfig` | `ip addr` |
| Servizio (es.) | `sc query Spooler` | `systemctl status nginx` |

Per broadcast su nodi misti Windows+Linux, invia comandi compatibili con entrambi (es. `hostname`, `whoami`) oppure seleziona un nodo alla volta.

---

## Architettura

```
┌─────────────────────────────────────────────────────────────┐
│                     MASTER (Overlord)                       │
│  ZMQ ROUTER :5555  ·  UDP Beacon :5556  ·  Streamlit UI    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Monitoraggio │  │ Terminal     │  │ Log / Eventi     │  │
│  │ CPU/RAM/Disk │  │ Remoto Admin │  │ HMAC audit trail │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │ HMAC-SHA256 signed JSON frames    │
          ▼                 ▼                 ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │ Worker   │      │ Worker   │      │ Worker   │
    │ Win Srv  │      │ Linux DC │      │ macOS    │
    └──────────┘      └──────────┘      └──────────┘
```

### Tipi di messaggio

| Tipo | Direzione | Contenuto |
|:---|:---|:---|
| `tel` | Worker → Master | Telemetria + meta OS |
| `exec` | Master → Worker | Comando shell da eseguire |
| `exec_result` | Worker → Master | stdout, stderr, exit code |

Formato frame ZeroMQ: `[identity | "" | payload_json | hmac_signature]`

---

## Sicurezza

- Ogni frame e firmato **HMAC-SHA256** con chiave pre-condivisa
- Verifica **timing-safe** (`hmac.compare_digest`)
- Terminal admin richiede **chiave + conferma esplicita** sulla UI Master
- I comandi `exec` sono accettati solo se la firma e valida (solo il Master puo inviarli)
- **Non esporre** `SECRET_KEY` / `ADMIN_KEY` in repository pubblici
- **Non esporre** la porta 5555 su Internet senza VPN/tunnel

> Usare HYDRA solo su reti fidate. L'esecuzione remota di comandi e una funzione potente: trattala come accesso SSH/RDP.

---

## Configurazione

In cima a `main.py`:

```python
SECRET_KEY = b"HYDRA_SINGULARITY_ENCRYPT_2026"  # Cluster + firma HMAC
ADMIN_KEY = SECRET_KEY                           # Gate UI terminal admin
TCP_PORT = 5555
UDP_PORT = 5556
NODE_TIMEOUT_SEC = 10
CMD_TIMEOUT_SEC = 30
CMD_MAX_LEN = 4096
```

Master e Worker devono condividere la stessa `SECRET_KEY`.

---

## Troubleshooting

| Problema | Soluzione |
|:---|:---|
| Comando senza output | Attendi 1-2 refresh; verifica Worker online |
| `Access denied` su Windows | Riavvia Worker come Amministratore |
| Comando Linux fallisce su Windows | Usa sintassi corretta per OS target |
| EXEC TIMEOUT | Comando > 30s o nodo non risponde |
| Nodo sparisce | Timeout 10s — riavvia Worker |
| Porta 5555 occupata | Chiudi altri processi Streamlit/Python |

---

## Changelog

### v3.0.0 — Remote Exec & Datacenter
- Terminal remoto admin da Master (singolo nodo + broadcast)
- Esecuzione cross-platform: Windows cmd, Linux/macOS sh
- Gate admin con chiave + conferma
- Meta OS per ogni nodo (Windows/Linux/Darwin)
- Positioning home lab + datacenter
- Protocollo messaggi tipizzato (`tel`, `exec`, `exec_result`)

### v2.3.0 — UI Overhaul
- Redesign IBM Plex, componenti nativi Streamlit
- Tab monitoraggio, terminal styling

### v2.2.0 / v2.1.0
- Fix HMAC, discovery, auto-refresh

---

## Licenza

[MIT](LICENSE) — Leonardo Galli 2026
