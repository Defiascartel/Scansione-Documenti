# DDT Scanner Manager

Applicazione desktop Windows per la digitalizzazione e archiviazione dei DDT (Documenti di Trasporto) scansionati nei punti vendita Unieuro.

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
File spostato in cartella "_confermati" + sidecar JSON
```

## Stack tecnologico

| Componente | Tecnologia |
|---|---|
| Linguaggio | Python 3.11+ |
| GUI | PySide6 (Qt6) |
| Barcode detection | pyzbar + opencv-python |
| Image processing | Pillow + opencv-python |
| PDF support | pdf2image |
| Database locale | SQLite |
| File monitoring | watchdog |
| Password hashing | bcrypt |
| Packaging | PyInstaller (pianificato) |

## Struttura progetto

```
ddt-scanner-manager/
├── src/
│   ├── main.py                  # Entry point
│   ├── config.py                # Configurazione app e percorsi
│   ├── database/
│   │   ├── models.py            # Schema SQLite
│   │   └── db.py                # CRUD + autenticazione
│   ├── ocr/
│   │   └── barcode_reader.py    # Estrazione barcode da immagini/PDF
│   ├── watcher/
│   │   └── folder_watcher.py    # Monitoraggio cartelle (watchdog + polling)
│   ├── gui/
│   │   └── login_dialog.py      # Dialog login PySide6
│   └── utils/
│       ├── file_manager.py      # Spostamento file + sidecar JSON
│       └── logger.py            # Logging su file con rotazione
└── tests/
    ├── test_db.py
    ├── test_barcode_reader.py
    ├── test_folder_watcher.py
    └── test_file_manager.py
```

## Installazione

```bash
pip install -r requirements.txt
```

> **Nota:** `pyzbar` richiede la libreria nativa **zbar**.
> Su Windows scaricare le DLL da [https://github.com/NaturalHistoryMuseum/pyzbar#windows](https://github.com/NaturalHistoryMuseum/pyzbar#windows)
> oppure installare tramite conda: `conda install -c conda-forge zbar`

## Avvio

```bash
py -m src.main
```

Al primo avvio viene creato automaticamente un utente **admin** con password **admin123** (da cambiare subito dal pannello admin).

## Test

```bash
py -m pytest tests/ -v
```

Risultato attuale: **40 test, tutti verdi**.

## Funzionalità implementate

### Fase 0 — Scaffolding
- Struttura directory completa
- `requirements.txt` e `CLAUDE.md`
- Configurazione percorsi e parametri app

### Fase 1 — Database e autenticazione
- Schema SQLite: `stores`, `users`, `watched_folders`, `operation_log`
- CRUD completo per negozi, utenti, cartelle monitorate
- Autenticazione con hashing bcrypt
- Creazione utente admin di default al primo avvio
- Dialog login PySide6

### Fase 2 — Motore OCR / Barcode
- Supporto formati: JPG, JPEG, PNG, TIFF, BMP, PDF
- 4 strategie di pre-processing in cascata:
  - Immagine originale
  - Scala di grigi
  - Threshold adattivo Gaussiano
  - Unsharp mask + OTSU threshold
- Deduplicazione barcode per pagina
- Supporto PDF multi-pagina via `pdf2image`

### Fase 3 — File Watcher e File Manager
- `FolderWatcher`: monitoraggio cartelle con watchdog + polling periodico (fallback ogni 30s)
- Aggiunta/rimozione dinamica di cartelle monitorate
- Delay di 2.5s dopo evento filesystem (attesa fine scrittura scanner)
- Deduplicazione file già visti
- `FileManager`: spostamento file in `_confermati` / `_scartati`
- Creazione automatica cartelle destinazione
- Risoluzione automatica conflitti di nome (suffisso timestamp)
- Sidecar JSON con barcode, operatore, negozio e timestamp

## Fasi pianificate

| Fase | Descrizione | Stato |
|---|---|---|
| 0 | Scaffolding | Completata |
| 1 | Database e autenticazione | Completata |
| 2 | OCR / Barcode | Completata |
| 3 | File Watcher + File Manager | Completata |
| 4 | GUI base (finestra principale a 3 pannelli) | Pianificata |
| 5 | Pannello Admin | Pianificata |
| 6 | Integrazione end-to-end e polish | Pianificata |
| 7 | Build .exe con PyInstaller | Pianificata |

## Ruoli utente

| Ruolo | Permessi |
|---|---|
| `admin` | Configura negozi, utenti, cartelle monitorate; accesso log completo |
| `operator` | Visualizza e lavora sui DDT del proprio negozio |

## Struttura cartelle di rete

```
\\server\scansioni\
  ├── negozio_001\
  │   ├── acquisti\             ← monitorata
  │   ├── acquisti_confermati\  ← destinazione automatica
  │   ├── resi\                 ← monitorata
  │   └── resi_confermati\
  └── negozio_002\
      └── ...
```
