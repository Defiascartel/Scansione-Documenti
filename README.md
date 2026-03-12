# DDT Scanner Manager

Applicazione desktop Windows per la digitalizzazione e archiviazione dei DDT (Documenti di Trasporto) scansionati nei punti vendita Unieuro.

## Installazione rapida

1. Copiare `DDT_Scanner_Manager.exe` in una cartella a scelta (es. `C:\DDT_Scanner`)
2. Lanciare l'exe — al primo avvio vengono create automaticamente:
   - `data\` — database SQLite con utenze, config e log
   - `logs\` — file di log con rotazione
3. Login con utente di default: **admin** / **admin123**
4. **Cambiare subito la password** da Impostazioni → Pannello Admin → tab Utenze

> L'exe è autocontenuto: non richiede Python, DLL o installazioni aggiuntive.
> Database e log vengono creati nella stessa cartella dell'exe.

## Panoramica

```
Scanner in negozio
    ↓
Deposita immagini in cartella di rete
    ↓
App monitora le cartelle configurate
    ↓
Nuovo file → estrazione barcode (OCR)
    ↓
Operatore vede documento + barcode estratti
    ↓
Operatore corregge (se necessario) e conferma
    ↓
File rinominato con barcode e spostato in cartella OUT + sidecar JSON
```

## Stack tecnologico

| Componente | Tecnologia |
|---|---|
| Linguaggio | Python 3.11+ |
| GUI | PySide6 (Qt6) |
| Barcode detection | OpenCV BarcodeDetector + pyzbar |
| Image processing | Pillow + opencv-python |
| PDF rendering | QPdfDocument (PySide6.QtPdf) |
| Database locale | SQLite |
| File monitoring | watchdog |
| Password hashing | bcrypt |
| Packaging | PyInstaller |

## Struttura progetto

```
ddt-scanner-manager/
├── src/
│   ├── main.py                   # Entry point
│   ├── config.py                 # Configurazione app e percorsi
│   ├── database/
│   │   ├── models.py             # Schema SQLite
│   │   └── db.py                 # CRUD + autenticazione
│   ├── ocr/
│   │   └── barcode_reader.py     # Estrazione barcode da immagini/PDF
│   ├── watcher/
│   │   └── folder_watcher.py     # Monitoraggio cartelle (watchdog + polling)
│   ├── gui/
│   │   ├── login_dialog.py       # Dialog login
│   │   ├── main_window.py        # Finestra principale 3 pannelli
│   │   ├── queue_panel.py        # Coda file in attesa
│   │   ├── document_viewer.py    # Viewer immagine/PDF
│   │   ├── barcode_editor.py     # Editor barcode + conferma/scarta
│   │   ├── admin_panel.py        # Pannello admin (negozi, utenti, cartelle, log)
│   │   └── styles.py             # Stylesheet QSS globale
│   └── utils/
│       ├── file_manager.py       # Spostamento file + sidecar JSON
│       └── logger.py             # Logging su file con rotazione
├── tests/
│   ├── test_db.py
│   ├── test_barcode_reader.py
│   ├── test_folder_watcher.py
│   └── test_file_manager.py
├── ddt_scanner.spec              # Configurazione PyInstaller
├── build.bat                     # Script build .exe
├── pyproject.toml
└── requirements.txt
```

## Installazione

```bash
pip install -r requirements.txt
```

> **Nota:** `pyzbar` richiede la libreria nativa **zbar**.
> Su Windows le DLL sono incluse automaticamente nel wheel pip.
> In caso di problemi: [https://github.com/NaturalHistoryMuseum/pyzbar#windows](https://github.com/NaturalHistoryMuseum/pyzbar#windows)

## Avvio

```bash
py -m src.main
```

Al primo avvio viene creato automaticamente un utente **admin** con password **admin123**.
Cambiare la password subito dal Pannello Admin → tab Utenze.

## Test

```bash
py -m pytest tests/ -v
```

Risultato attuale: **39 test, tutti verdi**.

## Build .exe

```bash
pip install pyinstaller
pyinstaller ddt_scanner.spec
```

Output: `dist\DDT_Scanner_Manager.exe` (singolo file, ~105 MB)

> **Note build:**
> - L'exe è self-contained (onefile): un unico file da distribuire
> - Il rendering PDF usa `QPdfDocument` (incluso in PySide6) — nessuna dipendenza esterna richiesta

---

## Funzionalità

### Autenticazione e ruoli
- Login con username e password (bcrypt)
- Ruolo **admin**: configura negozi, utenti e cartelle; visualizza log completo
- Ruolo **operator**: lavora sui DDT del proprio negozio
- Utente admin di default creato al primo avvio

### Monitoraggio cartelle
- Rilevamento nuovi file in tempo reale tramite watchdog
- Polling periodico (ogni 30s) come fallback per path di rete
- Delay di 2.5s dopo evento filesystem (attesa fine scrittura scanner)
- Filtro automatico sulle estensioni supportate: JPG, JPEG, PNG, TIFF, BMP, PDF
- Aggiunta/rimozione dinamica delle cartelle senza riavvio

### Rilevamento barcode
- Strategia ibrida: OpenCV `BarcodeDetector` localizza il barcode, pyzbar decodifica il crop (massima affidabilità su Code128)
- ROI intelligente: scansione prima del terzo superiore del documento, poi full-page come fallback
- 4 strategie di pre-processing in cascata (originale → grayscale → adaptive threshold → sharpen+OTSU)
- Deduplicazione barcode sulla stessa pagina
- Rendering PDF nativo via `QPdfDocument` (PySide6.QtPdf) a 400 DPI — nessuna dipendenza esterna (Poppler non richiesto)
- Composizione su sfondo bianco per gestire trasparenze PDF
- Scansione in background thread (GUI mai bloccata)

### Interfaccia operatore
- Layout a 3 pannelli ridimensionabili: **coda** | **viewer** | **barcode editor**
- Viewer con zoom (rotella mouse), pan (drag), rotazione 90°, fit-to-window
- Lista barcode editabile inline: modifica, aggiungi, rimuovi
- Pulsante **Conferma** (verde) → rinomina con barcode, sposta in cartella OUT + sidecar JSON + log DB
- Pulsante **Scarta** (rosso) → sposta in cartella scartati + sidecar JSON + log DB
- Retry automatico (4 tentativi) se il file è ancora bloccato dallo scanner
- System tray con notifiche balloon per nuovi file in coda

### Pannello Admin
- Tab **Negozi**: crea, modifica, elimina negozi
- Tab **Utenze**: crea, modifica utenti; assegna negozio e ruolo; attiva/disattiva
- Tab **Cartelle**: per negozio, aggiungi/rimuovi cartelle monitorate con browser e validazione path; reload istantaneo del watcher
- Tab **Log Operazioni**: storico con filtro per negozio, colori per azione

### Archiviazione
- L'admin configura cartella IN (sorgente) e OUT (destinazione) per ogni tipo documento
- File confermati rinominati con i barcode (es. `8016474743.pdf`, `8016474743_8016474744.pdf`)
- Creazione automatica cartelle destinazione se non esistono
- Risoluzione conflitti di nome con suffisso timestamp
- Sidecar `.json` con barcode confermati, operatore, negozio e timestamp

---

## Struttura cartelle di rete (esempio)

```
\\server\scansioni\
  ├── negozio_001\
  │   ├── acquisti\               ← cartella IN (monitorata)
  │   ├── acquisti_confermati\    ← cartella OUT (configurata dall'admin)
  │   ├── resi\                   ← cartella IN
  │   └── resi_confermati\        ← cartella OUT
  └── negozio_002\
      └── ...
```

## Fasi di sviluppo

| Fase | Descrizione | Stato |
|---|---|---|
| 0 | Scaffolding | Completata |
| 1 | Database e autenticazione | Completata |
| 2 | OCR / Barcode | Completata |
| 3 | File Watcher + File Manager | Completata |
| 4 | GUI base (login + finestra principale 3 pannelli) | Completata |
| 5 | Pannello Admin | Completata |
| 6 | Integrazione, polish, system tray, stylesheet | Completata |
| 7 | Build .exe con PyInstaller | Completata |

## Evoluzioni future (V2)

- Integrazione SAP via RFC/BAPI per invio barcode confermati
- Dashboard web per supervisori (statistiche, volumi, SLA)
- OCR avanzato con modelli ML per DDT specifici
- Notifiche push/email per file non processati da X ore
- Multi-negozio per singolo operatore
