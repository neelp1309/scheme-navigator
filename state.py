"""Shared LangGraph state: the "blackboard" every agent reads and writes."""
from __future__ import annotations

import operator
from typing import Annotated, Optional, TypedDict

from schemas import CitizenProfile, EligibilityResult, SchemeDoc, VerificationReport


class NavigatorState(TypedDict, total=False):
    # input
    user_input: str                      # full conversation text so far
    language: str                        # "en", "hi", "gu", ...
    profile_injected: bool               # eval only: skip extraction and use the given profile

    # agent outputs
    profile: CitizenProfile
    clarifying_question: Optional[str]
    clarification_rounds: int
    candidates: list[SchemeDoc]
    results: list[EligibilityResult]
    verification: VerificationReport
    retry_count: int
    pdf_path: Optional[str]
    case_id: Optional[str]
    summary: str

    # observability: each node appends one entry; operator.add merges lists
    trace: Annotated[list[dict], operator.add]
