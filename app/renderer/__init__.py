"""Renderer package: deterministic VPS question-paper DOCX renderer (Phase 5)."""

from app.renderer.config import ALLOWED_EXAMINATIONS, PaperSettings, SchoolConfig
from app.renderer.document import RenderBlockedError, render_question_paper

__all__ = [
    "ALLOWED_EXAMINATIONS",
    "PaperSettings",
    "SchoolConfig",
    "RenderBlockedError",
    "render_question_paper",
]
