"""Loads schemes.json once and gives agents typed access to it."""
from __future__ import annotations

import json
from functools import lru_cache

import config
from schemas import Scheme


@lru_cache(maxsize=1)
def load_schemes() -> dict[str, Scheme]:
    raw = json.loads(config.SCHEMES_PATH.read_text(encoding="utf-8"))
    schemes = [Scheme(**s) for s in raw]
    return {s.scheme_id: s for s in schemes}


def scheme_text(s: Scheme) -> str:
    """The text that gets embedded and shown to the LLM judge."""
    parts = [
        f"{s.name} ({'Central' if s.level == 'central' else s.state} scheme, {s.category})",
        s.description,
        f"Benefits: {s.benefits}",
        f"Eligibility: {s.eligibility_text}",
    ]
    if s.exclusions_text:
        parts.append(f"Exclusions: {s.exclusions_text}")
    return "\n".join(parts)
