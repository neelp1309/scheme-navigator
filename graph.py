"""LangGraph wiring for the Scheme Navigator.

            ┌────────────── clarify ──► END (UI asks the user, then re-runs)
            │
 START ─► extract_profile ─► retrieve ─► judge ─► verify ─┬─► execute ─► summarize ─► END
                                           ▲              │
                                           └── retry ◄────┘ (max MAX_VERIFIER_RETRIES)
"""
from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

import config
from agents.eligibility_judge import judge
from agents.executor import execute
from agents.profile_extractor import extract_profile
from agents.retriever import retrieve
from agents.summarizer import summarize
from agents.verifier import drop_unverified, verify
from state import NavigatorState

log = logging.getLogger(__name__)


def clarify(state: NavigatorState) -> dict:
    return {
        "clarification_rounds": state.get("clarification_rounds", 0) + 1,
        "trace": [{"agent": "Clarifier", "output": state["clarifying_question"]}],
    }


def after_extract(state: NavigatorState) -> str:
    return "clarify" if state.get("clarifying_question") else "retrieve"


def after_verify(state: NavigatorState) -> str:
    if state["verification"].passed:
        return "execute"
    if state.get("retry_count", 0) <= config.MAX_VERIFIER_RETRIES:
        return "judge"
    return "drop_unverified"


def build_graph():
    g = StateGraph(NavigatorState)
    g.add_node("extract_profile", extract_profile)
    g.add_node("clarify", clarify)
    g.add_node("retrieve", retrieve)
    g.add_node("judge", judge)
    g.add_node("verify", verify)
    g.add_node("drop_unverified", drop_unverified)
    g.add_node("execute", execute)
    g.add_node("summarize", summarize)

    g.add_edge(START, "extract_profile")
    g.add_conditional_edges("extract_profile", after_extract, {"clarify": "clarify", "retrieve": "retrieve"})
    g.add_edge("clarify", END)
    g.add_edge("retrieve", "judge")
    g.add_edge("judge", "verify")
    g.add_conditional_edges("verify", after_verify,
                            {"execute": "execute", "judge": "judge", "drop_unverified": "drop_unverified"})
    g.add_edge("drop_unverified", "execute")
    g.add_edge("execute", "summarize")
    g.add_edge("summarize", END)
    return g.compile()


GRAPH = build_graph()


def run(user_input: str, clarification_rounds: int = 0, **extra) -> NavigatorState:
    """Run the whole pipeline once. Pass clarification_rounds=1 after the user answered a question."""
    state: NavigatorState = {
        "user_input": user_input,
        "clarification_rounds": clarification_rounds,
        "retry_count": 0,
        "trace": [],
        **extra,
    }
    return GRAPH.invoke(state)


if __name__ == "__main__":
    import sys

    text = " ".join(sys.argv[1:]) or "I am a 45 year old farmer in Gujarat with 2 acres, income 1.2 lakh."
    out = run(text)
    if out.get("clarifying_question") and not out.get("summary"):
        print("QUESTION:", out["clarifying_question"])
    else:
        print(out["summary"])
        print("PDF:", out.get("pdf_path"))
