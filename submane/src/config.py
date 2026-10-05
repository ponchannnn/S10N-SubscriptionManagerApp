"""実API接続を行う際の設定．URLは環境変数で指定する．"""
import os
from pathlib import Path

USE_DUMMY_DATA = os.getenv("SUBMANE_USE_DUMMY_DATA", "true").lower() == "true"
API_BASE_URL = os.getenv("SUBMANE_API_BASE_URL", "").rstrip("/")
DATA_FILE = Path(os.getenv(
    "SUBMANE_DATA_FILE",
    str(Path(os.getenv("FLET_APP_STORAGE_DATA", str(Path(__file__).resolve().parents[1] / "data")))
        / "subscriptions.json"),
))
