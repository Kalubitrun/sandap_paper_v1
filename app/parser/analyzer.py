"""Phase 2: STRUCTURAL ANALYSIS (rule-based, deterministic, explainable).

Converts a Phase 1 :class:`RawDocument` into a :class:`NormalizedPaper`
without touching the DOCX and without rewriting teacher content.

Disambiguation rules (in priority order per paragraph):
  1. blank -> skip
  2. END marker -> end of paper
  3. SECTION heading (``^SECTION <id>``)
  4. "General Instructions" heading -> following lettered paras are
     instruction items until the next section / main question / END
  5. metadata keywords -> only while still in the preamble (before any
     instructions / section / question)
  6. Q-prefixed main question: ``Q1.`` ``Q1)`` ``Q1:`` ``Question 1``
  7. bare number ``1.`` ``1)`` ``1 -``: a main question only when no
     question is open (or when the document uses no Q-prefixes at all);
     otherwise a child item of the open question. Rationale: in a paper
     that already numbers mains as Q1..Qn, a bare "1." under Q1 is an
     item belonging to Q1, not a new main question.
  8. lettered ``a)`` ``(a)`` ``A.`` ``A)`` / roman ``i)`` ``ii)``:
     - instruction item while inside the instructions block
     - option of the current MCQ item while inside an mcq/mcq_group
       question that already has an open numbered item
     - otherwise a sub-question of the open question
  9. one paragraph holding several options (label-boundary scan over
     ``original_text``; single or multiple spaces both work) -> options
     of the current MCQ item
 10. plain text -> case-study passage (if a case_study question is open
     and has no sub-questions yet), else a ContentBlock continuation kept
     verbatim under the current owner with a warning, else unclassified
     warning.

Numbering is NEVER rewritten: jumps produce ``numbering_gap`` warnings.
Marks are NEVER invented: absent marks produce ``missing_marks`` warnings.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.models.document import RawDocument
from app.models.paper import (
    ContentBlock,
    InstructionInfo,
    MarksInfo,
    MetadataField,
    NormalizedPaper,
    OptionInfo,
    QuestionInfo,
    SectionInfo,
    SubQuestionInfo,
    WarningInfo,
)
from app.parser.extractor import extract_document

# ---------------------------------------------------------------- patterns

SECTION_RE = re.compile(r"^\s*SECTION\s+([A-Z0-9]+)\b\s*(.*)$", re.IGNORECASE)
INSTRUCTIONS_HEAD_RE = re.compile(r"^\s*General Instructions\b", re.IGNORECASE)
END_RE = re.compile(r"^\s*END\s*$", re.IGNORECASE)

# Q1. / Q1) / Q1: / Q 12 / Question 1 / QUESTION 3:
MAIN_Q_RE = re.compile(
    r"^\s*(?:Q\s*\.?\s*(\d+)|Question\s+(\d+))\s*[.\)\]:\-]?\s*(.*)$",
    re.IGNORECASE,
)
# 1. / 1) / 1 - / 1:  (rest may be empty)
BARE_NUM_RE = re.compile(r"^\s*(\d+)\s*([.\)\-:])\s*(.*)$")
# (a) X  (parens are the delimiter, no extra punct needed)
PAREN_LETTER_RE = re.compile(r"^\s*\(\s*([A-Za-z])\s*\)\s+(.*)$")
# a) X / A. X / A) X
LETTER_RE = re.compile(r"^\s*([A-Za-z])\s*[.)]\s+(.*)$")
# i) / ii) / iii) / iv) / vi) ... (checked before LETTER_RE)
ROMAN_RE = re.compile(
    r"^\s*\(?\s*(i{1,3}|iv|vi{0,3}|vii|viii|ix|x)\s*\)?\s*[.)]\s+(.*)$",
    re.IGNORECASE,
)

# Marks patterns, applied in order (first match wins).
_MARKS_RES = [
    ("split", re.compile(r"\(\s*(\d+)\s*[x×]\s*(\d+)\s*=\s*(\d+)\s*\)")),
    ("bracket", re.compile(r"\[\s*(\d+)\s*\]")),
    ("paren_marks", re.compile(r"\(\s*(\d+)\s*marks?\s*(each)?\s*\)", re.IGNORECASE)),
    ("paren_num", re.compile(r"\(\s*(\d+)\s*\)")),
    ("bare_marks", re.compile(r"(?<!\w)(\d+)\s*marks?\b(\s*each\b)?", re.IGNORECASE)),
    ("bare_num_marks", re.compile(r"Maximum\s+Marks?\s+(\d+)", re.IGNORECASE)),
]

# A single inline option label: "(a)" / "a)" / "a." / "A." anchored at
# start-of-text or after whitespace and followed by whitespace. Single
# spaces between options are enough; the boundary scan below decides.
_INLINE_LABEL_RE = re.compile(
    r"(?:^|(?<=\s))(?:\(\s*([a-zA-Z])\s*\)|([a-zA-Z])\s*[).])(?=\s)"
)

_QUESTION_TYPE_KEYWORDS = [
    ("mcq_group", re.compile(r"choose the correct|correct answer|multiple choice|\bmcq\b", re.I)),
    ("fill_blanks", re.compile(r"fill in the blank", re.I)),
    ("true_false", re.compile(r"true or false", re.I)),
    ("case_study", re.compile(r"case study", re.I)),
    ("short_notes", re.compile(r"short notes?", re.I)),
]

_METADATA_RULES = [
    ("subject_code", re.compile(r"subject\s*code", re.I)),
    ("subject", re.compile(r"^\s*subject\b", re.I)),
    ("class", re.compile(r"^\s*class\b", re.I)),
    ("time", re.compile(r"^\s*time\b", re.I)),
    ("max_marks", re.compile(r"maximum\s*marks?", re.I)),
    ("school", re.compile(r"school", re.I)),
    ("exam_title", re.compile(r"exam", re.I)),
]

_MCQ_PARENT_TYPES = ("mcq", "mcq_group")

# ---------------------------------------------------------------- helpers


def parse_marks(text: str) -> tuple[MarksInfo | None, str]:
    """Extract marks from text. Returns (marks_or_None, text_with_marks_removed)."""
    for kind, rx in _MARKS_RES:
        m = rx.search(text)
        if not m:
            continue
        if kind == "split":
            value = int(m.group(3))
            return MarksInfo(value=value, raw=m.group(0), per_item=False), _strip_once(text, m)
        if kind == "paren_marks":
            per_item = m.group(2) is not None
            return MarksInfo(value=int(m.group(1)), raw=m.group(0), per_item=per_item), _strip_once(text, m)
        if kind == "bare_marks":
            per_item = m.group(2) is not None and m.group(2).strip() != ""
            return MarksInfo(value=int(m.group(1)), raw=m.group(0).strip(), per_item=per_item), _strip_once(text, m)
        return MarksInfo(value=int(m.group(1)), raw=m.group(0), per_item=False), _strip_once(text, m)
    return None, text


def _strip_once(text: str, m: re.Match) -> str:
    cleaned = (text[: m.start()] + " " + text[m.end() :]).strip()
    return re.sub(r"\s+", " ", cleaned).strip(" -–—:;,")


def parse_main_question(text: str) -> tuple[int, str] | None:
    """Q-prefixed main question -> (number, rest)."""
    m = MAIN_Q_RE.match(text)
    if not m:
        return None
    # Guard: "Q" alone with no digits cannot match (regex requires digits),
    # but "Quality ..." etc. never match either since digits are mandatory.
    num = m.group(1) if m.group(1) is not None else m.group(2)
    return int(num), m.group(3).strip()


def parse_bare_number(text: str) -> tuple[str, str, str] | None:
    """Bare number -> (label, raw_label, rest). raw_label keeps the original separator."""
    m = BARE_NUM_RE.match(text)
    if not m:
        return None
    return m.group(1), f"{m.group(1)}{m.group(2)}", m.group(3).strip()


def parse_label(text: str) -> tuple[str, str, str, str] | None:
    """Letter/roman label -> (kind, label, raw_label, rest).

    kind is "roman" or "letter". label is normalized lowercase.
    """
    m = ROMAN_RE.match(text)
    if m:
        label = m.group(1).lower()
        raw_label = text[: m.start(2)].strip()
        return "roman", label, raw_label, m.group(2).strip()
    m = PAREN_LETTER_RE.match(text)
    if m:
        return "letter", m.group(1).lower(), f"({m.group(1)})", m.group(2).strip()
    m = LETTER_RE.match(text)
    if m:
        punct = _punct_after_letter(text, m.group(1))
        return "letter", m.group(1).lower(), f"{m.group(1)}{punct}", m.group(2).strip()
    return None


def _punct_after_letter(text: str, letter: str) -> str:
    m = re.match(r"^\s*" + re.escape(letter) + r"\s*([.)])", text)
    return m.group(1) if m else ")"


def split_inline_options(original_text: str) -> list[tuple[str, str, str]] | None:
    """Split "a) Email b) CPU ..." into [(label, raw_label, text)].

    Works with any spacing (single or multiple spaces) between options.
    Uses ``original_text`` (spacing intact). Returns None unless the
    paragraph holds >= 2 labels that:
      - start at the very beginning of the paragraph,
      - are single letters forming a consecutive run from 'a'
        (a, b, c, d — any of ``)`` / ``.`` / ``(...)`` spellings),
      - each carry non-empty text.
    Anything else (single option, gap in labels, label not at the start)
    returns None so the caller falls back to single-label handling
    instead of guessing.
    """
    text = original_text.strip()
    matches = list(_INLINE_LABEL_RE.finditer(text))
    if len(matches) < 2 or matches[0].start() != 0:
        return None
    out: list[tuple[str, str, str]] = []
    for i, m in enumerate(matches):
        label = (m.group(1) or m.group(2)).lower()
        raw_label = m.group(0).strip()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        rest = re.sub(r"\s+", " ", text[m.end():end]).strip()
        if not rest:
            return None
        out.append((label, raw_label, rest))
    labels = [label for label, _, _ in out]
    if labels[0] != "a" or [ord(l) - ord("a") for l in labels] != list(range(len(labels))):
        return None
    return out


def detect_metadata_key(text: str) -> str | None:
    for key, rx in _METADATA_RULES:
        if rx.search(text):
            return key
    return None


def classify_question_type(header_rest: str) -> str:
    for qtype, rx in _QUESTION_TYPE_KEYWORDS:
        if rx.search(header_rest):
            return qtype
    return "general"


# ---------------------------------------------------------------- analyzer


class _Analyzer:
    def __init__(self, raw: RawDocument):
        self.raw = raw
        self.paper = NormalizedPaper()
        self.section: SectionInfo | None = None
        self.question: QuestionInfo | None = None
        self.item: SubQuestionInfo | None = None  # open MCQ item taking options
        self.in_instructions = False
        self.preamble = True  # before first instructions/section/question
        self.has_q_prefix = any(
            not p.is_empty and parse_main_question(p.cleaned_text) is not None
            for p in raw.paragraphs
        )

    # -- emit helpers -------------------------------------------------
    def warn(self, wtype: str, message: str, **details) -> None:
        self.paper.warnings.append(WarningInfo(type=wtype, message=message, details=details))

    def _ensure_section(self, idx: int) -> SectionInfo:
        if self.section is None:
            self.section = SectionInfo(title="", section_id="", source_blocks=[])
            self.paper.sections.append(self.section)
            self.warn(
                "question_outside_section",
                f"Paragraph {idx} starts a question before any SECTION heading; "
                "placed in an implicit section.",
                source_block=idx,
            )
        return self.section

    def _close_question(self) -> None:
        self.question = None
        self.item = None

    # -- main loop ----------------------------------------------------
    def run(self) -> NormalizedPaper:
        for p in self.raw.paragraphs:
            if p.is_empty:
                continue
            self._handle(p.index, p.original_text, p.cleaned_text)
        self._validate_numbering()
        self._check_missing_marks()
        return self.paper

    def _handle(self, idx: int, original: str, text: str) -> None:
        if END_RE.match(text):
            self._close_question()
            self.in_instructions = False
            self.paper.end_marker = {"text": text, "source_block": idx}
            return

        m = SECTION_RE.match(text)
        if m:
            self._open_section(idx, text, m.group(1), m.group(2))
            return

        if INSTRUCTIONS_HEAD_RE.match(text):
            self._close_question()
            self.in_instructions = True
            self.preamble = False
            self.paper.instructions.append(InstructionInfo(text=text, source_blocks=[idx]))
            return

        parsed_q = parse_main_question(text)
        bare = parse_bare_number(text) if parsed_q is None else None
        # Inline check before single-label: a paragraph like
        # "a) Email    b) CPU ..." also parses as a single "a)" label,
        # so the multi-option split must take priority (it only fires
        # when >= 2 chunks all parse as options).
        inline = split_inline_options(original) if bare is None else None
        label = parse_label(text) if bare is None and inline is None else None

        if self.preamble:
            # Preamble claims only plain, unlabeled text (school name,
            # exam title, ...). Anything with a number/label falls through
            # to normal handling so a paper starting directly with "Q1."
            # is not swallowed as metadata.
            if parsed_q is None and bare is None and label is None and inline is None:
                key = detect_metadata_key(text)
                if key is not None:
                    self.paper.metadata.append(
                        MetadataField(key=key, text=text, source_block=idx)
                    )
                    return
                # Non-metadata preamble text (e.g. date line): keep, don't guess.
                self.warn(
                    "unclassified",
                    f"Paragraph {idx} in the preamble matches no metadata pattern; kept as-is.",
                    source_block=idx,
                    text=text,
                )
                self.paper.metadata.append(
                    MetadataField(key="other", text=text, source_block=idx)
                )
                return
            self.preamble = False

        if parsed_q is not None:
            self._open_question(idx, text, *parsed_q)
            return

        if inline is not None:
            self._add_inline_options(idx, original, inline)
            return

        if self.in_instructions and label is not None:
            kind, lab, raw_lab, rest = label
            self.paper.instructions.append(
                InstructionInfo(text=text, source_blocks=[idx])
            )
            return

        if self.in_instructions and bare is None and label is None:
            # Plain paragraph inside instructions block -> keep as instruction line.
            self.paper.instructions.append(
                InstructionInfo(text=text, source_blocks=[idx])
            )
            return

        if bare is not None:
            num_label, raw_label, rest = bare
            self._add_numbered(idx, text, num_label, raw_label, rest)
            return

        if label is not None:
            kind, lab, raw_lab, rest = label
            self._add_labeled(idx, text, kind, lab, raw_lab, rest)
            return

        self._add_plain(idx, text)

    # -- section / question -------------------------------------------
    def _open_section(self, idx: int, text: str, sid: str, rest: str) -> None:
        self._close_question()
        self.in_instructions = False
        self.preamble = False
        marks, _ = parse_marks(text)
        self.section = SectionInfo(
            title=text, section_id=sid, marks=marks, source_blocks=[idx]
        )
        self.paper.sections.append(self.section)

    def _open_question(self, idx: int, text: str, number: int, rest: str) -> None:
        section = self._ensure_section(idx)
        self.in_instructions = False
        self.preamble = False
        marks, clean_rest = parse_marks(rest)
        qtype = classify_question_type(rest)
        if marks is not None and marks.per_item:
            self.warn(
                "per_item_marks",
                f"Q{number} carries per-item marks {marks.raw}; stored at question "
                "level only, not distributed to sub-questions.",
                question=f"Q{number}",
                source_block=idx,
                marks=marks.raw,
            )
        self.question = QuestionInfo(
            number=number,
            raw_number=f"Q{number}",
            text=clean_rest,
            raw_text=text,
            type=qtype,
            marks=marks,
            source_blocks=[idx],
        )
        self.item = None
        section.questions.append(self.question)
        section.source_blocks.append(idx)

    # -- children ------------------------------------------------------
    def _add_numbered(self, idx: int, text: str, num_label: str, raw_label: str, rest: str) -> None:
        if self.question is None:
            # No open question: with Q-style papers this is ambiguous.
            if self.has_q_prefix:
                self.warn(
                    "ambiguous_numbering",
                    f"Paragraph {idx} looks like a numbered item ({num_label}) but no "
                    "question is open; treated as a main question.",
                    source_block=idx,
                    text=text,
                )
            section = self._ensure_section(idx)
            self.in_instructions = False
            marks, clean_rest = parse_marks(rest)
            self.question = QuestionInfo(
                number=int(num_label),
                raw_number=num_label,
                text=clean_rest,
                raw_text=text,
                type="general",
                marks=marks,
                source_blocks=[idx],
            )
            self.item = None
            section.questions.append(self.question)
            section.source_blocks.append(idx)
            return
        marks, clean_rest = parse_marks(rest)
        if self.question.type in _MCQ_PARENT_TYPES:
            sub = SubQuestionInfo(
                label=num_label,
                raw_label=raw_label,
                text=clean_rest,
                raw_text=text,
                type="mcq",
                marks=marks,
                source_blocks=[idx],
            )
            self.question.sub_questions.append(sub)
            self.question.source_blocks.append(idx)
            self.item = sub
        else:
            sub = SubQuestionInfo(
                label=num_label,
                raw_label=raw_label,
                text=clean_rest,
                raw_text=text,
                type=self.question.type,
                marks=marks,
                source_blocks=[idx],
            )
            self.question.sub_questions.append(sub)
            self.question.source_blocks.append(idx)
            self.item = None

    def _add_labeled(
        self, idx: int, text: str, kind: str, lab: str, raw_lab: str, rest: str
    ) -> None:
        if self.question is None:
            self.warn(
                "orphan_labeled_paragraph",
                f"Paragraph {idx} has label {raw_lab} but no question is open; kept as-is.",
                source_block=idx,
                text=text,
            )
            return
        marks, clean_rest = parse_marks(rest)
        if (
            kind == "letter"
            and self.item is not None
            and self.question.type in _MCQ_PARENT_TYPES
        ):
            self.item.options.append(
                OptionInfo(
                    label=lab, raw_label=raw_lab, text=clean_rest,
                    source_text=text, source_blocks=[idx],
                )
            )
            self.item.source_blocks.append(idx)
            self.question.source_blocks.append(idx)
            return
        sub = SubQuestionInfo(
            label=lab,
            raw_label=raw_lab,
            text=clean_rest,
            raw_text=text,
            type=self.question.type if kind != "letter" else self._sub_type_for_letter(),
            marks=marks,
            source_blocks=[idx],
        )
        self.question.sub_questions.append(sub)
        self.question.source_blocks.append(idx)
        self.item = None

    def _sub_type_for_letter(self) -> str:
        assert self.question is not None
        if self.question.type in _MCQ_PARENT_TYPES:
            # Lettered line directly under an MCQ header with no open
            # numbered item: ambiguous (option without stem?). Keep as a
            # sub-question and flag it rather than guessing.
            self.warn(
                "option_without_stem",
                f"Lettered paragraph under {self.question.raw_number} has no numbered "
                "stem above it; kept as a sub-question instead of an option.",
                question=self.question.raw_number,
                source_block=self.question.source_blocks[-1],
            )
            return "mcq"
        return self.question.type

    def _add_inline_options(
        self, idx: int, original: str, opts: list[tuple[str, str, str]]
    ) -> None:
        labels = [o[0] for o in opts]
        if self.question is None or (
            self.question.type in _MCQ_PARENT_TYPES and self.item is None
        ):
            self.warn(
                "orphan_inline_options",
                f"Paragraph {idx} holds inline options ({', '.join(labels)}) but there "
                "is no open item to attach them to; kept as-is.",
                source_block=idx,
                text=original.strip(),
            )
            return
        target = self.item if self.question.type in _MCQ_PARENT_TYPES else None
        if target is None:
            # Inline options under a non-MCQ question: attach to last
            # sub-question if any, else flag.
            if self.question.sub_questions:
                target_sq = self.question.sub_questions[-1]
                for lab, raw_lab, rest in opts:
                    target_sq.options.append(
                        OptionInfo(label=lab, raw_label=raw_lab, text=rest,
                                   source_text=original.strip(), source_blocks=[idx])
                    )
                    target_sq.source_blocks.append(idx)
                self.question.source_blocks.append(idx)
                self.warn(
                    "inline_options",
                    f"Paragraph {idx} holds inline options ({', '.join(labels)}); split "
                    f"into {len(opts)} options under sub-question "
                    f"{target_sq.raw_label}; original paragraph preserved in source_text.",
                    source_block=idx,
                    question=self.question.raw_number,
                )
                return
            self.warn(
                "orphan_inline_options",
                f"Paragraph {idx} holds inline options but there is no open item; kept as-is.",
                source_block=idx,
                text=original.strip(),
            )
            return
        for lab, raw_lab, rest in opts:
            target.options.append(
                OptionInfo(label=lab, raw_label=raw_lab, text=rest,
                           source_text=original.strip(), source_blocks=[idx])
            )
            target.source_blocks.append(idx)
        self.question.source_blocks.append(idx)
        self.warn(
            "inline_options",
            f"Paragraph {idx} holds inline options ({', '.join(labels)}); split into "
            f"{len(opts)} options under item {target.raw_label}; original paragraph "
            "preserved in source_text.",
            source_block=idx,
            question=self.question.raw_number,
        )

    def _add_plain(self, idx: int, text: str) -> None:
        if self.question is not None and (
            self.question.type == "case_study"
            and not self.question.sub_questions
            and self.question.passage is None
        ):
            self.question.passage = text
            self.question.passage_blocks = [idx]
            self.question.source_blocks.append(idx)
            return
        if self.question is not None:
            # Continuations are stored as structured content blocks (never
            # merged into header/sub text) so the renderer can place every
            # teacher paragraph instead of silently dropping it.
            owner = self.item if self.item is not None else self.question
            owner.content.append(ContentBlock(text=text, source_blocks=[idx]))
            owner.source_blocks.append(idx)
            self.question.source_blocks.append(idx)
            self.warn(
                "continued_paragraph",
                f"Paragraph {idx} has no label; kept as continuation content "
                f"under {self.question.raw_number}.",
                source_block=idx,
                question=self.question.raw_number,
            )
            return
        self.warn(
            "unclassified",
            f"Paragraph {idx} matches no rule and no question is open; kept as-is.",
            source_block=idx,
            text=text,
        )

    # -- validation ----------------------------------------------------
    def _validate_numbering(self) -> None:
        flat: list[QuestionInfo] = [q for s in self.paper.sections for q in s.questions]
        for prev, cur in zip(flat, flat[1:]):
            if cur.number == prev.number:
                self.warn(
                    "duplicate_question_number",
                    f"Question number Q{cur.number} appears more than once.",
                    actual=f"Q{cur.number}",
                    source_block=cur.source_blocks[0] if cur.source_blocks else None,
                )
            elif cur.number > prev.number + 1:
                expected = [f"Q{n}" for n in range(prev.number + 1, cur.number)]
                self.warn(
                    "numbering_gap",
                    f"Question numbering jumps from Q{prev.number} to Q{cur.number}.",
                    expected=expected,
                    actual=f"Q{cur.number}",
                    source_block=cur.source_blocks[0] if cur.source_blocks else None,
                )
            elif cur.number < prev.number:
                self.warn(
                    "numbering_out_of_order",
                    f"Question Q{cur.number} appears after Q{prev.number}.",
                    actual=f"Q{cur.number}",
                    source_block=cur.source_blocks[0] if cur.source_blocks else None,
                )

    def _check_missing_marks(self) -> None:
        for s in self.paper.sections:
            for q in s.questions:
                if q.marks is None:
                    self.warn(
                        "missing_marks",
                        f"{q.raw_number} has no marks annotation.",
                        question=q.raw_number,
                        source_block=q.source_blocks[0] if q.source_blocks else None,
                    )


def analyze_document(raw: RawDocument) -> NormalizedPaper:
    """Convert a Phase 1 RawDocument into a normalized question-paper structure."""
    return _Analyzer(raw).run()


def analyze_docx(path: str | Path) -> NormalizedPaper:
    """Load a DOCX file (Phase 1) and analyze it (Phase 2)."""
    return analyze_document(extract_document(path))
