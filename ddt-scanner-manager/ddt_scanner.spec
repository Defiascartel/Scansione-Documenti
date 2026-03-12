# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec — DDT Scanner Manager
#
# Prerequisiti prima di eseguire:
#   pip install pyinstaller pyzbar opencv-python Pillow PySide6 bcrypt watchdog pdf2image
#
# Build:
#   cd ddt-scanner-manager
#   pyinstaller ddt_scanner.spec
#
# Output: dist/DDT_Scanner_Manager/

import sys
from pathlib import Path
import pyzbar

# ---------------------------------------------------------------------------
# Collect zbar DLLs bundled inside the pyzbar wheel (Windows only)
# ---------------------------------------------------------------------------
pyzbar_dir = Path(pyzbar.__file__).parent
zbar_binaries = [(str(dll), ".") for dll in pyzbar_dir.glob("*.dll")]

block_cipher = None

a = Analysis(
    ["src/main.py"],
    pathex=["."],
    binaries=zbar_binaries,
    datas=[
        ("assets", "assets"),          # icon, etc.
        ("src", "src"),                # include full src package
    ],
    hiddenimports=[
        # pyzbar
        "pyzbar.pyzbar",
        "pyzbar.wrapper",
        "pyzbar.zbar",
        # PIL / Pillow
        "PIL._imaging",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFilter",
        # OpenCV
        "cv2",
        # watchdog Windows backend
        "watchdog.observers.winapi",
        "watchdog.events",
        # bcrypt
        "bcrypt",
        # PySide6 extras
        "PySide6.QtSvg",
        "PySide6.QtPrintSupport",
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
    [],
    exclude_binaries=True,
    name="DDT_Scanner_Manager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                 # no console window
    icon="assets/icon.ico",        # comment out if icon.ico is missing
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DDT_Scanner_Manager",
)
