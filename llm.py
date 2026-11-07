"""LLM and embedding factories.

Returns None when no API key is configured. Every agent checks for None and
falls back to a deterministic "offline" behaviour, so the whole graph can run
(and be tested) without an API key.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache

import config

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_llm():
    provider = config.LLM_PROVIDER.lower()
    try:
        if provider == "gemini" and os.getenv("GOOGLE_API_KEY"):
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model=config.LLM_MODEL, temperature=config.TEMPERATURE)
        if provider == "openai" and os.getenv("OPENAI_API_KEY"):
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=config.LLM_MODEL, temperature=config.TEMPERATURE)
    except ImportError as e:  # package for the chosen provider not installed
        log.warning("LLM provider package missing: %s", e)
    log.warning("No LLM configured (provider=%s). Running in OFFLINE mode.", provider)
    return None


@lru_cache(maxsize=1)
def get_embeddings():
    provider = config.LLM_PROVIDER.lower()
    try:
        if provider == "gemini" and os.getenv("GOOGLE_API_KEY"):
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            return GoogleGenerativeAIEmbeddings(model=config.EMBEDDING_MODEL)
        if provider == "openai" and os.getenv("OPENAI_API_KEY"):
            from langchain_openai import OpenAIEmbeddings
            return OpenAIEmbeddings(model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
    except ImportError as e:
        log.warning("Embedding provider package missing: %s", e)
    return None


def load_prompt(name: str) -> str:
    return (config.PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
