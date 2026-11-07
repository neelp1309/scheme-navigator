"""Agent 6 - Evaluate: guardrails before anything reaches the user.

Deterministic checks (no LLM needed):
1. Every scheme_id exists in the knowledge base       -> no hallucinated schemes
2. No "eligible" verdict contradicts a failed rule     -> LLM can't override rules
3. Evidence quotes appear in the scheme's own text     -> grounded reasons
4. State schemes only for residents of that state

On failure the graph loops back to the Judge with these issues as feedback.

TODO(you): add an LLM-based check for tone/readability of the summary, and a
bias check (e.g. results should not change when only the name changes).
"""
from __future__ import annotations

import logging
import re
import time

from knowledge_base import load_schemes, scheme_text
from rules.criteria_check import check_scheme
from schemas import VerificationReport
from state import NavigatorState

log = logging.getLogger(__name__)


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.lower()).strip()


def verify(state: NavigatorState) -> dict:
    start = time.time()
    schemes = load_schemes()
    profile = state["profile"]
    issues: list[str] = []

    for r in state.get("results", []):
        if r.scheme_id not in schemes:
            issues.append(f"{r.scheme_id}: not in the knowledge base (hallucinated). Remove it.")
            continue
        s = schemes[r.scheme_id]

        if r.verdict == "eligible":
            rule = check_scheme(s, profile)
            if rule.verdict != "eligible":
                issues.append(f"{r.scheme_id}: marked eligible but rule check says {rule.verdict} "
                              f"({rule.failed_criteria or rule.missing_info}).")
            if s.level == "state" and (not profile.state or profile.state.lower() != (s.state or "").lower()):
                issues.append(f"{r.scheme_id}: state scheme for {s.state}, user is in {profile.state}.")
            if r.evidence:
                source = _norm(scheme_text(s) + " " + " ".join(s.fuzzy_conditions))
                # allow light paraphrase: require the first 60 chars to be present
                if _norm(r.evidence)[:60] not in source:
                    issues.append(f"{r.scheme_id}: evidence quote not found in the scheme text. "
                                  "Quote the scheme text exactly.")

    report = VerificationReport(passed=not issues, issues=issues)
    retries = state.get("retry_count", 0) + (0 if report.passed else 1)
    log.info("verification passed=%s issues=%d", report.passed, len(issues))
    return {
        "verification": report,
        "retry_count": retries,
        "trace": [{
            "agent": "Verifier",
            "output": report.model_dump(),
            "seconds": round(time.time() - start, 2),
        }],
    }


def drop_unverified(state: NavigatorState) -> dict:
    """Used when retries are exhausted: keep only results that pass all checks."""
    schemes = load_schemes()
    profile = state["profile"]
    kept = []
    for r in state.get("results", []):
        if r.scheme_id not in schemes:
            continue
        if r.verdict == "eligible" and check_scheme(schemes[r.scheme_id], profile).verdict != "eligible":
            r.verdict = "needs_info"
        kept.append(r)
    return {"results": kept, "trace": [{"agent": "Verifier", "output": "retries exhausted: unverified results downgraded"}]}
