"""Validation result model for Phase 3.

Read-only findings about a :class:`NormalizedPaper`. The validator never
mutates the paper; it only appends :class:`ValidationIssue` entries here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

SEVERITIES = ("error", "warning", "info")


@dataclass
class ValidationIssue:
    code: str
    severity: str  # "error" | "warning" | "info"
    message: str
    source_blocks: list[int] = field(default_factory=list)
    question_number: int | None = None
    section: str | None = None  # section_id, e.g. "A"; None when not in a named section
    details: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"Unknown severity: {self.severity!r}")

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "source_blocks": list(self.source_blocks),
            "question_number": self.question_number,
            "section": self.section,
            "details": dict(self.details),
        }


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def info(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "info"]

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def summary(self) -> dict:
        return {
            "total": len(self.issues),
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "info": len(self.info),
            "has_errors": self.has_errors,
        }

    def to_dict(self) -> dict:
        return {
            "errors": [i.to_dict() for i in self.errors],
            "warnings": [i.to_dict() for i in self.warnings],
            "info": [i.to_dict() for i in self.info],
            "summary": self.summary(),
        }

    def by_code(self, code: str) -> list[ValidationIssue]:
        return [i for i in self.issues if i.code == code]
