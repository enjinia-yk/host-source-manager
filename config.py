import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
REPO_DIR = BASE_DIR / "repo"
DB_PATH = DATA_DIR / "sources.db"

APP_HOST = "0.0.0.0"
APP_PORT = 8080
APP_TITLE = "ホストソース管理システム"
APP_STORAGE_SECRET = os.getenv("APP_STORAGE_SECRET", "hsm-dev-secret")
