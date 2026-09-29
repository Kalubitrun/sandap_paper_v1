"""Phase 3: VALIDATION ENGINE (deterministic, explainable, read-only).

Inspects a Phase 2 :class:`NormalizedPaper` and produces a
:class:`ValidationResult`. Never modifies teacher content or the
normalized paper; never renumbers; never invents marks.

Severity policy:
  ERROR   - structurally broken enough that generating a paper may be
            unsafe (duplicates, empty content, missing sections).
  WARNING - suspicious, needs human review (gaps, missing marks, odd
            option counts, analyst-flagged paragraphs).
  INFO    - useful context needing no correction (marks totals,
            unusual-but-legal option counts, handled inline splits).
"""

from __future__ import annotations

from pathlib import Path

from app.models.paper import (
    NormalizedPaper,
    OptionInfo,
    QuestionInfo,
    SectionInfo,
    SubQuestionInfo,
)
from app.parser.analyzer import parse_label
from app.validation.models import ValidationIssue, ValidationResult

# Phase 2 analyst notes that validation re-surfaces (core numbering /
# marks / placement rules are re-derived independently, not trusted).
_ANALYST_NOTE_MAP = {
    "continued_paragraph": ("SUSPICIOUS_CONTINUATION", "warning"),
    "option_without_stem": ("OPTION_WITHOUT_STEM", "warning"),
    "ambiguous_numbering": ("AMBIGUOUS_NUMBERING", "warning"),
    "orphan_labeled_paragraph": ("UNCLASSIFIED_CONTENT", "warning"),
    "orphan_inline_options": ("UNCLASSIFIED_CONTENT", "warning"),
    "unclassified": ("UNCLASSIFIED_CONTENT", "warning"),
    "inline_options": ("INLINE_OPTIONS_SPLIT", "info"),
    "per_item_marks": ("PER_ITEM_MARKS_NOTE", "info"),
}

_ROMAN_VALUES = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
    "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
}


def _label_value(label: str) -> tuple[str, int] | None:
    """Map a normalized label to (kind, int_value) for sequence checks."""
    low = label.lower()
    if low in _ROMAN_VALUES and not (len(low) == 1 and low in ("v", "x")):
        # Single "v"/"x" are letters, not roman numerals.
        return ("roman", _ROMAN_VALUES[low])
    if len(low) == 1 and low.isalpha():
        return ("letter", ord(low) - ord("a") + 1)
    if label.isdigit():
        return ("number", int(label))
    if low in _ROMAN_VALUES:
        return ("roman", _ROMAN_VALUES[low])
    return None


def _sequence_gaps(labels: list[str], *, expect_start: bool) -> list:
    """Find missing labels in an otherwise homogeneous label run.

    Returns the missing labels (same representation as input). Empty
    means sequential. Mixed kinds (letters + numbers) are skipped
    entirely: we do not guess across kinds. With ``expect_start`` the
    run must begin at the first element ('a' / 1 / 'i'); otherwise only
    internal gaps are reported.
    """
    parsed = [_label_value(l) for l in labels]
    if not parsed or any(p is None for p in parsed):
        return []
    kinds = {p[0] for p in parsed}  # type: ignore[union-attr]
    if len(kinds) != 1:
        return []
    kind = next(iter(kinds))
    values = [p[1] for p in parsed]  # type: ignore[union-attr]
    start = min(values) if not expect_start else 1
    missing_vals = [v for v in range(start, max(values)) if v not in values]
    if kind == "letter":
        return [chr(ord("a") + v - 1) for v in missing_vals]
    if kind == "roman":
        inv = {v: k for k, v in _ROMAN_VALUES.items()}
        return [inv[v] for v in missing_vals if v in inv]
    return missing_vals


def _duplicates(items: list) -> list:
    seen: set = set()
    dupes: list = []
    for it in items:
        if it in seen and it not in dupes:
            dupes.append(it)
        seen.add(it)
    return dupes


