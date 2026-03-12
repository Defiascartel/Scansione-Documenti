# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec — DDT Scanner Manager
#
# Build:
#   cd ddt-scanner-manager
#   pyinstaller ddt_scanner.spec
#
# Output: dist/DDT_Scanner_Manager.exe  (single file)

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Collect zbar DLLs bundled inside the pyzbar wheel (Windows only)
# ---------------------------------------------------------------------------
zbar_binaries = []
try:
    import pyzbar
    pyzbar_dir = Path(pyzbar.__file__).parent
    zbar_binaries = [(str(dll), ".") for dll in pyzbar_dir.glob("*.dll")]
except ImportError:
    pass

block_cipher = None

a = Analysis(
    ["src/main.py"],
    pathex=["."],
    binaries=zbar_binaries,
    datas=[
        ("assets", "assets"),          # icon, etc.
    ],
    hiddenimports=[
        # pyzbar
        "pyzbar.pyzbar",
        "pyzbar.wrapper",
        # OpenCV
        "cv2",
        "cv2.barcode",
        # watchdog Windows backend
        "watchdog.observers.winapi",
        "watchdog.events",
        # bcrypt
        "bcrypt",
        # PySide6 extras
        "PySide6.QtSvg",
        "PySide6.QtPrintSupport",
        "PySide6.QtPdf",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "notebook",
        "IPython",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="DDT_Scanner_Manager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,                 # no console window
    icon="assets/icon.ico" if Path("assets/icon.ico").exists() else None,
)
