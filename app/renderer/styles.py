"""Centralized typography / page configuration (Phase 5, refined).

All font sizes, spacing, margins and logo sizing live here. Nothing in
the section/question/option modules hard-codes these values.

Visual hierarchy (dominant first):
  school name 22 bold > exam name 14 bold > class/subject 12 bold >
  section 13 bold+underline > question 11.5 (bold number) >
  options 11 > instructions 10.5 > footer 9.
"""

from __future__ import annotations

from dataclasses import dataclass

from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

_BORDER_EDGES = ("top", "left", "bottom", "right", "insideH", "insideV")


@dataclass
class PageConfig:
    page_width_inches: float = 8.27  # A4
    page_height_inches: float = 11.69  # A4
    margin_top_inches: float = 0.6
    margin_bottom_inches: float = 0.6
    margin_left_inches: float = 0.75
    margin_right_inches: float = 0.75


@dataclass
class StyleConfig:
    body_font: str = "Calibri"
    body_size_pt: float = 11.0
    # 17pt: measured to fit the 3.37" center column on one line both in
    # Word/Calibri (2.63") and under serif substitution (3.30").
    school_name_size_pt: float = 17.0
    address_size_pt: float = 11.0
    exam_info_size_pt: float = 14.0
    exam_detail_size_pt: float = 12.0
    section_heading_size_pt: float = 13.0
    question_size_pt: float = 11.5
    option_size_pt: float = 11.0
    instruction_size_pt: float = 10.5
    footer_size_pt: float = 9.0
    line_spacing_rule: object = WD_LINE_SPACING.SINGLE
    paragraph_space_after_pt: float = 4.0
    question_space_before_pt: float = 8.0
    question_space_after_pt: float = 3.0
    option_space_after_pt: float = 1.0
    instruction_space_after_pt: float = 2.0
    # Space before the FIRST sub-question only (gap under the parent stem).
    subquestion_first_space_before_pt: float = 4.0
    section_space_before_pt: float = 12.0
    section_space_after_pt: float = 8.0
    passage_indent_inches: float = 0.25
    # Fixed header column widths: side columns fit the logos, the center
    # keeps enough room for the one-line school name.
    header_side_col_inches: float = 1.7
    # Match-the-Following two-column widths (must sum to content width).
    match_col_a_inches: float = 3.38
    match_col_b_inches: float = 3.39
    # Options share one table row only when every option fits this length.
    inline_option_max_chars: int = 40

    def content_width_twips(self, page: "PageConfig") -> int:
        """Printable width in twips (for the right-aligned marks tab stop)."""
        return int(round(
            (page.page_width_inches - page.margin_left_inches
             - page.margin_right_inches) * 1440))


def configure_document(doc, page: PageConfig, style: StyleConfig):
    """Apply A4 page setup and the base Normal style."""
    section = doc.sections[0]
    section.page_width = Inches(page.page_width_inches)
    section.page_height = Inches(page.page_height_inches)
    section.top_margin = Inches(page.margin_top_inches)
    section.bottom_margin = Inches(page.margin_bottom_inches)
    section.left_margin = Inches(page.margin_left_inches)
    section.right_margin = Inches(page.margin_right_inches)

    normal = doc.styles["Normal"]
    normal.font.name = style.body_font
    normal.font.size = Pt(style.body_size_pt)
    normal.paragraph_format.space_after = Pt(style.paragraph_space_after_pt)
    normal.paragraph_format.line_spacing_rule = style.line_spacing_rule
    normal.paragraph_format.widow_control = True
    return section


def add_paragraph(doc, text: str, *, size_pt: float | None = None,
                  bold: bool = False, underline: bool = False,
                  italic: bool = False,
                  align: WD_ALIGN_PARAGRAPH | None = None,
                  space_before_pt: float | None = None,
                  space_after_pt: float | None = None,
                  keep_with_next: bool = False,
                  keep_together: bool = False,
                  font_name: str | None = None):
    """Add one uniformly formatted paragraph."""
    para = doc.add_paragraph()
    run = para.add_run(text)
    cfg = _current_style(doc)
    run.font.size = Pt(size_pt if size_pt is not None else cfg.body_size_pt)
    if font_name or cfg.body_font:
        run.font.name = font_name or cfg.body_font
    run.bold = bold or None
    run.underline = underline or None
    run.italic = italic or None
    if align is not None:
        para.alignment = align
    if space_before_pt is not None:
        para.paragraph_format.space_before = Pt(space_before_pt)
    if space_after_pt is not None:
        para.paragraph_format.space_after = Pt(space_after_pt)
    if keep_with_next:
        para.paragraph_format.keep_with_next = True
    if keep_together:
        para.paragraph_format.keep_together = True
    return para


def _current_style(doc) -> StyleConfig:
    cfg = getattr(doc, "_vps_style_config", None)
    return cfg if cfg is not None else StyleConfig()


def borderless(table) -> None:
    """Make a layout table fully invisible in Word.

    python-docx tables default to the "Table Grid" style, whose visible
    borders survive an empty ``tcBorders`` element (and the default
    template has no borderless table style to switch to). So this writes
    explicit ``nil`` borders at table level and on every cell, which
    override the style grid.
    """
    tblPr = table._tbl.tblPr
    existing = tblPr.find(qn("w:tblBorders"))
    if existing is not None:
        tblPr.remove(existing)
    tblPr.append(_nil_borders("w:tblBorders"))
    for row in table.rows:
        for cell in row.cells:
            tcPr = cell._tc.get_or_add_tcPr()
            old = tcPr.find(qn("w:tcBorders"))
            if old is not None:
                tcPr.remove(old)
            tcPr.append(_nil_borders("w:tcBorders"))


def zero_cell_margins(table) -> None:
    """Remove default cell padding so wide content (school name) fits."""
    tblPr = table._tbl.tblPr
    old = tblPr.find(qn("w:tblCellMar"))
    if old is not None:
        tblPr.remove(old)
    mar = OxmlElement("w:tblCellMar")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:w"), "0")
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tblPr.append(mar)


def _nil_borders(tag: str):
    borders = OxmlElement(tag)
    for edge in _BORDER_EDGES:
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        el.set(qn("w:sz"), "0")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "auto")
        borders.append(el)
    return borders


def add_right_tabstop(paragraph, position_twips: int) -> None:
    """Add a right-aligned tab stop (used for the marks column)."""
    pPr = paragraph._p.get_or_add_pPr()
    tabs = pPr.find(qn("w:tabs"))
    if tabs is None:
        tabs = OxmlElement("w:tabs")
        pPr.append(tabs)
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "right")
    tab.set(qn("w:pos"), str(int(position_twips)))
    tabs.append(tab)
