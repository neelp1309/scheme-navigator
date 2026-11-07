"""Streamlit UI.  Run:  streamlit run app.py"""
from __future__ import annotations

import json

import streamlit as st

from graph import run
from knowledge_base import load_schemes

st.set_page_config(page_title="Scheme Navigator", page_icon="🧭", layout="wide")
st.title("🧭 Scheme Navigator")
st.caption("Describe your situation in English, Hindi or Gujarati. "
           "Guidance only; always confirm on the official portal.")

if "history" not in st.session_state:
    st.session_state.history = []          # list of (role, text)
    st.session_state.pending_question = False

for role, text in st.session_state.history:
    st.chat_message(role).write(text)

user_msg = st.chat_input("e.g. I'm a 45-year-old farmer in Gujarat with 2 acres, family income ₹1.2 lakh")
if user_msg:
    st.session_state.history.append(("user", user_msg))
    st.chat_message("user").write(user_msg)

    full_text = "\n".join(t for r, t in st.session_state.history if r == "user")
    rounds = 1 if st.session_state.pending_question else 0
    with st.spinner("Agents at work…"):
        out = run(full_text, clarification_rounds=rounds)

    if out.get("clarifying_question") and not out.get("summary"):
        q = out["clarifying_question"]
        st.session_state.history.append(("assistant", q))
        st.session_state.pending_question = True
        st.chat_message("assistant").write(q)
    else:
        st.session_state.pending_question = False
        st.session_state.history.append(("assistant", out["summary"]))
        st.chat_message("assistant").write(out["summary"])
        st.session_state.last = out

out = st.session_state.get("last")
if out:
    schemes = load_schemes()
    col1, col2 = st.columns([3, 2])
    with col1:
        st.subheader("Results")
        for r in out["results"]:
            if r.verdict == "not_eligible":
                continue
            s = schemes[r.scheme_id]
            icon = "✅" if r.verdict == "eligible" else "❓"
            with st.expander(f"{icon} {s.name}"):
                st.write(s.benefits)
                if r.matched_criteria:
                    st.markdown("**Why:** " + "; ".join(r.matched_criteria))
                if r.missing_info:
                    st.markdown("**Need to know:** " + ", ".join(r.missing_info))
                st.markdown(f"[Official source]({s.source_urls[0]})")
        if out.get("pdf_path"):
            with open(out["pdf_path"], "rb") as f:
                st.download_button("📄 Download checklist PDF", f, file_name=f"checklist_{out['case_id']}.pdf")
    with col2:
        st.subheader("Agent trace")
        for step in out.get("trace", []):
            with st.expander(f"{step['agent']} ({step.get('seconds', '')}s)"):
                st.code(json.dumps(step, indent=1, ensure_ascii=False, default=str), language="json")

with st.sidebar:
    if st.button("Start over"):
        st.session_state.clear()
        st.rerun()
