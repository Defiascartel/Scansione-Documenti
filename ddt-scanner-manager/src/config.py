"""Application configuration."""

import os
import sys
from pathlib import Path

# Base directories — when running as a PyInstaller bundle, use the directory
# containing the .exe so that data/logs persist across runs.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# Ensure data and logs directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Database
DB_PATH = DATA_DIR / "ddt_scanner.db"

# App info
APP_NAME = "DDT Scanner Manager"
APP_VERSION = "1.0.0"

# Default admin credentials (used only on first run)
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"

# Supported file extensions
PDF_EXTENSIONS = {".pdf"}
TIF_EXTENSIONS = {".tif", ".tiff"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}
SUPPORTED_EXTENSIONS = PDF_EXTENSIONS | TIF_EXTENSIONS | IMAGE_EXTENSIONS
