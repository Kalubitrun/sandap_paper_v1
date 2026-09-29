"""Renderer configuration: single source of truth for fixed school info (Phase 5).

Phone number: no phone number exists anywhere in the project, so the
field stays configurable (None by default) instead of inventing one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOGO_PATH = PROJECT_ROOT / "logo.webp"

ALLOWED_EXAMINATIONS = (
    "PT 1",
    "PT 2",
    "Half Yearly Examination",
    "Annual Examination",
)


@dataclass
class SchoolConfig:
    name: str = "VARANASI PUBLIC SCHOOL"
    address: str = "BANGALIPUR, RAJATALAB, VARANASI"
    affiliation_number: str = "2131898"
    school_number: str = "71377"
    phone_number: str | None = None  # not available in project: never invented
    logo_path: str | Path = DEFAULT_LOGO_PATH
    emblem_path: str | Path | None = None  # right-side emblem if available
    use_logo_both_sides: bool = True  # mirror logo right when no emblem exists
    logo_width_inches: float = 1.6


@dataclass
class PaperSettings:
    examination: str = "Half Yearly Examination"
    session: str = "2026-27"
    class_name: str = "IX"
    subject: str = "Information Technology"
    subject_code: str = "402"
    max_marks: int | str = 50
    time: str = "3:00 hours"

    def __post_init__(self) -> None:
        if self.examination not in ALLOWED_EXAMINATIONS:
            raise ValueError(
                f"Unknown examination {self.examination!r}; "
                f"allowed: {list(ALLOWED_EXAMINATIONS)}"
            )
