"""Agent 5 - Summarize: results -> a short, friendly message in the user's language."""
from __future__ import annotations

import json
import logging
import time

from knowledge_base import load_schemes
from llm import get_llm, load_prompt
from state import NavigatorState

log = logging.getLogger(__name__)


def _template_summary(state: NavigatorState) -> str:
    schemes = load_schemes()
    res = state["results"]
    eligible = [r for r in res if r.verdict == "eligible"]
    maybe = [r for r in res if r.verdict == "needs_info"]
    lines = []
    if eligible:
        lines.append(f"Good news: you appear to qualify for {len(eligible)} scheme(s).")
        for r in eligible:
            lines.append(f"• {schemes[r.scheme_id].name}: {schemes[r.scheme_id].benefits}")
    else:
        lines.append("I couldn't confirm any scheme yet.")
    if maybe:
        need = sorted({m for r in maybe for m in r.missing_info})[:5]
        lines.append(f"\n{len(maybe)} more scheme(s) might apply. It would help to know: {', '.join(need)}.")
    lines.append("\nYour checklist PDF lists the documents and steps for each scheme. "
                 "This is guidance only; please confirm on the official portal.")
    return "\n".join(lines)


def summarize(state: NavigatorState) -> dict:
    start = time.time()
    llm = get_llm()
    if llm is None:
        summary, mode = _template_summary(state), "template"
    else:
        schemes = load_schemes()
        payload = [
            {
                "scheme": schemes[r.scheme_id].name,
                "verdict": r.verdict,
                "benefit": schemes[r.scheme_id].benefits,
                "why": r.matched_criteria[-2:] + r.failed_criteria[:1],
                "missing": r.missing_info[:3],
            }
            for r in state["results"] if r.verdict != "not_eligible"
        ]
        prompt = (load_prompt("summarizer")
                  .replace("{user_input}", state.get("user_input", ""))
                  .replace("{results}", json.dumps(payload, ensure_ascii=False, indent=1)))
        summary, mode = llm.invoke(prompt).content, "llm"
    return {
        "summary": summary,
        "trace": [{"agent": "Summarizer", "mode": mode, "output": summary[:300],
                   "seconds": round(time.time() - start, 2)}],
    }
