# DDT Scanner Manager — Analisi e Piano di Sviluppo per Claude Code

## 1. Panoramica del Progetto

**Nome progetto:** DDT Scanner Manager
**Obiettivo:** Digitalizzare il processo di acquisizione, verifica OCR e archiviazione dei DDT (Documenti di Trasporto) scansionati nei punti vendita Unieuro.
**Output:** Applicazione desktop `.exe` per Windows.

### Workflow operativo

```
Scanner in negozio
    ↓
Deposita immagini in cartella di rete alberata
    ↓
App monitora le cartelle configurate
    ↓
Nuovo file → OCR per estrazione barcode
    ↓
Operatore vede documento + barcode estratti
    ↓
Operatore corregge (se necessario) e conferma
    ↓
File spostato in cartella speculare "_confermati"
    ↓
Processo completato
```

---

## 2. Analisi Funzionale

### 2.1 Gestione Utenze e Negozi

| Requisito | Dettaglio |
|-----------|-----------|
| Autenticazione | Login per utenza (username + password) |
| Ruoli | **Admin** (configura tutto), **Operatore** (lavora sui DDT) |
| Associazione | Ogni utenza è legata a 1 negozio |
| Configurazione negozio | Nome, codice, lista cartelle da monitorare |
| Configurazione cartelle | Path sorgente → path destinazione (derivata automaticamente con suffisso `_confermati`) |

**Esempio struttura cartelle:**

```
\\server\scansioni\
  ├── negozio_001\
  │   ├── acquisti\          ← monitorata
  │   ├── acquisti_confermati\  ← destinazione automatica
  │   ├── resi\              ← monitorata
  │   ├── resi_confermati\      ← destinazione automatica
  │   ├── altro\
  │   └── altro_confermati\
  ├── negozio_002\
  │   ├── acquisti\
  │   └── ...
```

### 2.2 Monitoraggio Cartelle

| Requisito | Dettaglio |
|-----------|-----------|
| Meccanismo | File system watcher + polling periodico come fallback |
| Filtro file | Solo immagini: `.jpg`, `.jpeg`, `.png`, `.tiff`, `.bmp`, `.pdf` |
| Coda di lavoro | I file rilevati entrano in una coda FIFO visibile all'operatore |
| Stato file | `nuovo` → `in_lavorazione` → `confermato` |
| Lock file | Evitare che due operatori lavorino sullo stesso file |

### 2.3 OCR e Estrazione Barcode

| Requisito | Dettaglio |
|-----------|-----------|
| Tipo barcode | 1D (Code 128, EAN-13, etc.) e 2D (QR, DataMatrix) |
| Libreria suggerita | `pyzbar` (wrapper di zbar) + `Pillow` per pre-processing |
| Fallback OCR | Tesseract OCR per testo generico se servisse in futuro |
| Pre-processing | Conversione grayscale, threshold adattivo, deskew per migliorare il riconoscimento |
| Output | Lista di barcode trovati con valore decodificato e tipo |

### 2.4 Interfaccia Operatore

**Schermata principale:**
- Sidebar sinistra: coda dei file in attesa (con contatore per cartella)
- Area centrale: anteprima del documento scansionato (zoom, pan, rotazione)
- Pannello destro: lista barcode rilevati (editabili) + pulsanti azione

**Azioni operatore:**
- Visualizzare il documento
- Vedere i barcode trovati dall'OCR
- Modificare/aggiungere/rimuovere barcode manualmente
- Confermare → il file viene spostato nella cartella `_confermati`
- Scartare → il file viene spostato in una cartella `_scartati` (opzionale)

### 2.5 Spostamento e Archiviazione

| Requisito | Dettaglio |
|-----------|-----------|
| Regola naming destinazione | `{cartella_sorgente}_confermati` (creata automaticamente se non esiste) |
| Rinominazione file | Opzionale: prefisso con timestamp o barcode principale |
| Log | Ogni operazione viene loggata: chi, quando, quale file, barcode confermati |
| Sidecar JSON | Accanto al file spostato, creare un `.json` con i metadati (barcode, operatore, timestamp) |

---

## 3. Scelte Tecniche

### 3.1 Stack Tecnologico

