"""Phase 1: DOCX -> Raw Document Representation.

Deterministic extraction only (python-docx). No classification,
no content rewriting. ``original_text`` is preserved byte-for-byte
as python-docx returns it; ``cleaned_text`` is a whitespace-normalised
helper for future phases.
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.models.document import (
    ParagraphInfo,
    RawDocument,
    RunInfo,
    TableCellInfo,
    TableInfo,
)

_ALIGNMENT_NAMES = {
    WD_ALIGN_PARAGRAPH.LEFT: "LEFT",
    WD_ALIGN_PARAGRAPH.CENTER: "CENTER",
    WD_ALIGN_PARAGRAPH.RIGHT: "RIGHT",
    WD_ALIGN_PARAGRAPH.JUSTIFY: "JUSTIFY",
    WD_ALIGN_PARAGRAPH.DISTRIBUTE: "DISTRIBUTE",
}

_WHITESPACE_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Normalise whitespace for future processing.

    - Strips leading/trailing whitespace.
    - Collapses every run of whitespace (spaces, tabs, etc.) to one space.
    Never applied back onto ``original_text``.
    """
    return _WHITESPACE_RE.sub(" ", text.strip())


def _alignment_name(paragraph) -> str | None:
    alignment = paragraph.paragraph_format.alignment
    if alignment is None:
        return None  # inherits document default (normally left)
    return _ALIGNMENT_NAMES.get(alignment, str(alignment))


def _extract_run(run) -> RunInfo:
    font = run.font
    size_pt = None
    if font.size is not None:
        size_pt = round(font.size.pt, 2)
    color = None
    try:
        if font.color is not None and font.color.rgb is not None:
            color = str(font.color.rgb)
    except Exception:
        color = None
    return RunInfo(
        text=run.text,
        bold=run.bold,
        italic=run.italic,
        underline=bool(run.underline) if run.underline is not None else None,
        strike=font.strike,
        font_name=font.name,
        font_size_pt=size_pt,
        font_color_rgb=color,
    )


def _extract_paragraph(paragraph, index: int) -> ParagraphInfo:
    original = paragraph.text  # untouched source of truth
    style = paragraph.style.name if paragraph.style is not None else None
    return ParagraphInfo(
        index=index,
        original_text=original,
        cleaned_text=clean_text(original),
        style=style,
        alignment=_alignment_name(paragraph),
        is_empty=(original.strip() == ""),
        runs=[_extract_run(r) for r in paragraph.runs],
    )


def _extract_tables(doc: DocxDocument) -> list[TableInfo]:
    tables: list[TableInfo] = []
    for ti, table in enumerate(doc.tables):
        n_rows = len(table.rows)
        n_cols = len(table.rows[0].cells) if n_rows else 0
        cells: list[TableCellInfo] = []
        for ri, row in enumerate(table.rows):
            for ci, cell in enumerate(row.cells):
                cell_paras = [
                    _extract_paragraph(p, index=pi)
                    for pi, p in enumerate(cell.paragraphs)
                ]
                cell_text = "\n".join(p.original_text for p in cell_paras)
                # python-docx cell.text strips trailing newline; keep our join instead
                cells.append(
                    TableCellInfo(row=ri, col=ci, text=cell.text, paragraphs=cell_paras)
                )
        style_name = None
        try:
            style_name = table.style.name if table.style is not None else None
        except Exception:
            style_name = None
        _ = style_name  # reserved for future phases; not part of Phase 1 schema
        tables.append(TableInfo(index=ti, rows=n_rows, cols=n_cols, cells=cells))
    return tables


def extract_document(path: str | Path) -> RawDocument:
    """Load a DOCX file and return its raw representation."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"DOCX not found: {path}")
    doc = DocxDocument(str(path))
    paragraphs = [_extract_paragraph(p, index=i) for i, p in enumerate(doc.paragraphs)]
    tables = _extract_tables(doc)
    return RawDocument(source=path.name, paragraphs=paragraphs, tables=tables)


def load_document(path: str | Path) -> RawDocument:
    """Alias for :func:`extract_document`."""
    return extract_document(path)
