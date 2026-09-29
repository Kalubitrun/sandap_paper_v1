"""Section headings (Phase 5). Titles rendered verbatim from the normalized paper."""

from __future__ import annotations

from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.renderer.styles import StyleConfig, add_paragraph


def render_section_heading(doc, title: str, style: StyleConfig) -> None:
    add_paragraph(doc, title, size_pt=style.section_heading_size_pt,
                  bold=True, underline=True,
                  align=WD_ALIGN_PARAGRAPH.CENTER,
                  space_before_pt=style.section_space_before_pt,
                  space_after_pt=style.section_space_after_pt,
                  keep_with_next=True)
