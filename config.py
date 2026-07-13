"""Environment configuration for the Support & Compliance Pipeline."""

import os

from dotenv import load_dotenv


load_dotenv()


LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
USE_LLM = os.getenv("USE_LLM", "").lower() in {"1", "true", "yes"}
