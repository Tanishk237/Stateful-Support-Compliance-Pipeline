"""Environment configuration for the Support & Compliance Pipeline."""

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


LLM_API_KEY = os.getenv("LLM_API_KEY", "")
# The OpenAI client also supports compatible providers through a custom base URL.
# Leave this blank to use the OpenAI default endpoint.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()
USE_LLM = os.getenv("USE_LLM", "").lower() in {"1", "true", "yes"}

PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    str(PROJECT_ROOT / "data" / "support_pipeline.db"),
)
