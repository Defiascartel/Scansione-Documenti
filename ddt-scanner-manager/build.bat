@echo off
:: ============================================================
:: DDT Scanner Manager — Build script
:: Genera dist\DDT_Scanner_Manager\ pronto per la distribuzione
:: ============================================================

setlocal

:: Vai nella directory del progetto
cd /d "%~dp0"

echo.
echo ======================================
echo  DDT Scanner Manager - Build .exe
echo ======================================
echo.

:: Verifica Python
where py >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Python non trovato. Installare Python 3.11+ e riprovare.
    pause & exit /b 1
)

echo [1/4] Installazione dipendenze...
py -m pip install -r requirements.txt pyinstaller --quiet
if errorlevel 1 (
    echo [ERRORE] Installazione dipendenze fallita.
    pause & exit /b 1
)

echo [2/4] Pulizia build precedente...
if exist dist\DDT_Scanner_Manager rmdir /s /q dist\DDT_Scanner_Manager
if exist build\_pyinstaller rmdir /s /q build\_pyinstaller

echo [3/4] Esecuzione PyInstaller...
py -m PyInstaller ddt_scanner.spec --workpath build\_pyinstaller --distpath dist --noconfirm
if errorlevel 1 (
    echo [ERRORE] PyInstaller fallito. Controlla i messaggi sopra.
    pause & exit /b 1
)

echo [4/4] Build completata!
echo.
echo Output: dist\DDT_Scanner_Manager\DDT_Scanner_Manager.exe
echo.

:: Note post-build
echo ============================================================
echo  NOTE IMPORTANTI
echo ============================================================
echo.
echo  1. Se pyzbar non rileva i barcode, verificare la presenza
echo     delle DLL zbar nella cartella dist\DDT_Scanner_Manager\
echo     (libzbar-64.dll e libiconv.dll).
echo     Se mancanti, scaricarle da:
echo     https://github.com/NaturalHistoryMuseum/pyzbar#windows
echo     e copiarle nella cartella dist\DDT_Scanner_Manager\
echo.
echo  2. Per pdf2image, assicurarsi che Poppler sia installato
echo     e nel PATH, oppure copiare la cartella poppler\bin
echo     dentro dist\DDT_Scanner_Manager\
echo.
echo  3. Il file ddt_scanner.db viene creato automaticamente
echo     alla prima esecuzione nella cartella data\
echo.
echo ============================================================

pause
