"""Agent 4 - Execute: turn decisions into real artifacts.

* Generates a PDF checklist (documents + application steps) for every
  eligible scheme.
* Saves the case to SQLite so it can be looked up later.

TODO(you): add an optional action such as emailing the PDF or creating a
reminder for application deadlines.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

import config
from knowledge_base import load_schemes
from state import NavigatorState

log = logging.getLogger(__name__)


def _safe(text: str) -> str:
    """ReportLab's built-in fonts have no ₹ glyph; use 'Rs.' so the PDF works on any machine.
    TODO(you): register a Unicode TTF font (e.g. Noto Sans Gujarati) to print in Indian languages."""
    return text.replace("₹", "Rs. ").replace("&", "&amp;")


def _pdf(path, results, schemes, case_id: str) -> None:
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Your Government Scheme Checklist", styles["Title"]),
        Paragraph(f"Case ID: {case_id} &nbsp;&nbsp; Date: {datetime.now():%d %b %Y}", styles["Normal"]),
        Paragraph("This is guidance, not an official decision. Always confirm on the official portal.",
                  styles["Italic"]),
        Spacer(1, 6 * mm),
    ]
    eligible = [r for r in results if r.verdict == "eligible"]
    if not eligible:
        story.append(Paragraph("No schemes were confirmed as eligible yet.", styles["Normal"]))
    for i, r in enumerate(eligible, 1):
        s = schemes[r.scheme_id]
        story += [
            Paragraph(f"{i}. {_safe(s.name)}", styles["Heading2"]),
            Paragraph(f"<b>Benefit:</b> {_safe(s.benefits)}", styles["Normal"]),
            Spacer(1, 2 * mm),
            Paragraph("<b>Documents to keep ready</b>", styles["Normal"]),
            ListFlowable([ListItem(Paragraph("[ ]  " + _safe(d), styles["Normal"]), value="") for d in s.documents_required],
                         bulletType="bullet", start="", leftIndent=10),
            Paragraph("<b>How to apply</b>", styles["Normal"]),
            ListFlowable([ListItem(Paragraph(_safe(st), styles["Normal"])) for st in s.application_steps],
                         bulletType="1", leftIndent=10),
            Paragraph(f"<font color='{colors.grey.hexval()}'>Source: {s.source_urls[0]}</font>", styles["Normal"]),
            Spacer(1, 5 * mm),
        ]
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm).build(story)


def _save_case(case_id: str, state: NavigatorState) -> None:
    with sqlite3.connect(config.DB_PATH) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY, created_at TEXT, user_input TEXT,
            profile_json TEXT, results_json TEXT)""")
        db.execute(
            "INSERT OR REPLACE INTO cases VALUES (?, ?, ?, ?, ?)",
            (
                case_id,
                datetime.now().isoformat(timespec="seconds"),
                state.get("user_input", ""),
                state["profile"].model_dump_json(exclude_none=True),
                json.dumps([r.model_dump() for r in state["results"]], ensure_ascii=False),
            ),
        )


def execute(state: NavigatorState) -> dict:
    start = time.time()
    schemes = load_schemes()
    case_id = uuid.uuid4().hex[:8].upper()
    pdf_path = config.OUTPUT_DIR / f"checklist_{case_id}.pdf"

    _pdf(pdf_path, state["results"], schemes, case_id)
    _save_case(case_id, state)

    log.info("case %s saved, pdf=%s", case_id, pdf_path)
    return {
        "case_id": case_id,
        "pdf_path": str(pdf_path),
        "trace": [{
            "agent": "Action Executor",
            "output": {"case_id": case_id, "pdf": pdf_path.name},
            "seconds": round(time.time() - start, 2),
        }],
    }
