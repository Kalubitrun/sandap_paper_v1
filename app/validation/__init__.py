"""Validation package: Phase 3 read-only checks over NormalizedPaper."""

from app.validation.models import ValidationIssue, ValidationResult
from app.validation.validator import validate_docx, validate_paper

__all__ = ["ValidationIssue", "ValidationResult", "validate_paper", "validate_docx"]
