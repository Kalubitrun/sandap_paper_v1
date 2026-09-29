"""Spell-check result model for Phase 4.

Findings only: nothing is ever replaced. Every suggestion stays
``status="pending"`` for a human to review in a later phase.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Suggestion:
    original: str
    suggested: str
    source_blocks: list[int] = field(default_factory=list)
    question_number: int | None = None
    context: str = ""
    confidence: str = "low"  # "high" | "medium" | "low"
    status: str = "pending"

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "suggested": self.suggested,
            "source_blocks": list(self.source_blocks),
            "question_number": self.question_number,
            "context": self.context,
            "confidence": self.confidence,
            "status": self.status,
        }


@dataclass
class SpellCheckResult:
    suggestions: list[Suggestion] = field(default_factory=list)
    texts_checked: int = 0
    words_checked: int = 0
    custom_dictionary_size: int = 0

    def summary(self) -> dict:
        return {
            "total_suggestions": len(self.suggestions),
            "texts_checked": self.texts_checked,
            "words_checked": self.words_checked,
            "custom_dictionary_size": self.custom_dictionary_size,
        }

    def to_dict(self) -> dict:
        return {
            "suggestions": [s.to_dict() for s in self.suggestions],
            "summary": self.summary(),
        }