| Componente | Tecnologia | Motivazione |
|------------|-----------|-------------|
| **Linguaggio** | Python 3.11+ | Ecosistema OCR maturo, packaging .exe con PyInstaller |
| **GUI Framework** | PySide6 (Qt6) | UI nativa Windows, performante, viewer immagini integrato |
| **Barcode Detection** | `pyzbar` + `opencv-python` | Riconoscimento multi-formato robusto |
| **OCR Backup** | `pytesseract` (opzionale) | Per testo aggiuntivo se necessario |
| **Image Processing** | `Pillow` + `opencv-python` | Pre-processing, rotazione, zoom |
| **Database locale** | SQLite | Configurazione utenze, negozi, log operazioni |
| **File Watcher** | `watchdog` | Monitoraggio cartelle cross-platform |
| **Packaging** | PyInstaller | Genera `.exe` standalone |
| **Config** | File `config.json` o SQLite | Parametri app e mappatura cartelle |

### 3.2 Architettura

```
┌─────────────────────────────────────────────┐
│                  GUI (PySide6)               │
│  ┌──────────┐ ┌──────────────┐ ┌──────────┐ │
│  │  Coda    │ │  Viewer      │ │ Barcode  │ │
│  │  File    │ │  Documento   │ │ Editor   │ │
│  └────┬─────┘ └──────┬───────┘ └────┬─────┘ │
│       │              │              │        │
│  ┌────┴──────────────┴──────────────┴─────┐  │
│  │          Controller Principale         │  │
│  └────┬──────────────┬──────────────┬─────┘  │
│       │              │              │        │
│  ┌────┴─────┐  ┌─────┴─────┐ ┌─────┴──────┐ │
│  │ Watcher  │  │  OCR /    │ │  File      │ │
│  │ Service  │  │  Barcode  │ │  Manager   │ │
│  └──────────┘  └───────────┘ └────────────┘  │
│       │                            │         │
│  ┌────┴────────────────────────────┴───────┐ │
│  │            SQLite Database              │ │
│  │  (utenze, negozi, config, log)          │ │
│  └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### 3.3 Struttura Database SQLite

```sql
-- Negozi
CREATE TABLE stores (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,      -- es. "001"
    name TEXT NOT NULL,             -- es. "Bologna Centro"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Utenze
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'operator',   -- 'admin' | 'operator'
    store_id INTEGER REFERENCES stores(id),
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cartelle monitorate per negozio
CREATE TABLE watched_folders (
    id INTEGER PRIMARY KEY,
    store_id INTEGER REFERENCES stores(id),
    source_path TEXT NOT NULL,      -- es. "\\server\scansioni\negozio_001\acquisti"
    folder_type TEXT NOT NULL,      -- es. "acquisti", "resi"
    is_active BOOLEAN DEFAULT 1
);

-- Log operazioni
CREATE TABLE operation_log (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    store_id INTEGER REFERENCES stores(id),
    source_path TEXT NOT NULL,
    dest_path TEXT NOT NULL,
    filename TEXT NOT NULL,
    barcodes_json TEXT,             -- JSON array dei barcode confermati
    action TEXT NOT NULL,           -- 'confirmed' | 'discarded'
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 4. Piano di Sviluppo (Fasi per Claude Code)

L'approccio è **incrementale**: ogni fase produce un deliverable funzionante e testabile.

### Fase 0 — Scaffolding progetto
**Effort stimato: 1 sessione Claude Code**

- [ ] Creare struttura directory del progetto
- [ ] Setup `pyproject.toml` o `requirements.txt`
- [ ] Creare `CLAUDE.md` con contesto progetto e convenzioni
- [ ] Struttura base:

```
ddt-scanner-manager/
├── CLAUDE.md
├── requirements.txt
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── config.py               # Configurazione app
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py           # Schema DB
│   │   └── db.py               # Connessione e CRUD
│   ├── watcher/
│   │   ├── __init__.py
│   │   └── folder_watcher.py   # Monitoraggio cartelle
│   ├── ocr/
│   │   ├── __init__.py
│   │   └── barcode_reader.py   # Estrazione barcode
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py      # Finestra principale
│   │   ├── login_dialog.py     # Dialog login
│   │   ├── admin_panel.py      # Pannello admin
│   │   ├── document_viewer.py  # Viewer immagine
│   │   ├── barcode_editor.py   # Editor barcode
│   │   └── queue_panel.py      # Coda file
│   └── utils/
│       ├── __init__.py
│       ├── file_manager.py     # Spostamento file + sidecar JSON
│       └── logger.py           # Logging applicativo
├── tests/
│   ├── test_barcode_reader.py
│   ├── test_folder_watcher.py
│   └── test_file_manager.py
├── assets/
│   └── icon.ico
└── build/
    └── build_exe.spec          # Config PyInstaller
```

---

### Fase 1 — Database e Gestione Utenze
**Effort stimato: 1-2 sessioni Claude Code**

**Deliverable:** Backend CRUD completo per utenze, negozi, cartelle.

- [ ] Implementare `database/models.py` con creazione tabelle SQLite
- [ ] Implementare `database/db.py` con funzioni CRUD:
  - `create_store()`, `list_stores()`, `update_store()`, `delete_store()`
  - `create_user()`, `authenticate()`, `list_users()`, `update_user()`
  - `add_watched_folder()`, `list_watched_folders(store_id)`, `remove_watched_folder()`
  - `log_operation()`
- [ ] Hashing password con `bcrypt`
- [ ] Creazione utente admin di default al primo avvio
- [ ] Unit test per tutte le operazioni CRUD

---

### Fase 2 — Motore OCR / Barcode
**Effort stimato: 1-2 sessioni Claude Code**

**Deliverable:** Modulo che prende un file immagine e restituisce lista barcode.

- [ ] Implementare `ocr/barcode_reader.py`:
  - Caricamento immagine (supporto jpg, png, tiff, pdf prima pagina)
  - Pre-processing: grayscale → threshold adattivo → deskew
  - Scansione barcode con `pyzbar`
  - Output: `List[BarcodeResult]` con `value`, `type`, `bounding_box`
- [ ] Gestione PDF multi-pagina (conversione pagine in immagini)
- [ ] Test con immagini campione (barcode puliti e rumorosi)
- [ ] Tuning parametri pre-processing per massimizzare detection rate

---

### Fase 3 — File Watcher
**Effort stimato: 1 sessione Claude Code**

**Deliverable:** Servizio che monitora cartelle e alimenta una coda di lavoro.

- [ ] Implementare `watcher/folder_watcher.py`:
  - Usa `watchdog` per eventi filesystem
  - Polling periodico come fallback (ogni 30 secondi)
  - Filtro per estensioni supportate
  - Alimenta coda thread-safe (`queue.Queue`)
  - Gestisce aggiunta/rimozione dinamica di cartelle
- [ ] Implementare `utils/file_manager.py`:
  - `move_to_confirmed(source, dest_base)` → sposta file + crea sidecar JSON
  - `move_to_discarded(source, dest_base)` → sposta file scartato
  - Creazione automatica cartelle destinazione
  - Gestione conflitti nomi (aggiunta timestamp se duplicato)
- [ ] Test con cartelle temporanee

---

### Fase 4 — GUI Base (Login + Main Window)
**Effort stimato: 2-3 sessioni Claude Code**

**Deliverable:** Applicazione con login e finestra principale con layout a 3 pannelli.

- [ ] `gui/login_dialog.py`: dialog login con username/password
- [ ] `gui/main_window.py`: finestra principale con:
  - Menu bar (File, Impostazioni, Info)
  - Status bar con info utente e negozio
  - Layout a 3 colonne (splitter ridimensionabili)
- [ ] `gui/queue_panel.py`: lista file in coda raggruppati per cartella sorgente
  - Contatore file per cartella
  - Click su file → carica nel viewer
  - Indicatore stato (nuovo, in lavorazione)
- [ ] `gui/document_viewer.py`: visualizzatore immagine con:
  - Zoom in/out (rotella mouse)
  - Pan (drag)
  - Rotazione 90°
  - Fit to window
  - Supporto PDF (render prima pagina)
- [ ] `gui/barcode_editor.py`: pannello barcode con:
  - Lista barcode rilevati (editabili inline)
  - Pulsante "Aggiungi barcode"
  - Pulsante "Rimuovi barcode"
  - Pulsante "Conferma" (verde, prominente)
  - Pulsante "Scarta" (rosso, secondario)
- [ ] Integrazione controller: click su file → OCR → mostra risultati → azioni

---

### Fase 5 — Pannello Admin
**Effort stimato: 1-2 sessioni Claude Code**

**Deliverable:** Interfaccia admin per configurare negozi, utenze, cartelle.

- [ ] `gui/admin_panel.py` accessibile solo con ruolo admin:
  - Tab "Negozi": CRUD negozi
  - Tab "Utenze": CRUD utenze con assegnazione negozio
  - Tab "Cartelle": per ogni negozio, lista cartelle monitorate + aggiungi/rimuovi
  - Tab "Log": visualizzazione log operazioni con filtri (data, negozio, operatore)
- [ ] Validazione path cartelle (verifica esistenza)
- [ ] Reload dinamico watcher quando cambiano le cartelle configurate

---

### Fase 6 — Integrazione End-to-End e Polish
**Effort stimato: 2-3 sessioni Claude Code**

**Deliverable:** Applicazione completa e funzionante.

- [ ] Integrazione completa di tutti i moduli
- [ ] Threading corretto: watcher in thread separato, OCR in thread separato, GUI in main thread
- [ ] Signal/slot Qt per comunicazione thread-safe tra watcher → GUI → OCR
- [ ] Gestione errori robusti (file locked, path non raggiungibile, OCR fallito)
- [ ] Logging su file (`logs/app.log`) con rotazione
- [ ] Notifiche: suono o notifica desktop quando arriva nuovo file
- [ ] Icona nella system tray (opzionale)
- [ ] Temi: stile pulito e professionale (Qt stylesheet)
- [ ] Test integrazione completo

---

### Fase 7 — Build e Distribuzione
**Effort stimato: 1 sessione Claude Code**

**Deliverable:** File `.exe` distribuibile.

- [ ] Configurare PyInstaller:
  - Single file o single directory (consigliato directory per performance)
  - Inclusione DLL zbar
  - Inclusione assets (icona, etc.)
  - Esclusione moduli non necessari
- [ ] Creare script `build.bat` / `build.sh`
- [ ] Test `.exe` su macchina pulita
- [ ] Creare installer con NSIS o Inno Setup (opzionale)
- [ ] Documentazione utente base

---

## 5. CLAUDE.md Suggerito

```markdown
# DDT Scanner Manager

## Contesto
App desktop Windows (.exe) per gestione DDT scansionati nei negozi Unieuro.
Workflow: Scanner → Cartella → OCR barcode → Verifica operatore → Archiviazione.

## Stack
- Python 3.11+, PySide6, pyzbar, opencv-python, watchdog, SQLite, PyInstaller
- GUI: PySide6 con layout a 3 pannelli (coda | viewer | barcode editor)
- DB: SQLite locale per utenze, config, log

## Convenzioni
- Lingua codice: inglese (variabili, funzioni, commenti)
- Lingua UI: italiano
- Type hints su tutte le funzioni pubbliche
- Docstring Google-style
- Test con pytest nella cartella tests/
- Logging con modulo logging standard (non print)

## Struttura
- src/database/ → modelli e CRUD SQLite
- src/watcher/ → monitoraggio cartelle con watchdog
- src/ocr/ → estrazione barcode con pyzbar
- src/gui/ → interfaccia PySide6
- src/utils/ → file management, logging

## Regole importanti
- Mai bloccare il main thread (GUI): operazioni IO e OCR in thread separati
- Usare signal/slot Qt per comunicazione inter-thread
- Il path destinazione si deriva dal sorgente: "{nome_cartella}_confermati"
- Ogni file confermato produce un sidecar .json con metadati
- Password hashate con bcrypt, mai in chiaro
```

---

## 6. Rischi e Mitigazioni

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| OCR non rileva barcode su scansioni di bassa qualità | Alto | Pre-processing aggressivo + editing manuale come fallback |
| Path di rete non raggiungibili | Medio | Polling con retry + notifica errore all'operatore |
| File locked dallo scanner durante la scrittura | Medio | Delay di 2-3 secondi dopo evento filesystem prima di processare |
| PyInstaller non include DLL zbar | Medio | Configurazione spec file con hidden imports e binary includes |
| Conflitti se più operatori vedono lo stesso file | Basso | Lock su file in lavorazione (flag in DB o rename temporaneo) |
| Performance con molti file in coda | Basso | Paginazione coda + OCR on-demand (solo al click) |

---

## 7. Stima Effort Totale

| Fase | Sessioni Claude Code stimate |
|------|-------------------------------|
| Fase 0 — Scaffolding | 1 |
| Fase 1 — Database e Utenze | 1-2 |
| Fase 2 — OCR / Barcode | 1-2 |
| Fase 3 — File Watcher | 1 |
| Fase 4 — GUI Base | 2-3 |
| Fase 5 — Pannello Admin | 1-2 |
| Fase 6 — Integrazione e Polish | 2-3 |
| Fase 7 — Build .exe | 1 |
| **Totale** | **10-15 sessioni** |

> Ogni "sessione Claude Code" corrisponde a circa 1-2 ore di lavoro iterativo con Claude Code, includendo test e debugging.

---

## 8. Evoluzioni Future (V2)

- Integrazione con SAP: invio barcode confermati a SAP via RFC/BAPI
- Dashboard web per supervisori (statistiche, volumi, SLA)
- OCR avanzato con modelli ML per DDT specifici
- Notifiche push/email per file non processati da X ore
- Multi-tenant cloud con sync cartelle via agent locale
