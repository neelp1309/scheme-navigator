"""Evaluate the system on data/personas.json.

Modes
-----
offline : skip the Profile Extractor and inject each persona's expected_profile.
          Tests retrieval + rules + judge + verifier. Works without an API key
          (fuzzy conditions are assumed met, so this is the rule-only baseline).
full    : run the whole graph from the raw persona text (needs an LLM key).
          Also measures profile-extraction accuracy.

Metrics
-------
* precision / recall / F1 of the "eligible" set vs expected_eligible
  (schemes listed in a persona's "acceptable" list are ignored either way)
* hallucinated scheme IDs
* profile field accuracy (full mode)
* clarification behaviour on vague inputs
* latency

Usage:  python -m eval.run_eval --mode offline
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from graph import GRAPH  # noqa: E402
from knowledge_base import load_schemes  # noqa: E402
from schemas import CitizenProfile  # noqa: E402

OUT_DIR = Path(__file__).parent


def profile_accuracy(pred: CitizenProfile, expected: dict) -> tuple[int, int, list[str]]:
    correct, wrong = 0, []
    for k, v in expected.items():
        got = getattr(pred, k, None)
        if k == "children":
            got = [c.model_dump() for c in got]
        ok = abs(got - v) <= max(0.05 * abs(v), 0.1) if isinstance(v, float) and isinstance(got, (int, float)) else got == v
        if ok:
            correct += 1
        else:
            wrong.append(f"{k}: expected {v!r}, got {got!r}")
    return correct, len(expected), wrong


def run(mode: str) -> dict:
    personas = json.loads(config.PERSONAS_PATH.read_text(encoding="utf-8"))
    kb = load_schemes()
    rows, tp_all, fp_all, fn_all = [], 0, 0, 0
    field_ok = field_total = 0
    hallucinated = 0

    for p in personas:
        t0 = time.time()
        state = {"user_input": p["text"], "retry_count": 0, "clarification_rounds": 0, "trace": []}
        if mode == "offline":
            state["profile"] = CitizenProfile(**p["expected_profile"])
            state["profile_injected"] = True
        out = GRAPH.invoke(state)
        secs = time.time() - t0

        asked = bool(out.get("clarifying_question")) and not out.get("summary")
        pred = {r.scheme_id for r in out.get("results", []) if r.verdict == "eligible"}
        hallucinated += sum(1 for s in pred if s not in kb)
        exp, acc = set(p["expected_eligible"]), set(p.get("acceptable", []))
        tp, fp, fn = pred & exp, pred - exp - acc, exp - pred
        tp_all, fp_all, fn_all = tp_all + len(tp), fp_all + len(fp), fn_all + len(fn)

        row = {
            "persona": p["persona_id"], "seconds": round(secs, 2),
            "asked_clarification": asked, "expected_clarification": p.get("expects_clarification", False),
            "tp": sorted(tp), "fp": sorted(fp), "fn": sorted(fn),
            "retries": out.get("retry_count", 0),
        }
        if mode == "full" and out.get("profile") is not None:
            c, n, wrong = profile_accuracy(out["profile"], p["expected_profile"])
            field_ok, field_total = field_ok + c, field_total + n
            row["profile_errors"] = wrong
        rows.append(row)
        print(f"{p['persona_id']}: tp={len(tp)} fp={sorted(fp)} fn={sorted(fn)} ({secs:.1f}s)")

    precision = tp_all / (tp_all + fp_all) if tp_all + fp_all else 0.0
    recall = tp_all / (tp_all + fn_all) if tp_all + fn_all else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    clar = [r for r in rows if r["expected_clarification"]]
    summary = {
        "mode": mode,
        "personas": len(rows),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "hallucinated_schemes": hallucinated,
        "clarification_correct": f"{sum(r['asked_clarification'] for r in clar)}/{len(clar)}",
        "profile_field_accuracy": round(field_ok / field_total, 3) if field_total else None,
        "avg_seconds": round(sum(r["seconds"] for r in rows) / len(rows), 2),
        "max_seconds": max(r["seconds"] for r in rows),
    }
    (OUT_DIR / f"results_{mode}.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    print("\n" + json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["offline", "full"], default="offline")
    run(ap.parse_args().mode)
