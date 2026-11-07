"""Agent 1 - Understand: free text -> CitizenProfile.

Also decides whether critical information is missing, in which case the graph
routes to the clarification step instead of guessing.
"""
from __future__ import annotations

import logging
import time

import config
from llm import get_llm, load_prompt
from schemas import CitizenProfile
from state import NavigatorState

log = logging.getLogger(__name__)

ACRES_TO_HA = 0.4047


def _missing_critical(p: CitizenProfile) -> list[str]:
    missing = [f for f in config.CRITICAL_FIELDS if getattr(p, f) in (None, "", [])]
    if all(getattr(p, f) is None for f in config.CRITICAL_ANY_OF):
        missing.append(" or ".join(config.CRITICAL_ANY_OF))
    return missing


def _normalise(p: CitizenProfile) -> CitizenProfile:
    if p.state:
        p.state = p.state.strip().title().replace("And", "and")
    if p.occupation == "govt_employee":
        p.is_govt_employee = True
    return p


def build_question(missing: list[str]) -> str:
    asks = {
        "age": "your age",
        "state": "which state you live in",
        "occupation or annual_family_income or is_bpl": "what work you do and roughly how much your family earns in a year",
    }
    items = [asks.get(m, m.replace("_", " ")) for m in missing]
    return "To find the right schemes, could you tell me " + ", ".join(items) + "?"


def extract_profile(state: NavigatorState) -> dict:
    start = time.time()

    # Evaluation shortcut: a profile can be injected to test the later agents alone.
    if state.get("profile_injected") and state.get("profile") is not None:
        profile = state["profile"]
        mode = "injected"
    else:
        llm = get_llm()
        if llm is None:
            raise RuntimeError(
                "Profile extraction needs an LLM. Set GOOGLE_API_KEY or OPENAI_API_KEY in .env, "
                "or pass a ready-made profile (see eval/run_eval.py --mode offline)."
            )
        prompt = load_prompt("profile_extractor").replace("{user_input}", state["user_input"])
        # TODO(you): add few-shot examples to the prompt and measure the change in eval.
        extractor = llm.with_structured_output(CitizenProfile)
        profile = extractor.invoke(prompt)
        mode = "llm"

    profile = _normalise(profile)
    profile.missing_fields = _missing_critical(profile)

    rounds = state.get("clarification_rounds", 0)
    question = None
    if profile.missing_fields and rounds < config.MAX_CLARIFICATION_ROUNDS:
        question = build_question(profile.missing_fields)

    log.info("profile extracted (%s): missing=%s", mode, profile.missing_fields)
    return {
        "profile": profile,
        "clarifying_question": question,
        "trace": [{
            "agent": "Profile Extractor",
            "mode": mode,
            "output": profile.model_dump(exclude_none=True, exclude_defaults=True),
            "missing": profile.missing_fields,
            "seconds": round(time.time() - start, 2),
        }],
    }
