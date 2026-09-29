"""General instructions block (Phase 5). Teacher wording rendered verbatim."""

from __future__ import annotations

from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.renderer.styles import StyleConfig, add_paragraph


def render_instructions(doc, instructions, style: StyleConfig) -> None:
    if not instructions:
        return
    head, *items = instructions
    head_text = head.text.strip()
    add_paragraph(doc, head_text if head_text.endswith(":") else f"{head_text}:",
                  size_pt=style.instruction_size_pt, bold=True,
                  space_before_pt=style.section_space_before_pt,
                  space_after_pt=style.question_space_after_pt,
                  keep_with_next=bool(items))
    for item in items:
        add_paragraph(doc, item.text, size_pt=style.instruction_size_pt,
                      space_after_pt=style.instruction_space_after_pt)
