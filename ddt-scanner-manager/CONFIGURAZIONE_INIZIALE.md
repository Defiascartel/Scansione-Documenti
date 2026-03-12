# DDT Scanner Manager — Guida alla Configurazione Iniziale

Questa guida descrive i passi necessari per configurare l'applicazione al primo avvio e renderla operativa per un nuovo punto vendita.

---

## Prerequisiti

### Macchina su cui gira l'applicazione
- Windows 10 / Windows 11 (64-bit)
- Connessione di rete al server dove risiedono le cartelle di scansione
- Accesso in lettura/scrittura alle cartelle di rete del negozio

### Cartelle di rete (da predisporre prima dell'avvio)
Le cartelle sorgente devono esistere sul server **prima** di essere configurate nell'app. L'applicazione creerà automaticamente le cartelle `_confermati` e `_scartati` al momento del primo utilizzo.

Struttura consigliata:
```
\\server\scansioni\
  └── negozio_XXX\
      ├── acquisti\
      ├── resi\
      └── altro\          (opzionale)
```

---

## Passo 1 — Primo avvio

Avviare l'applicazione (`DDT_Scanner_Manager.exe` oppure `py -m src.main`).

Al primo avvio vengono create automaticamente:
- Il database locale (`data\ddt_scanner.db`)
- L'utente amministratore di default

**Credenziali di accesso iniziali:**

| Campo | Valore |
|---|---|
| Username | `admin` |
| Password | `admin123` |

> ⚠️ **Cambiare la password admin immediatamente** (vedi Passo 2).

---

## Passo 2 — Cambio password amministratore

1. Accedere con `admin` / `admin123`
2. Dal menu in alto: **Impostazioni → Pannello Admin**
3. Aprire la tab **Utenze**
4. Selezionare l'utente `admin` e cliccare **✎ Modifica**
5. Inserire la nuova password nel campo **Password** e confermare con **OK**

---

## Passo 3 — Creazione del negozio

1. Nel Pannello Admin, aprire la tab **Negozi**
2. Cliccare **+ Aggiungi**
3. Compilare i campi:

| Campo | Esempio | Note |
|---|---|---|
| Codice | `001` | Codice univoco del punto vendita |
| Nome | `Bologna Centro` | Nome descrittivo |

4. Cliccare **OK**

Il negozio appare nella lista. Ripetere per ogni punto vendita da configurare.

---

## Passo 4 — Creazione utenti operatori

Per ogni operatore del negozio:

1. Nel Pannello Admin, aprire la tab **Utenze**
2. Cliccare **+ Aggiungi**
3. Compilare i campi:

| Campo | Valore | Note |
|---|---|---|
| Username | es. `mario.rossi` | Usato per il login |
| Password | a scelta | Minimo consigliato: 8 caratteri |
| Ruolo | `operator` | Gli operatori vedono solo il proprio negozio |
| Negozio | selezionare dalla lista | Assegna il negozio creato al Passo 3 |
| Utente attivo | ✔ spuntato | Deselezionare per disabilitare l'accesso |

4. Cliccare **OK**

> **Nota:** Un utente con ruolo `admin` non ha un negozio assegnato e vede tutte le cartelle di tutti i negozi.

---

## Passo 5 — Configurazione cartelle monitorate

1. Nel Pannello Admin, aprire la tab **Cartelle**
2. Selezionare il negozio dal menu a tendina
3. Cliccare **+ Aggiungi cartella**
4. Compilare i campi:

| Campo | Esempio | Note |
|---|---|---|
| Negozio | `Bologna Centro (001)` | Pre-selezionato dal filtro |
| Percorso | `\\server\scansioni\negozio_001\acquisti` | Usare il pulsante **…** per navigare |
| Tipo cartella | `acquisti` | Etichetta descrittiva (usata nei log) |

5. Cliccare **OK**

Ripetere per ogni cartella da monitorare (es. `resi`, `altro`).

> Se il percorso non è raggiungibile al momento della configurazione, l'applicazione chiederà conferma prima di salvare. La cartella verrà comunque aggiunta e monitorata non appena il percorso di rete diventerà disponibile.

---

## Passo 6 — Verifica della configurazione

Prima di chiudere il Pannello Admin, verificare:

- [ ] Il negozio è presente nella tab **Negozi**
- [ ] Gli operatori sono presenti nella tab **Utenze** con il negozio corretto assegnato
- [ ] Le cartelle sono presenti nella tab **Cartelle** con i percorsi corretti
- [ ] Accedendo con un account operatore, l'applicazione mostra nella status bar il nome del negozio assegnato

---

## Passo 7 — Test operativo

1. Copiare manualmente un file immagine (JPG, PNG, TIFF o PDF) nella cartella sorgente configurata
2. Entro pochi secondi il file compare nel pannello **Coda documenti** a sinistra
3. Cliccare sul file: il documento viene mostrato al centro, i barcode estratti appaiono a destra
4. Cliccare **✓ Conferma** oppure **✗ Scarta**
5. Verificare che nella cartella `_confermati` (o `_scartati`) siano presenti:
   - Il file originale
   - Il file `.json` con i metadati (barcode, operatore, timestamp)

---

## Riepilogo credenziali e percorsi utili

| Elemento | Valore / Percorso |
|---|---|
| Eseguibile | `DDT_Scanner_Manager.exe` |
| Database | `data\ddt_scanner.db` |
| Log applicativo | `logs\app.log` |
| Cartella confermati | `{cartella_sorgente}_confermati\` |
| Cartella scartati | `{cartella_sorgente}_scartati\` |
| Utente admin default | `admin` / `admin123` |

---

## Problemi comuni

| Problema | Possibile causa | Soluzione |
|---|---|---|
| Il file non appare in coda | Il percorso di rete non è raggiungibile | Verificare la connessione al server; il polling riproverà ogni 30 secondi |
| "File bloccato dallo scanner" | Lo scanner sta ancora scrivendo | Attendere qualche secondo e cliccare di nuovo Conferma |
| Nessun barcode rilevato | Scansione a bassa qualità o orientamento errato | Usare il pulsante **↻** per ruotare; inserire il barcode manualmente con **+ Aggiungi** |
| Errore database all'avvio | Cartella `data\` non scrivibile | Verificare i permessi sulla cartella dell'applicazione |
| Anteprima PDF non disponibile | Versione PySide6 senza modulo QtPdf | Aggiornare PySide6: `pip install --upgrade PySide6` |
