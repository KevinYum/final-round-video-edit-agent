import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ENV = os.getenv("ENV", "development")
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./storage"))

# OpenAI / LLM
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
