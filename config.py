"""Central configuration, read from environment variables (.env)."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"
INDEX_DIR = ROOT / "data" / "faiss_index"
PROMPTS_DIR = ROOT / "prompts"

SCHEMES_PATH = DATA_DIR / "schemes.json"
PERSONAS_PATH = DATA_DIR / "personas.json"
DB_PATH = OUTPUT_DIR / "cases.db"

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")          # gemini | openai
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))

RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "20"))
MAX_VERIFIER_RETRIES = int(os.getenv("MAX_VERIFIER_RETRIES", "2"))
MAX_CLARIFICATION_ROUNDS = int(os.getenv("MAX_CLARIFICATION_ROUNDS", "1"))

# Fields without which the system asks a follow-up question instead of guessing.
CRITICAL_FIELDS = ["age", "state"]
# At least one of these must be known too.
CRITICAL_ANY_OF = ["occupation", "annual_family_income", "is_bpl"]

OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
