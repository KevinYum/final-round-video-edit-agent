import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ENV = os.getenv("ENV", "development")
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./storage"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
