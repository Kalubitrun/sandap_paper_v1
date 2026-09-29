"""Spelling package: deterministic, non-AI spell checking (Phase 4)."""

from app.spelling.checker import SpellCheckerService, spellcheck_docx
from app.spelling.dictionary import DEFAULT_DICTIONARY_PATH, load_dictionary
from app.spelling.models import SpellCheckResult, Suggestion

__all__ = [
    "SpellCheckerService",
    "spellcheck_docx",
    "load_dictionary",
    "DEFAULT_DICTIONARY_PATH",
    "SpellCheckResult",
    "Suggestion",
]
