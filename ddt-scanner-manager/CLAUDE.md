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
