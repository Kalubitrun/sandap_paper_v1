"""Document orchestrator (Phase 5).

Clean API:

    render_question_paper(paper, school_config, paper_settings,
                          validation_result, output_path)

ERROR-level validation findings block generation (RenderBlockedError).
WARNING/INFO findings allow generation; nothing is auto-corrected.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document

from app.renderer.config import PaperSettings, SchoolConfig
from app.renderer.footer import render_footer
from app.renderer.header import render_header
from app.renderer.instructions import render_instructions
from app.renderer.questions import render_end_marker, render_question
from app.renderer.sections import render_section_heading
from app.renderer.styles import PageConfig, StyleConfig, configure_document


class RenderBlockedError(RuntimeError):
    """Raised when ERROR-level validation findings block generation."""


def render_question_paper(paper, school_config: SchoolConfig | None = None,
                          paper_settings: PaperSettings | None = None,
                          validation_result=None,
                          output_path: str | Path = "output/vps_question_paper.docx",
                          page_config: PageConfig | None = None,
                          style_config: StyleConfig | None = None) -> Path:
    if validation_result is not None and validation_result.has_errors:
        codes = sorted({i.code for i in validation_result.errors})
        raise RenderBlockedError(
            f"Generation blocked by ERROR-level findings: {', '.join(codes)}"
        )
    school_config = school_config or SchoolConfig()
    paper_settings = paper_settings or PaperSettings()
    page_config = page_config or PageConfig()
    style_config = style_config or StyleConfig()

    doc = Document()
    doc._vps_style_config = style_config
    configure_document(doc, page_config, style_config)
    marks_tab_twips = style_config.content_width_twips(page_config)
    content_width_inches = (page_config.page_width_inches
                            - page_config.margin_left_inches
                            - page_config.margin_right_inches)

    render_header(doc, school_config, paper_settings, style_config,
                  content_width_inches)
    render_instructions(doc, paper.instructions, style_config)
    for section in paper.sections:
        if section.title:
            render_section_heading(doc, section.title, style_config)
        for question in section.questions:
            render_question(doc, question, style_config, marks_tab_twips)
    render_end_marker(doc, paper.end_marker, style_config)
    render_footer(doc, style_config)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    return out
