"""Backend service layer for the Phase 6 API (Phase 6).

Pure functions over bytes; no HTTP framework here so the logic stays
testable without a server. All document processing is delegated to the
existing Phase 1-5 engine -- nothing is reimplemented.
"""

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path

from app.parser.analyzer import analyze_document
from app.parser.extractor import extract_document
from app.renderer import PaperSettings, SchoolConfig, render_question_paper
from app.spelling import SpellCheckerService
from app.validation import validate_paper

log = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

_EXAM_FILENAME_PART = {
    "PT 1": "PT1",
    "PT 2": "PT2",
    "Half Yearly Examination": "Half_Yearly",
    "Annual Examination": "Annual",
}

class ApiError(Exception):
    """User-safe failure (message is shown in the UI, never a traceback)."""

    def __init__(self, message: str, status_code: int = 400, code: str = "error"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def _check_upload(data: bytes, filename: str) -> None:
    if not filename.lower().endswith(".docx"):
        raise ApiError(
            "Unsupported file type. Please upload a Word document (.docx).",
            status_code=415, code="unsupported_file_type",
        )
    if not data:
        raise ApiError("The uploaded file is empty.", status_code=400, code="empty_file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ApiError(
            f"File is too large ({len(data) / 1024 / 1024:.1f} MB). "
            "Please upload a file smaller than 10 MB.",
            status_code=413, code="file_too_large",
        )
    if data[:4] != b"PK\x03\x04":
        raise ApiError(
            "Unable to read the question paper. Please check that the DOCX file is valid.",
            status_code=400, code="invalid_docx",
        )


def _load_paper(data: bytes, filename: str):
    _check_upload(data, filename)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "upload.docx"
            path.write_bytes(data)
            raw = extract_document(path)
            return analyze_document(raw)
    except ApiError:
        raise
    except Exception as exc:
        log.exception("Document processing failed for %s", filename)
        raise ApiError(
            "Unable to read the question paper. Please check that the DOCX file is valid.",
            status_code=422, code="unreadable_docx",
        ) from exc


def analyze_document_bytes(data: bytes, filename: str) -> dict:
    """Run Phases 1-4 over uploaded bytes; return JSON-safe analysis."""
    paper = _load_paper(data, filename)
    validation = validate_paper(paper)
    spelling = SpellCheckerService().check_paper(paper)
    n_questions = sum(len(s.questions) for s in paper.sections)
    return {
        "filename": filename,
        "summary": {
            "sections": len(paper.sections),
            "questions": n_questions,
            "instructions": max(0, len(paper.instructions) - 1),
            "has_instructions": bool(paper.instructions),
            "spelling_suggestions": len(spelling.suggestions),
            "has_errors": validation.has_errors,
        },
        "paper": paper.to_dict(),
        "validation": validation.to_dict(),
        "spelling": spelling.to_dict(),
    }


def build_download_filename(settings: PaperSettings) -> str:
    """VPS_Half_Yearly_IX_IT_2026-27.docx style names from paper settings."""
    exam = _EXAM_FILENAME_PART.get(settings.examination, "Paper")
    initials = "".join(w[0] for w in re.split(r"\s+", settings.subject.strip()) if w)
    parts = [exam, str(settings.class_name), initials.upper(),
             str(settings.session)]
    safe = "_".join(re.sub(r"[^A-Za-z0-9_-]+", "", p) or "X" for p in parts)
    return f"VPS_{safe}.docx"


def generate_document_bytes(data: bytes, filename: str,
                            settings: PaperSettings) -> tuple[bytes, str]:
    """Run the full pipeline and render; blocked on ERROR-level findings."""
    paper = _load_paper(data, filename)
    try:
        maximum = int(settings.max_marks)
    except (TypeError, ValueError):
        maximum = None
    validation = validate_paper(paper, maximum_marks=maximum)
    if validation.has_errors:
        codes = sorted({i.code for i in validation.errors})
        log.warning("Generation blocked for %s: %s", filename, codes)
        raise ApiError(
            "Question paper generation failed. Some structural problems must be "
            f"fixed first: {', '.join(codes)}.",
            status_code=422, code="validation_blocked",
        )
    try:
        with tempfile.TemporaryDirectory() as tmp:
            out = render_question_paper(paper, SchoolConfig(), settings,
                                        validation, Path(tmp) / "paper.docx")
            return out.read_bytes(), build_download_filename(settings)
    except ApiError:
        raise
    except Exception as exc:
        log.exception("Rendering failed for %s", filename)
        raise ApiError(
            "Question paper generation failed. Please try again.",
            status_code=500, code="render_failed",
        ) from exc
