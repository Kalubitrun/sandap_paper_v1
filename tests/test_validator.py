"""Phase 3 tests: validation engine over NormalizedPaper.

Covers: numbering gaps/duplicates, missing/detected/maximum marks,
sections, empty questions, options, sub-question gaps, instruction
gaps, unclassified content, and preservation of the normalized data.
"""

from __future__ import annotations

import copy

from app.models.paper import (
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
from app.parser.analyzer import analyze_document
from app.parser.extractor import clean_text, extract_document
from app.models.document import ParagraphInfo, RawDocument, RunInfo
from app.validation import validate_paper
from pathlib import Path

DOCX = Path(__file__).resolve().parents[1] / "input" / "amateur_teacher_question_paper.docx"


# ------------------------------------------------------------ builders

_blk = 0


def _next_block() -> int:
    global _blk
    _blk += 1
    return _blk


def M(value: int, raw: str | None = None, per_item: bool = False) -> MarksInfo:
    return MarksInfo(value=value, raw=raw or f"({value})", per_item=per_item)


def O(label: str, text: str = "option text") -> OptionInfo:
    b = _next_block()
    return OptionInfo(label=label.lower(), raw_label=f"{label})", text=text,
                      source_text=f"{label}) {text}", source_blocks=[b])


def S(label: str, text: str = "sub text", options: list | None = None) -> SubQuestionInfo:
    b = _next_block()
    return SubQuestionInfo(label=label.lower(), raw_label=f"{label})", text=text,
                           raw_text=f"{label}) {text}", type="general",
                           options=list(options or []), source_blocks=[b])


def Q(num: int, text: str = "Question text", marks: MarksInfo | None = M(2),
      subs: list | None = None, options: list | None = None,
      qtype: str = "general") -> QuestionInfo:
    b = _next_block()
    return QuestionInfo(number=num, raw_number=f"Q{num}", text=text,
                        raw_text=f"Q{num}. {text}", type=qtype, marks=marks,
                        options=list(options or []),
                        sub_questions=list(subs or []), source_blocks=[b])


def SEC(sid: str, questions: list, title: str | None = None,
        marks: MarksInfo | None = None) -> SectionInfo:
    b = _next_block()
    return SectionInfo(title=title or f"SECTION {sid}", section_id=sid,
                       marks=marks, questions=list(questions),
                       source_blocks=[b])


def P(sections: list, instructions: list | None = None,
      warnings: list | None = None) -> NormalizedPaper:
    return NormalizedPaper(metadata=[], instructions=list(instructions or []),
                           sections=list(sections), warnings=list(warnings or []))


# ------------------------------------------------------------ numbering


def test_numbering_gap_detected_with_details():
    paper = P([SEC("A", [Q(1), Q(2), Q(3), Q(6)])])
    res = validate_paper(paper)
    gaps = res.by_code("QUESTION_NUMBERING_GAP")
    assert len(gaps) == 1
    g = gaps[0]
    assert g.severity == "warning"
    assert g.message == "Question numbering jumps from Q3 to Q6."
    assert g.details == {"previous": 3, "actual": 6, "missing": [4, 5]}
    assert g.question_number == 6 and g.section == "A"


def test_numbering_never_rewritten():
    paper = P([SEC("A", [Q(1), Q(2), Q(3), Q(6)])])
    before = copy.deepcopy(paper.to_dict())
    validate_paper(paper)
    assert paper.to_dict() == before
    assert [q.number for q in paper.sections[0].questions] == [1, 2, 3, 6]


def test_duplicate_question_number_is_error():
    paper = P([SEC("A", [Q(5), Q(6), Q(6)])])
    res = validate_paper(paper)
    dupes = res.by_code("DUPLICATE_QUESTION_NUMBER")
    assert len(dupes) == 1
    assert dupes[0].severity == "error"
    assert res.has_errors is True


def test_sequential_numbering_has_no_gap_issues():
    paper = P([SEC("A", [Q(1), Q(2), Q(3)])])
    res = validate_paper(paper)
    assert res.by_code("QUESTION_NUMBERING_GAP") == []
    assert res.by_code("DUPLICATE_QUESTION_NUMBER") == []


# ------------------------------------------------------------ marks


def test_missing_marks_warning_per_question():
    paper = P([SEC("A", [Q(12, marks=None)])])
    res = validate_paper(paper)
    mm = res.by_code("MISSING_MARKS")
    assert len(mm) == 1
    assert mm[0].severity == "warning"
    assert mm[0].question_number == 12
    assert "Q12" in mm[0].message


def test_marks_invented_never():
    paper = P([SEC("A", [Q(12, marks=None)])])
    validate_paper(paper)
    assert paper.sections[0].questions[0].marks is None


def test_detected_marks_complete_total():
    paper = P([SEC("A", [Q(1, marks=M(5)), Q(2, marks=M(3))])])
    res = validate_paper(paper)
    summaries = res.by_code("MARKS_SUMMARY")
    assert len(summaries) == 1
    d = summaries[0].details
    assert d["detected_marks"] == 8
    assert d["marks_complete"] is True
    assert d["unknown_questions"] == []


def test_maximum_marks_match_and_mismatch():
    paper = P([SEC("A", [Q(1, marks=M(5)), Q(2, marks=M(3))])])
    ok = validate_paper(paper, maximum_marks=8)
    assert ok.by_code("MARKS_TOTAL_MISMATCH") == []
    assert ok.by_code("MARKS_SUMMARY")[0].details["maximum_marks"] == 8

    bad = validate_paper(paper, maximum_marks=50)
    mm = bad.by_code("MARKS_TOTAL_MISMATCH")
    assert len(mm) == 1 and mm[0].severity == "warning"
    assert mm[0].details["detected_marks"] == 8


def test_incomplete_marks_never_assumed_zero():
    paper = P([SEC("A", [Q(1, marks=M(5)), Q(2, marks=None)])])
    res = validate_paper(paper, maximum_marks=50)
    s = res.by_code("MARKS_SUMMARY")[0]
    assert s.details["detected_marks"] == 5  # unknown Q2 contributes nothing
    assert s.details["marks_complete"] is False
    assert s.details["unknown_questions"] == [2]
    assert "manual review required" in s.message
    # No mismatch warning when incomplete: comparison would be meaningless.
    assert res.by_code("MARKS_TOTAL_MISMATCH") == []


def test_per_item_marks_derived_only_with_subs():
    paper = P([SEC("A", [Q(6, marks=M(2, "(2 marks each)", per_item=True),
                         subs=[S("a"), S("b")])])])
    res = validate_paper(paper, maximum_marks=4)
    assert res.by_code("MARKS_SUMMARY")[0].details["detected_marks"] == 4
    assert res.by_code("MARKS_TOTAL_MISMATCH") == []

    lonely = P([SEC("A", [Q(6, marks=M(2, "(2 marks each)", per_item=True))])])
    res2 = validate_paper(lonely)
    assert res2.by_code("MARKS_SUMMARY")[0].details["marks_complete"] is False


# ------------------------------------------------------------ sections


def test_missing_section_is_error():
    res = validate_paper(P([]))
    errs = res.by_code("NO_SECTIONS")
    assert len(errs) == 1 and errs[0].severity == "error"


def test_question_before_section_is_flagged_not_moved():
    implicit = SectionInfo(title="", section_id="", questions=[Q(1)],
                           source_blocks=[1])
    paper = P([implicit])
    res = validate_paper(paper)
    outs = res.by_code("QUESTION_OUTSIDE_SECTION")
    assert len(outs) == 1 and outs[0].severity == "warning"
    assert outs[0].question_number == 1 and outs[0].section is None
    assert paper.sections[0].questions[0].number == 1  # not moved


def test_section_without_questions_and_missing_section_marks():
    paper = P([SEC("A", []), SEC("B", [Q(1)], marks=M(10))])
    res = validate_paper(paper)
    assert len(res.by_code("SECTION_WITHOUT_QUESTIONS")) == 1
    infos = res.by_code("SECTION_MISSING_MARKS")
    assert len(infos) == 1 and infos[0].severity == "info" and infos[0].section == "A"


# ------------------------------------------------------------ questions


def test_empty_question_error_and_empty_stem_warning():
    res = validate_paper(P([SEC("A", [Q(5, text="")])]))
    errs = res.by_code("EMPTY_QUESTION")
    assert len(errs) == 1 and errs[0].severity == "error"

    res2 = validate_paper(P([SEC("A", [Q(5, text="", subs=[S("a")])])]))
    assert res2.by_code("EMPTY_QUESTION") == []
    stems = res2.by_code("EMPTY_QUESTION_STEM")
    assert len(stems) == 1 and stems[0].severity == "warning"


def test_mcq_without_options():
    paper = P([SEC("A", [Q(1, qtype="mcq_group")])])
    res = validate_paper(paper)
    assert len(res.by_code("MCQ_WITHOUT_OPTIONS")) == 1

    itemless = Q(1, qtype="mcq_group", subs=[S("1", options=[])])
    itemless.sub_questions[0].type = "mcq"
    res2 = validate_paper(P([SEC("A", [itemless])]))
    assert len(res2.by_code("MCQ_WITHOUT_OPTIONS")) == 1


def test_suspicious_continuation_surfaced():
    paper = P([SEC("A", [Q(1)])],
              warnings=[WarningInfo(type="continued_paragraph",
                                    message="Paragraph 12 has no label; appended.",
                                    details={"source_block": 12, "question": "Q1"})])
    res = validate_paper(paper)
    found = res.by_code("SUSPICIOUS_CONTINUATION")
    assert len(found) == 1 and found[0].severity == "warning"
    assert found[0].source_blocks == [12] and found[0].question_number == 1


# ------------------------------------------------------------ options


def test_duplicate_option_labels_is_error():
    q = Q(1, qtype="mcq", options=[O("a", "One"), O("a", "Two")])
    res = validate_paper(P([SEC("A", [q])]))
    dupes = res.by_code("DUPLICATE_OPTION_LABELS")
    assert len(dupes) == 1 and dupes[0].severity == "error"


def test_missing_option_label_warns_without_renaming():
    q = Q(1, qtype="mcq", options=[O("a"), O("b"), O("d")])
    res = validate_paper(P([SEC("A", [q])]))
    miss = res.by_code("MISSING_OPTION_LABEL")
    assert len(miss) == 1 and miss[0].severity == "warning"
    assert miss[0].details["missing"] == ["c"]
    assert [o.label for o in q.options] == ["a", "b", "d"]  # untouched


def test_duplicate_option_text_warns():
    q = Q(1, qtype="mcq", options=[O("a", "Same"), O("b", "same ")])
    res = validate_paper(P([SEC("A", [q])]))
    assert len(res.by_code("DUPLICATE_OPTION_TEXT")) == 1


def test_option_counts_two_three_ok_one_suspicious():
    two = validate_paper(P([SEC("A", [Q(1, qtype="mcq", options=[O("a"), O("b")])])]))
    assert two.by_code("FEW_OPTIONS") == []
    assert len(two.by_code("UNUSUAL_OPTION_COUNT")) == 1  # info only

    three = validate_paper(P([SEC("A", [Q(1, qtype="mcq",
                                        options=[O("a"), O("b"), O("c")])])]))
    assert three.by_code("FEW_OPTIONS") == []
    assert len(three.by_code("UNUSUAL_OPTION_COUNT")) == 1

    one = validate_paper(P([SEC("A", [Q(1, qtype="mcq", options=[O("a")])])]))
    assert len(one.by_code("FEW_OPTIONS")) == 1

    four = validate_paper(P([SEC("A", [Q(1, qtype="mcq",
                                       options=[O("a"), O("b"), O("c"), O("d")])])]))
    assert four.by_code("FEW_OPTIONS") == []
    assert four.by_code("UNUSUAL_OPTION_COUNT") == []


# ------------------------------------------------------------ sub-questions


def test_subquestion_gaps_not_renamed():
    q = Q(6, subs=[S("a"), S("b"), S("d")])
    res = validate_paper(P([SEC("A", [q])]))
    gaps = res.by_code("SUBQUESTION_LABEL_GAP")
    assert len(gaps) == 1 and gaps[0].severity == "warning"
    assert gaps[0].details["missing"] == ["c"]
    assert [s.label for s in q.sub_questions] == ["a", "b", "d"]

    roman = validate_paper(P([SEC("A", [Q(10, subs=[S("i"), S("ii"), S("iv")])])]))
    assert roman.by_code("SUBQUESTION_LABEL_GAP")[0].details["missing"] == ["iii"]

    numeric = validate_paper(P([SEC("A", [Q(11, subs=[S("1"), S("2"), S("4")])])]))
    assert numeric.by_code("SUBQUESTION_LABEL_GAP")[0].details["missing"] == [3]


def test_duplicate_subquestion_label_is_error():
    q = Q(6, subs=[S("a"), S("a")])
    res = validate_paper(P([SEC("A", [q])]))
    dupes = res.by_code("DUPLICATE_SUBQUESTION_LABEL")
    assert len(dupes) == 1 and dupes[0].severity == "error"


# ------------------------------------------------------------ instructions


def test_instruction_gaps():
    inst = [InstructionInfo(text="General Instructions", source_blocks=[8]),
            InstructionInfo(text="a) Read.", source_blocks=[9]),
            InstructionInfo(text="b) Write.", source_blocks=[10]),
            InstructionInfo(text="d) Submit.", source_blocks=[11])]
    res = validate_paper(P([SEC("A", [Q(1)])], instructions=inst))
    gaps = res.by_code("INSTRUCTION_LABEL_GAP")
    assert len(gaps) == 1 and gaps[0].details["missing"] == ["c"]


def test_instructions_empty_and_absent():
    head_only = [InstructionInfo(text="General Instructions", source_blocks=[8])]
    res = validate_paper(P([SEC("A", [Q(1)])], instructions=head_only))
    assert len(res.by_code("INSTRUCTIONS_EMPTY")) == 1

    res2 = validate_paper(P([SEC("A", [Q(1)])]))
    assert len(res2.by_code("NO_INSTRUCTIONS")) == 1
    assert res2.by_code("NO_INSTRUCTIONS")[0].severity == "info"


# ------------------------------------------------------------ preservation


def test_unclassified_content_surfaced():
    paper = P([SEC("A", [Q(1)])],
              warnings=[WarningInfo(type="unclassified",
                                    message="Paragraph 3 kept as-is.",
                                    details={"source_block": 3, "text": "???"})])
    res = validate_paper(P([SEC("A", [Q(1)])],
                           warnings=paper.warnings))
    found = res.by_code("UNCLASSIFIED_CONTENT")
    assert len(found) == 1 and found[0].source_blocks == [3]


def test_validation_never_modifies_paper():
    paper = P([SEC("A", [Q(1, marks=None), Q(3)]),
               SEC("B", [Q(6, subs=[S("a"), S("b")])])],
              instructions=[InstructionInfo(text="General Instructions",
                                            source_blocks=[8])])
    snapshot = copy.deepcopy(paper.to_dict())
    validate_paper(paper, maximum_marks=50)
    assert paper.to_dict() == snapshot


def test_issue_model_shape():
    res = validate_paper(P([SEC("A", [Q(1), Q(3)])]), maximum_marks=50)
    d = res.to_dict()
    assert set(d) == {"errors", "warnings", "info", "summary"}
    for group in ("errors", "warnings", "info"):
        for item in d[group]:
            assert set(item) == {"code", "severity", "message", "source_blocks",
                                 "question_number", "section", "details"}
    assert d["summary"]["total"] == (len(d["errors"]) + len(d["warnings"])
                                     + len(d["info"]))


# ------------------------------------------------------------ sample document


def make_raw(texts: list[str]) -> RawDocument:
    return RawDocument(
        source="synthetic.docx",
        paragraphs=[ParagraphInfo(
            index=i, original_text=t, cleaned_text=clean_text(t),
            style="Normal", alignment=None, is_empty=(t.strip() == ""),
            runs=[RunInfo(text=t)]) for i, t in enumerate(texts)],
        tables=[])


def test_sample_document_validation():
    from app.parser.analyzer import analyze_document  # noqa: F811 (shadow import ok)
    paper = analyze_document(extract_document(DOCX))
    res = validate_paper(paper, maximum_marks=50)

    gaps = res.by_code("QUESTION_NUMBERING_GAP")
    assert len(gaps) == 1
    assert gaps[0].details == {"previous": 3, "actual": 6, "missing": [4, 5]}

    missing = res.by_code("MISSING_MARKS")
    assert {m.question_number for m in missing} == \
        {1, 8, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21}

    summary = res.by_code("MARKS_SUMMARY")[0]
    assert summary.details["maximum_marks"] == 50
    assert summary.details["detected_marks"] == 24
    assert summary.details["marks_complete"] is False
    assert "manual review required" in summary.message

    assert res.errors == []  # nothing structurally broken in the sample
    assert res.by_code("DUPLICATE_QUESTION_NUMBER") == []
    assert res.by_code("SUBQUESTION_LABEL_GAP") == []
    assert res.by_code("MISSING_OPTION_LABEL") == []
