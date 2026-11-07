"""Agent 3 - Decide: profile + candidates -> EligibilityResult per scheme.

Hybrid design:
1. rules/criteria_check.py decides every numeric / categorical rule.
2. Only schemes that pass the rules AND have fuzzy_conditions go to the LLM,
   which judges those conditions against what the user actually said.
The LLM can downgrade an "eligible" to "not_eligible"/"needs_info", but can
never upgrade a rule failure. The Verifier enforces this.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Literal

from pydantic import BaseModel, Field

from knowledge_base import load_schemes
from llm import get_llm, load_prompt
from rules.criteria_check import check_scheme
from schemas import EligibilityResult
from state import NavigatorState

log = logging.getLogger(__name__)


class FuzzyVerdict(BaseModel):
    """LLM output for one scheme's fuzzy conditions."""

    verdict: Literal["met", "not_met", "unknown"]
    reason: str = Field(description="One sentence, citing what the user said")
    evidence: str = Field(description="Exact quote copied from the scheme text that the decision relies on")
    confidence: float = Field(ge=0, le=1)


def _judge_fuzzy(llm, user_input: str, profile_json: str, scheme, feedback: str | None) -> FuzzyVerdict:
    prompt = (
        load_prompt("eligibility_judge")
        .replace("{user_input}", user_input)
        .replace("{profile}", profile_json)
        .replace("{scheme_text}", f"{scheme.eligibility_text}\nExclusions: {scheme.exclusions_text}")
        .replace("{conditions}", "\n".join(f"- {c}" for c in scheme.fuzzy_conditions))
        .replace("{feedback}", feedback or "None")
    )
    return llm.with_structured_output(FuzzyVerdict).invoke(prompt)


def judge(state: NavigatorState) -> dict:
    start = time.time()
    schemes = load_schemes()
    profile = state["profile"]
    llm = get_llm()
    feedback = None
    if state.get("verification") and not state["verification"].passed:
        feedback = "\n".join(state["verification"].issues)

    profile_json = json.dumps(profile.model_dump(exclude_none=True, exclude_defaults=True), ensure_ascii=False)
    results: list[EligibilityResult] = []
    llm_calls = 0

    for cand in state["candidates"]:
        s = schemes[cand.scheme_id]
        rule = check_scheme(s, profile)
        res = EligibilityResult(
            scheme_id=s.scheme_id,
            verdict=rule.verdict,
            matched_criteria=rule.matched_criteria,
            failed_criteria=rule.failed_criteria,
            missing_info=rule.missing_info,
            evidence=s.eligibility_text[:200],
            confidence=1.0 if not rule.assumptions else 0.85,
        )

        if rule.verdict == "eligible" and s.fuzzy_conditions:
            if llm is None:
                # Offline baseline: assume fuzzy conditions are met.
                res.confidence = min(res.confidence, 0.6)
            else:
                fv = _judge_fuzzy(llm, state.get("user_input", ""), profile_json, s, feedback)
                llm_calls += 1
                res.evidence = fv.evidence
                res.confidence = fv.confidence
                if fv.verdict == "not_met":
                    res.verdict = "not_eligible"
                    res.failed_criteria.append(fv.reason)
                elif fv.verdict == "unknown":
                    res.verdict = "needs_info"
                    res.missing_info.append(fv.reason)
                else:
                    res.matched_criteria.append(fv.reason)
        results.append(res)

    # Most useful first: eligible, then needs_info, then the rest
    order = {"eligible": 0, "needs_info": 1, "not_eligible": 2}
    results.sort(key=lambda r: (order[r.verdict], -r.confidence))

    counts = {v: sum(r.verdict == v for r in results) for v in order}
    log.info("judged %d schemes: %s (llm calls=%d)", len(results), counts, llm_calls)
    return {
        "results": results,
        "trace": [{
            "agent": "Eligibility Judge",
            "mode": "rules+llm" if llm else "rules_only",
            "output": counts,
            "eligible": [r.scheme_id for r in results if r.verdict == "eligible"],
            "llm_calls": llm_calls,
            "retry_feedback": feedback,
            "seconds": round(time.time() - start, 2),
        }],
    }
