"""Agent 2 - Retrieve: CitizenProfile -> candidate schemes.

Step 1: hard metadata filter (central schemes + schemes of the user's state).
Step 2: if a FAISS index exists, rank by semantic similarity to a query built
        from the profile and keep the top-k. Without an index, keep everything
        that passed the filter (fine for a 40-scheme knowledge base).
"""
from __future__ import annotations

import logging
import time

import config
from knowledge_base import load_schemes, scheme_text
from llm import get_embeddings
from schemas import CitizenProfile, SchemeDoc
from state import NavigatorState

log = logging.getLogger(__name__)
_index = None


def _load_index():
    global _index
    if _index is None and (config.INDEX_DIR / "index.faiss").exists():
        emb = get_embeddings()
        if emb is not None:
            from langchain_community.vectorstores import FAISS
            _index = FAISS.load_local(str(config.INDEX_DIR), emb, allow_dangerous_deserialization=True)
    return _index


def build_query(p: CitizenProfile, user_input: str = "") -> str:
    bits = []
    if p.age is not None:
        bits.append(f"{p.age} year old")
    for v in (p.gender, p.social_category, p.occupation, p.artisan_trade, p.marital_status, p.education_level):
        if v:
            bits.append(str(v).replace("_", " "))
    if p.is_bpl:
        bits.append("BPL below poverty line")
    if p.disability_percent:
        bits.append("person with disability")
    if p.is_pregnant_or_lactating:
        bits.append("pregnant woman maternity")
    if any(c.gender == "female" for c in p.children):
        bits.append("girl child")
    bits += p.health_conditions + [i.replace("_", " ") for i in p.intents]
    return " ".join(bits) + " " + user_input[:300]


def retrieve(state: NavigatorState) -> dict:
    start = time.time()
    p = state["profile"]
    schemes = load_schemes()

    allowed = [
        s for s in schemes.values()
        if s.level == "central" or (p.state and s.state and s.state.lower() == p.state.lower())
    ]
    allowed_ids = {s.scheme_id for s in allowed}

    index = _load_index()
    if index is not None:
        query = build_query(p, state.get("user_input", ""))
        hits = index.similarity_search_with_score(query, k=len(schemes))
        scored = [(h.metadata["scheme_id"], float(score)) for h, score in hits if h.metadata["scheme_id"] in allowed_ids]
        scored = scored[: config.RETRIEVAL_TOP_K]
        mode = "faiss"
    else:
        scored = [(s.scheme_id, 0.0) for s in allowed]
        mode = "filter_only"

    candidates = [
        SchemeDoc(
            scheme_id=sid,
            name=schemes[sid].name,
            level=schemes[sid].level,
            category=schemes[sid].category,
            text=scheme_text(schemes[sid]),
            score=score,
        )
        for sid, score in scored
    ]
    log.info("retrieved %d candidates (%s)", len(candidates), mode)
    return {
        "candidates": candidates,
        "trace": [{
            "agent": "Scheme Retriever",
            "mode": mode,
            "output": [c.scheme_id for c in candidates],
            "seconds": round(time.time() - start, 2),
        }],
    }