class _Validator:
    def __init__(self, paper: NormalizedPaper, maximum_marks: int | None = None):
        self.paper = paper
        self.maximum_marks = maximum_marks
        self.issues: list[ValidationIssue] = []

    # -- emit ---------------------------------------------------------
    def issue(self, code: str, severity: str, message: str,
              source_blocks: list[int] | None = None,
              question_number: int | None = None,
              section: str | None = None, **details) -> None:
        self.issues.append(ValidationIssue(
            code=code, severity=severity, message=message,
            source_blocks=list(source_blocks or []),
            question_number=question_number, section=section,
            details=details,
        ))

    def _section_ref(self, section: SectionInfo) -> str | None:
        return section.section_id or None

    def run(self) -> ValidationResult:
        self._check_sections()
        self._check_numbering()
        for section in self.paper.sections:
            for question in section.questions:
                self._check_question(section, question)
        self._check_instructions()
        self._import_analyst_notes()
        self._check_marks_total()
        return ValidationResult(issues=self.issues)

    # -- sections ------------------------------------------------------
    def _check_sections(self) -> None:
        if not self.paper.sections:
            self.issue("NO_SECTIONS", "error", "The paper has no sections.",
                       source_blocks=[])
            return
        for section in self.paper.sections:
            ref = self._section_ref(section)
            if not section.title:
                for q in section.questions:
                    self.issue(
                        "QUESTION_OUTSIDE_SECTION", "warning",
                        f"Q{q.number} appears before any SECTION heading; "
                        "it was not moved.",
                        source_blocks=list(q.source_blocks[:1]),
                        question_number=q.number, section=None,
                    )
            if not section.questions:
                self.issue(
                    "SECTION_WITHOUT_QUESTIONS", "warning",
                    f"Section {ref or '(untitled)'} has no questions.",
                    source_blocks=list(section.source_blocks[:1]),
                    section=ref,
                )
            if section.marks is None and section.title:
                self.issue(
                    "SECTION_MISSING_MARKS", "info",
                    f"No marks annotation detected for section {ref or '(untitled)'}.",
                    source_blocks=list(section.source_blocks[:1]),
                    section=ref,
                )

    # -- numbering ------------------------------------------------------
    def _check_numbering(self) -> None:
        flat: list[tuple[SectionInfo, QuestionInfo]] = [
            (s, q) for s in self.paper.sections for q in s.questions
        ]
        for (prev_s, prev), (cur_s, cur) in zip(flat, flat[1:]):
            cur_ref = self._section_ref(cur_s)
            first_block = list(cur.source_blocks[:1])
            if cur.number == prev.number:
                # Duplicate references are ambiguous: generating output
                # could attach content to the wrong question -> error.
                self.issue(
                    "DUPLICATE_QUESTION_NUMBER", "error",
                    f"Question number Q{cur.number} appears more than once.",
                    source_blocks=first_block,
                    question_number=cur.number, section=cur_ref,
                    duplicate=cur.number,
                )
            elif cur.number > prev.number + 1:
                missing = list(range(prev.number + 1, cur.number))
                self.issue(
                    "QUESTION_NUMBERING_GAP", "warning",
                    f"Question numbering jumps from Q{prev.number} to Q{cur.number}.",
                    source_blocks=first_block,
                    question_number=cur.number, section=cur_ref,
                    previous=prev.number, actual=cur.number, missing=missing,
                )
            elif cur.number < prev.number:
                self.issue(
                    "QUESTION_NUMBERING_OUT_OF_ORDER", "warning",
                    f"Question Q{cur.number} appears after Q{prev.number}.",
                    source_blocks=first_block,
                    question_number=cur.number, section=cur_ref,
                    previous=prev.number, actual=cur.number,
                )

    # -- questions -------------------------------------------------------
    def _check_question(self, section: SectionInfo, q: QuestionInfo) -> None:
        ref = self._section_ref(section)
        first_block = list(q.source_blocks[:1])
        if q.marks is None:
            self.issue(
                "MISSING_MARKS", "warning",
                f"Marks were not detected for Q{q.number}.",
                source_blocks=first_block,
                question_number=q.number, section=ref,
            )
        has_children = bool(q.sub_questions or q.options or q.passage
                              or q.content)
        if not q.text.strip():
            if has_children:
                self.issue(
                    "EMPTY_QUESTION_STEM", "warning",
                    f"Q{q.number} has no header text but has sub-content; "
                    "kept as a container.",
                    source_blocks=first_block,
                    question_number=q.number, section=ref,
                )
            else:
                self.issue(
                    "EMPTY_QUESTION", "error",
                    f"Q{q.number} has no text and no sub-content.",
                    source_blocks=first_block,
                    question_number=q.number, section=ref,
                )
        if q.type in ("mcq", "mcq_group"):
            if not q.sub_questions and not q.options:
                self.issue(
                    "MCQ_WITHOUT_OPTIONS", "warning",
                    f"Q{q.number} looks like an MCQ but has no options or items.",
                    source_blocks=first_block,
                    question_number=q.number, section=ref,
                )
            for sub in q.sub_questions:
                if sub.type == "mcq" and not sub.options:
                    self.issue(
                        "MCQ_WITHOUT_OPTIONS", "warning",
                        f"Q{q.number} item {sub.raw_label} has no options.",
                        source_blocks=list(sub.source_blocks[:1]),
                        question_number=q.number, section=ref,
                        item=sub.label,
                    )
        if q.options:
            self._check_option_list(
                q.options, owner=f"Q{q.number}", question=q, section_ref=ref,
            )
        for sub in q.sub_questions:
            if sub.options:
                self._check_option_list(
                    sub.options, owner=f"Q{q.number} item {sub.raw_label}",
                    question=q, section_ref=ref, item=sub.label,
                )
        self._check_sub_sequence(section, q)

    def _check_option_list(self, options: list[OptionInfo], *, owner: str,
                           question: QuestionInfo, section_ref: str | None,
                           item: str | None = None) -> None:
        labels = [o.label for o in options]
        first_block = list(options[0].source_blocks[:1]) if options else []
        dupes = _duplicates(labels)
        if dupes:
            self.issue(
                "DUPLICATE_OPTION_LABELS", "error",
                f"{owner} has duplicate option label(s): {', '.join(dupes)}.",
                source_blocks=first_block,
                question_number=question.number, section=section_ref,
                labels=dupes, **({"item": item} if item else {}),
            )
        missing = _sequence_gaps(labels, expect_start=True)
        if missing:
            self.issue(
                "MISSING_OPTION_LABEL", "warning",
                f"{owner} is missing option label(s): "
                f"{', '.join(str(m) for m in missing)}; labels were not renamed.",
                source_blocks=first_block,
                question_number=question.number, section=section_ref,
                expected=[labels[0], labels[-1]] if labels else [],
                missing=list(missing),
                **({"item": item} if item else {}),
            )
        texts = [o.text.strip().lower() for o in options]
        dup_texts = _duplicates(texts)
        if dup_texts:
            self.issue(
                "DUPLICATE_OPTION_TEXT", "warning",
                f"{owner} has duplicate option text: {dup_texts[0]!r}.",
                source_blocks=first_block,
                question_number=question.number, section=section_ref,
                text=dup_texts[0], **({"item": item} if item else {}),
            )
        for o in options:
            if not o.text.strip():
                self.issue(
                    "EMPTY_OPTION_TEXT", "error",
                    f"{owner} option {o.raw_label} has no text.",
                    source_blocks=list(o.source_blocks[:1]),
                    question_number=question.number, section=section_ref,
                    label=o.label, **({"item": item} if item else {}),
                )
        # 4 is common but 2/3/more are legal: only suspicious counts warn.
        if len(options) == 1:
            self.issue(
                "FEW_OPTIONS", "warning",
                f"{owner} has only 1 option; an option may be missing.",
                source_blocks=first_block,
                question_number=question.number, section=section_ref,
                count=1, **({"item": item} if item else {}),
            )
        elif len(options) in (2, 3):
            self.issue(
                "UNUSUAL_OPTION_COUNT", "info",
                f"{owner} has {len(options)} options (2-3 is legal, no action needed).",
                source_blocks=first_block,
                question_number=question.number, section=section_ref,
                count=len(options), **({"item": item} if item else {}),
            )

    def _check_sub_sequence(self, section: SectionInfo, q: QuestionInfo) -> None:
        if len(q.sub_questions) < 2:
            return
        labels = [s.label for s in q.sub_questions]
        if _duplicates(labels):
            self.issue(
                "DUPLICATE_SUBQUESTION_LABEL", "error",
                f"Q{q.number} has duplicate sub-question label(s): "
                f"{', '.join(_duplicates(labels))}.",
                source_blocks=list(q.source_blocks[:1]),
                question_number=q.number, section=self._section_ref(section),
                labels=_duplicates(labels),
            )
            return
        missing = _sequence_gaps(labels, expect_start=False)
        if missing:
            self.issue(
                "SUBQUESTION_LABEL_GAP", "warning",
                f"Q{q.number} sub-questions skip label(s): "
                f"{', '.join(str(m) for m in missing)}; labels were not renamed.",
                source_blocks=list(q.source_blocks[:1]),
                question_number=q.number, section=self._section_ref(section),
                sequence=labels,
                missing=list(missing),
            )

    # -- instructions ----------------------------------------------------
    def _check_instructions(self) -> None:
        if not self.paper.instructions:
            self.issue("NO_INSTRUCTIONS", "info",
                       "No general instructions found in the paper.",
                       source_blocks=[])
            return
        if len(self.paper.instructions) < 2:
            head = self.paper.instructions[0]
            self.issue(
                "INSTRUCTIONS_EMPTY", "warning",
                "General Instructions heading found but no instruction items followed.",
                source_blocks=list(head.source_blocks),
            )
            return
        labels: list[str] = []
        for inst in self.paper.instructions[1:]:
            parsed = parse_label(inst.text)
            if parsed is None:
                break  # plain continuation line: not a gap, stop checking
            _, lab, _, _ = parsed
            labels.append(lab)
        if len(labels) >= 2:
            missing = _sequence_gaps(labels, expect_start=False)
            if missing:
                self.issue(
                    "INSTRUCTION_LABEL_GAP", "warning",
                    "Instruction items skip label(s): "
                    f"{', '.join(str(m) for m in missing)}; items were not renamed.",
                    source_blocks=[],
                    sequence=labels,
                    missing=list(missing),
                )

    # -- analyst notes ----------------------------------------------------
    def _import_analyst_notes(self) -> None:
        for w in self.paper.warnings:
            mapped = _ANALYST_NOTE_MAP.get(w.type)
            if mapped is None:
                continue  # core rules re-derived above; ignore the rest
            code, severity = mapped
            details = dict(w.details)
            block = details.pop("source_block", None)
            blocks = [block] if isinstance(block, int) else []
            qnum = self._coerce_question_number(details.pop("question", None))
            self.issue(code, severity, w.message,
                       source_blocks=blocks, question_number=qnum, **details)

    @staticmethod
    def _coerce_question_number(value: object) -> int | None:
        import re as _re
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            m = _re.search(r"(\d+)", value)
            if m:
                return int(m.group(1))
        return None

    # -- marks total -------------------------------------------------------
    def _check_marks_total(self) -> None:
        detected = 0
        derived = 0
        unknown: list[int] = []
        for s in self.paper.sections:
            for q in s.questions:
                contrib = self._question_marks(q)
                if contrib is None:
                    unknown.append(q.number)
                else:
                    value, was_derived = contrib
                    detected += value
                    if was_derived:
                        derived += value
        complete = not unknown
        if complete:
            message = (f"Detected {detected} of {self.maximum_marks} maximum marks."
                       if self.maximum_marks is not None
                       else f"All question marks detected; total {detected}.")
        else:
            message = (f"Detected marks are incomplete ({detected} found so far); "
                       "manual review required.")
        self.issue(
            "MARKS_SUMMARY", "info", message,
            source_blocks=[],
            maximum_marks=self.maximum_marks,
            detected_marks=detected,
            derived_per_item_marks=derived,
            marks_complete=complete,
            unknown_count=len(unknown),
            unknown_questions=unknown,
        )
        if (complete and self.maximum_marks is not None
                and detected != self.maximum_marks):
            self.issue(
                "MARKS_TOTAL_MISMATCH", "warning",
                f"Detected total ({detected}) does not match maximum marks "
                f"({self.maximum_marks}).",
                source_blocks=[],
                maximum_marks=self.maximum_marks,
                detected_marks=detected,
            )

    @staticmethod
    def _question_marks(q: QuestionInfo) -> tuple[int, bool] | None:
        """Reliable marks contribution, or None when unknown.

        per_item marks ("2 marks each") are multiplied by the sub-question
        count only when sub-questions exist; otherwise unknown. Missing
        marks are never treated as zero.
        """
        if q.marks is None:
            return None
        if not q.marks.per_item:
            return q.marks.value, False
        if not q.sub_questions:
            return None
        return q.marks.value * len(q.sub_questions), True


def validate_paper(paper: NormalizedPaper,
                   maximum_marks: int | None = None) -> ValidationResult:
    """Validate a normalized paper without modifying it."""
    return _Validator(paper, maximum_marks).run()


def validate_docx(path: str | Path,
                  maximum_marks: int | None = None) -> ValidationResult:
    """Phase 1 -> Phase 2 -> Phase 3 convenience entry point."""
    from app.parser.analyzer import analyze_docx  # deferred: validator is downstream
    return validate_paper(analyze_docx(path), maximum_marks)
