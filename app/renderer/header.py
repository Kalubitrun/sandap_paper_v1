"""School header block (Phase 5).

Layout uses borderless tables (never spaces) so alignment survives in
Microsoft Word. The project logo (logo.webp) is converted to PNG
in-memory via Pillow because Word cannot reliably embed webp; the image
itself is untouched and aspect ratio is preserved.
"""

from __future__ import annotations

from io import BytesIO

from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

from app.renderer.config import PaperSettings, SchoolConfig
from app.renderer.styles import StyleConfig, add_paragraph, borderless, zero_cell_margins


def _logo_png_bytes(path) -> BytesIO | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(path) as im:
            buf = BytesIO()
            im.save(buf, format="PNG")
    except (OSError, ValueError):
        return None
    buf.seek(0)
    return buf


def _add_logo(cell, path, width_inches: float) -> bool:
    buf = _logo_png_bytes(path) if path else None
    if buf is None:
        return False
    para = cell.paragraphs[0]
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.add_run().add_picture(buf, width=Inches(width_inches))
    return True


def _separator(doc) -> None:
    """Horizontal rule via paragraph border (never typed characters)."""
    sep = doc.add_paragraph()
    pPr = sep._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), "000000")
    pBdr.append(bottom)
    pPr.append(pBdr)


def render_header(doc, school: SchoolConfig, settings: PaperSettings,
                  style: StyleConfig, content_width_inches: float | None = None) -> None:
    # Row 1: affiliation (left) / school number (right).
    top = doc.add_table(rows=1, cols=2)
    top.autofit = True
    borderless(top)
    left = top.cell(0, 0).paragraphs[0]
    left.add_run(f"Affiliation No. - {school.affiliation_number}")
    left.runs[0].font.size = Pt(style.body_size_pt)
    right = top.cell(0, 1).paragraphs[0]
    right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    right.add_run(f"School No. - {school.school_number}")
    right.runs[0].font.size = Pt(style.body_size_pt)

    # Main header: logo | school name + address | logo mirrored right
    # (same emblem on both sides when no separate emblem is configured).
    # Fixed layout with explicit widths: the center column keeps enough
    # room for the one-line school name, side columns fit the logos.
    head = doc.add_table(rows=1, cols=3)
    head.autofit = False
    borderless(head)
    zero_cell_margins(head)
    if content_width_inches is not None:
        from docx.shared import Inches as _Inches
        side = school.logo_width_inches + 0.1
        # Column widths keep gridCol in sync (fixed layout reads gridCol).
        for col, width in zip(head.columns,
                              (side, content_width_inches - 2 * side, side)):
            col.width = _Inches(width)
    # Center column gets the remaining printable width implicitly.
    for cell in head.row_cells(0):
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    _add_logo(head.cell(0, 0), school.logo_path, school.logo_width_inches)

    center = head.cell(0, 1)
    name_para = center.paragraphs[0]
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = name_para.add_run(school.name)
    name_run.bold = True
    name_run.font.size = Pt(style.school_name_size_pt)
    addr_para = center.add_paragraph()
    addr_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    addr_run = addr_para.add_run(school.address)
    addr_run.font.size = Pt(style.address_size_pt)
    if school.phone_number:
        phone_para = center.add_paragraph()
        phone_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        phone_run = phone_para.add_run(f"Phone: {school.phone_number}")
        phone_run.font.size = Pt(style.address_size_pt)

    right_logo = school.emblem_path or (
        school.logo_path if school.use_logo_both_sides else None)
    if right_logo:
        _add_logo(head.cell(0, 2), right_logo, school.logo_width_inches)

    # Examination information block: prominent exam name, session below it.
    add_paragraph(doc, settings.examination,
                  size_pt=style.exam_info_size_pt, bold=True,
                  align=WD_ALIGN_PARAGRAPH.CENTER,
                  space_after_pt=0)
    add_paragraph(doc, f"({settings.session})",
                  size_pt=style.exam_info_size_pt, bold=True,
                  align=WD_ALIGN_PARAGRAPH.CENTER)
    add_paragraph(doc, f"CLASS- {settings.class_name}",
                  size_pt=style.exam_detail_size_pt, bold=True,
                  align=WD_ALIGN_PARAGRAPH.CENTER,
                  space_after_pt=0)
    add_paragraph(doc, f"Subject- {settings.subject} ({settings.subject_code})",
                  size_pt=style.exam_detail_size_pt, bold=True,
                  align=WD_ALIGN_PARAGRAPH.CENTER)

    _separator(doc)

    # Time (left) / Max marks (right), borderless table (never spaces).
    row = doc.add_table(rows=1, cols=2)
    row.autofit = True
    borderless(row)
    tcell = row.cell(0, 0).paragraphs[0]
    tcell.add_run(f"Time: {settings.time}")
    tcell.runs[0].font.size = Pt(style.exam_detail_size_pt)
    tcell.runs[0].bold = True
    mcell = row.cell(0, 1).paragraphs[0]
    mcell.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    mcell.add_run(f"M.M.: {settings.max_marks}")
    mcell.runs[0].font.size = Pt(style.exam_detail_size_pt)
    mcell.runs[0].bold = True

    _separator(doc)
