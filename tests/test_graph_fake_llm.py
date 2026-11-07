"""End-to-end graph test with a fake LLM, so the LLM code paths run without an API key."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agents.eligibility_judge as judge_mod  # noqa: E402
import agents.profile_extractor as extractor_mod  # noqa: E402
import agents.summarizer as summarizer_mod  # noqa: E402
from graph import run  # noqa: E402
from schemas import CitizenProfile  # noqa: E402


class _Msg:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    """Returns a fixed profile, says fuzzy conditions are 'not_met' for Stand-Up India
    (the loan-size trap) and 'met' otherwise, quoting the scheme text as evidence."""

    def __init__(self, profile: CitizenProfile):
        self.profile = profile

    def with_structured_output(self, schema):
        llm = self

        class _Runner:
            def invoke(self, prompt):
                if schema is CitizenProfile:
                    return llm.profile.model_copy()
                scheme_text = re.search(r'SCHEME TEXT:\n"""\n(.*?)\n', prompt, re.S).group(1)
                not_met = "₹10 lakh to ₹1 crore" in prompt or "greenfield" in prompt.lower()
                return schema(
                    verdict="not_met" if not_met else "met",
                    reason="loan needed is far below ₹10 lakh" if not_met else "consistent with the message",
                    evidence=scheme_text[:120],
                    confidence=0.9,
                )
        return _Runner()

    def invoke(self, prompt):
        return _Msg("Here are the schemes you qualify for.")


def _patch(monkeypatch, profile):
    fake = FakeLLM(profile)
    for mod in (extractor_mod, judge_mod, summarizer_mod):
        monkeypatch.setattr(mod, "get_llm", lambda fake=fake: fake)


def test_full_graph_with_fake_llm(monkeypatch, tmp_path):
    profile = CitizenProfile(age=27, gender="female", state="Gujarat", area="rural", occupation="artisan",
                             artisan_trade="tailor", social_category="sc", annual_family_income=140000,
                             intents=["start_business"])
    _patch(monkeypatch, profile)
    out = run("I'm Rekha, 27, SC, tailor in Anand, want to start a small shop. Income 1.4 lakh.")
    eligible = {r.scheme_id for r in out["results"] if r.verdict == "eligible"}
    assert "pm_vishwakarma" in eligible
    assert "stand_up_india" not in eligible          # judge caught the trap
    assert out["verification"].passed
    assert Path(out["pdf_path"]).exists()
    assert [t["agent"] for t in out["trace"]][:2] == ["Profile Extractor", "Scheme Retriever"]


def test_vague_input_triggers_clarification(monkeypatch):
    _patch(monkeypatch, CitizenProfile())
    out = run("I need some help from the government, I am poor.")
    assert out["clarifying_question"]
    assert "summary" not in out or not out.get("summary")
