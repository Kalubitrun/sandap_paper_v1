"""Typed normalized model for Phase 2 structural analysis.

Every normalized object keeps ``source_blocks``: the list of Phase 1
paragraph indexes it was built from, so a future UI can answer
"Where did this content come from?" Original teacher text is never
rewritten: ``raw_text``/``source_text`` hold the untouched cleaned
paragraph text, while ``text`` is the derived normalized form
(numbering prefix / marks annotation stripped).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class MarksInfo:
    value: int
    raw: str  # e.g. "(3)", "[3]", "(5 x 1 = 5)"
    per_item: bool = False  # True for "(2 marks each)" style annotations


@dataclass
class OptionInfo:
    label: str  # normalized lowercase, e.g. "a"
    raw_label: str  # as written, e.g. "A.", "(a)"
    text: str
    source_text: str  # full original paragraph text (for inline-split paras)
    source_blocks: list[int] = field(default_factory=list)


@dataclass
class SubQuestionInfo:
    label: str  # e.g. "a", "1", "ii"
    raw_label: str  # as written, e.g. "a)", "1)", "iii)"
    text: str
    raw_text: str
    type: str = "general"
    marks: MarksInfo | None = None
    options: list[OptionInfo] = field(default_factory=list)
    # Plain continuation paragraphs belonging to this sub-question, in order.
    content: list["ContentBlock"] = field(default_factory=list)
    source_blocks: list[int] = field(default_factory=list)


@dataclass
class ContentBlock:
    """A plain teacher paragraph (passage/extract/continuation) kept verbatim."""

    text: str
    source_blocks: list[int] = field(default_factory=list)


@dataclass
class QuestionInfo:
    number: int
    raw_number: str  # as written, e.g. "Q1"
    text: str
    raw_text: str  # full header text incl. numbering prefix and marks
    type: str = "general"  # mcq_group | mcq | fill_blanks | true_false | case_study | short_notes | general
    marks: MarksInfo | None = None
    options: list[OptionInfo] = field(default_factory=list)
    sub_questions: list[SubQuestionInfo] = field(default_factory=list)
    passage: str | None = None  # case-study passage text, if any
    passage_blocks: list[int] = field(default_factory=list)
    # Plain continuation paragraphs belonging to this question, in order.
    content: list[ContentBlock] = field(default_factory=list)
    source_blocks: list[int] = field(default_factory=list)


@dataclass
class SectionInfo:
    title: str  # original heading text preserved
    section_id: str = ""  # e.g. "A", "B"
    marks: MarksInfo | None = None
    questions: list[QuestionInfo] = field(default_factory=list)
    source_blocks: list[int] = field(default_factory=list)


@dataclass
class InstructionInfo:
    text: str
    source_blocks: list[int] = field(default_factory=list)


@dataclass
class MetadataField:
    key: str  # school | exam_title | class | subject | subject_code | time | max_marks
    text: str
    source_block: int


@dataclass
class WarningInfo:
    type: str  # numbering_gap | missing_marks | inline_options | unclassified | ...
    message: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"type": self.type, "message": self.message, **self.details}


@dataclass
class NormalizedPaper:
    metadata: list[MetadataField] = field(default_factory=list)
    instructions: list[InstructionInfo] = field(default_factory=list)
    sections: list[SectionInfo] = field(default_factory=list)
    warnings: list[WarningInfo] = field(default_factory=list)
    end_marker: dict | None = None  # {"text": ..., "source_block": ...}

    def to_dict(self) -> dict:
        return {
            "metadata": [asdict(m) for m in self.metadata],
            "instructions": [asdict(i) for i in self.instructions],
            "sections": [
                {
                    "title": s.title,
                    "section_id": s.section_id,
                    "marks": asdict(s.marks) if s.marks else None,
                    "questions": [
                        {
                            "number": q.number,
                            "raw_number": q.raw_number,
                            "type": q.type,
                            "text": q.text,
                            "raw_text": q.raw_text,
                            "marks": asdict(q.marks) if q.marks else None,
                            "options": [asdict(o) for o in q.options],
                            "sub_questions": [asdict(sq) for sq in q.sub_questions],
                            "passage": q.passage,
                            "passage_blocks": q.passage_blocks,
                            "content": [asdict(c) for c in q.content],
                            "source_blocks": q.source_blocks,
                        }
                        for q in s.questions
                    ],
                    "source_blocks": s.source_blocks,
                }
                for s in self.sections
            ],
            "warnings": [w.to_dict() for w in self.warnings],
            "end_marker": self.end_marker,
        }
