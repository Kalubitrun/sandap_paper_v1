"""Typed internal data model for Phase 1 raw document representation.

Principles:
- ``original_text`` is the source of truth and is never modified.
- ``cleaned_text`` is a derived helper for future processing only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class RunInfo:
    """A single text run inside a paragraph."""

    text: str
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    strike: bool | None = None
    font_name: str | None = None
    font_size_pt: float | None = None
    font_color_rgb: str | None = None  # hex string like "FF0000", else None


@dataclass
class ParagraphInfo:
    """One body paragraph in document order."""

    index: int
    original_text: str
    cleaned_text: str
    style: str | None
    alignment: str | None  # e.g. "LEFT", "CENTER", "RIGHT", "JUSTIFY", None if inherited
    is_empty: bool  # True when original_text.strip() == ""
    runs: list[RunInfo] = field(default_factory=list)


@dataclass
class TableCellInfo:
    row: int
    col: int
    text: str  # concatenated cell text (paragraphs joined by "\n")
    paragraphs: list[ParagraphInfo] = field(default_factory=list)


@dataclass
class TableInfo:
    index: int
    rows: int
    cols: int
    cells: list[TableCellInfo] = field(default_factory=list)


@dataclass
class RawDocument:
    source: str
    paragraphs: list[ParagraphInfo] = field(default_factory=list)
    tables: list[TableInfo] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "paragraphs": [asdict(p) for p in self.paragraphs],
            "tables": [asdict(t) for t in self.tables],
        }
