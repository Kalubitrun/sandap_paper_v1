"""Phase 2 tests: structural analysis of the raw representation.

Covers: Q numbering, numbering gaps, option variants, same-line options,
sub-questions, sections, instructions, marks, missing marks, and
preservation of original text with source-block traceability.
"""

from __future__ import annotations

from pathlib import Path

from app.models.document import ParagraphInfo, RawDocument, RunInfo
from app.parser.analyzer import (
    analyze_document,
    parse_bare_number,
    parse_label,
    parse_main_question,
    parse_marks,
    split_inline_options,
)
from app.parser.extractor import clean_text, extract_document

DOCX = Path(__file__).resolve().parents[1] / "input" / "amateur_teacher_question_paper.docx"


def make_raw(texts: list[str], source: str = "synthetic.docx") -> RawDocument:
    """Build a minimal RawDocument from plain paragraph texts."""
    paras = [
        ParagraphInfo(
            index=i,
            original_text=t,
            cleaned_text=clean_text(t),
            style="Normal",
            alignment=None,
            is_empty=(t.strip() == ""),
            runs=[RunInfo(text=t)],
        )
        for i, t in enumerate(texts)
    ]
    return RawDocument(source=source, paragraphs=paras, tables=[])


# ------------------------------------------------ unit: question headers


def test_main_question_variants():
    assert parse_main_question("Q1. Choose the correct answer.") == (1, "Choose the correct answer.")
    assert parse_main_question("Q1) Text") == (1, "Text")
    assert parse_main_question("Q1: Text") == (1, "Text")
    assert parse_main_question("Q12. Explain.") == (12, "Explain.")
    assert parse_main_question("Question 1 Text") == (1, "Text")
    assert parse_main_question("QUESTION 3: Text") == (3, "Text")
    # Not a question header:
    assert parse_main_question("Quality matters a lot") is None
    assert parse_main_question("1. Which part is physical?") is None  # bare, not Q-prefixed
    assert parse_main_question("SECTION A") is None


def test_bare_numbers_are_not_main_questions_by_themselves():
    assert parse_bare_number("1. Which part?") == ("1", "1.", "Which part?")
    assert parse_bare_number("2) What is BPO?") == ("2", "2)", "What is BPO?")
    assert parse_bare_number("1 - First item") == ("1", "1-", "First item")
    assert parse_bare_number("Time 3 Hours") is None


def test_bare_numbers_attach_to_open_question_not_as_mains():
    # "1, 2, 3 under Q1 are items belonging to Q1, not main questions."
    raw = make_raw(["Q1. Choose the correct answer.", "1. Stem one?", "2. Stem two?"])
    paper = analyze_document(raw)
    assert len(paper.sections) == 1
    assert len(paper.sections[0].questions) == 1
    q = paper.sections[0].questions[0]
    assert q.number == 1
    assert [s.label for s in q.sub_questions] == ["1", "2"]


# ------------------------------------------------ unit: options


def test_option_label_variants_normalize():
    assert parse_label("a) Keyboard")[1:] == ("a", "a)", "Keyboard")
    assert parse_label("(a) Keyboard")[1:] == ("a", "(a)", "Keyboard")
    assert parse_label("A) Keyboard")[1:] == ("a", "A)", "Keyboard")
    assert parse_label("A. Keyboard")[1:] == ("a", "A.", "Keyboard")
    assert parse_label("d) Google Chrome")[1:] == ("d", "d)", "Google Chrome")


def test_roman_labels():
    assert parse_label("i) CPU")[0:2] == ("roman", "i")
    assert parse_label("ii) RAM")[1] == "ii"
    assert parse_label("iii) ROM")[1] == "iii"


def test_inline_options_split():
    opts = split_inline_options("a) Email    b) CPU    c) RAM    d) Printer")
    assert opts is not None and len(opts) == 4
    assert [(label, text) for label, _, text in opts] == [
        ("a", "Email"), ("b", "CPU"), ("c", "RAM"), ("d", "Printer"),
    ]
    # Single-space text must NOT split (unsafe): returns None.
    assert split_inline_options("a) ASDF and JKL;") is None
    # A chunk that is not an option -> None (no guessing).
    assert split_inline_options("a) Email    hello world") is None


# ------------------------------------------------ unit: marks


def test_marks_variants():
    assert parse_marks("(3)")[0].value == 3
    assert parse_marks("(3 marks)")[0].value == 3
    assert parse_marks("(3 Marks)")[0].value == 3
    assert parse_marks("[3]")[0].value == 3
    assert parse_marks("Explain. 3 marks")[0].value == 3
    m, _ = parse_marks("Q2. Fill in the blanks. (5 x 1 = 5)")
    assert (m.value, m.raw) == (5, "(5 x 1 = 5)")
    assert parse_marks("No marks here")[0] is None


def test_marks_raw_preserved_and_stripped_from_text():
    m, stripped = parse_marks("Write True or False. (4 x 1 = 4)")
    assert m.raw == "(4 x 1 = 4)" and stripped == "Write True or False."
    m, stripped = parse_marks("Difference between RAM and ROM? (3)")
    assert m.raw == "(3)" and stripped == "Difference between RAM and ROM?"


def test_per_item_marks_flagged_not_distributed():
    raw = make_raw(["Q6. Answer the following questions. (2 marks each)",
                    "a) What is a computer?"])
    paper = analyze_document(raw)
    q = paper.sections[0].questions[0]
    assert q.marks is not None and q.marks.per_item is True
    assert q.sub_questions[0].marks is None  # never invented/distributed
    assert any(w.type == "per_item_marks" for w in paper.warnings)


# ------------------------------------------------ sample-doc integration


def test_sample_q1_q2_q3_numbering_and_types():
    paper = analyze_document(extract_document(DOCX))
    sec_a = paper.sections[0]
    assert [q.number for q in sec_a.questions] == [1, 2, 3]
    assert [q.type for q in sec_a.questions] == ["mcq_group", "fill_blanks", "true_false"]
    assert sec_a.questions[1].marks is not None and sec_a.questions[1].marks.value == 5
    assert sec_a.questions[2].marks is not None and sec_a.questions[2].marks.value == 4


def test_sample_numbering_gap_q3_to_q6():
    paper = analyze_document(extract_document(DOCX))
    gaps = [w for w in paper.warnings if w.type == "numbering_gap"]
    assert len(gaps) == 1
    assert gaps[0].to_dict()["expected"] == ["Q4", "Q5"]
    assert gaps[0].to_dict()["actual"] == "Q6"
    assert "Q3 to Q6" in gaps[0].message
    # Numbers are NOT rewritten.
    all_nums = [q.number for s in paper.sections for q in s.questions]
    assert all_nums == [1, 2, 3, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]


def test_sample_option_styles_all_normalized():
    paper = analyze_document(extract_document(DOCX))
    q1 = paper.sections[0].questions[0]
    assert len(q1.sub_questions) == 5  # 1..5 are items, not mains
    opt_labels = [[o.label for o in s.options] for s in q1.sub_questions]
    assert opt_labels == [["a", "b", "c", "d"]] * 5
    # Raw labels preserve what the teacher wrote.
    assert [o.raw_label for o in q1.sub_questions[1].options] == ["(a)", "(b)", "(c)", "(d)"]
    assert [o.raw_label for o in q1.sub_questions[2].options] == ["A.", "B.", "C.", "D."]


def test_sample_same_line_options_split_with_source_preserved():
    paper = analyze_document(extract_document(DOCX))
    item4 = paper.sections[0].questions[0].sub_questions[3]
    assert [(o.label, o.text) for o in item4.options] == [
        ("a", "Email"), ("b", "CPU"), ("c", "RAM"), ("d", "Printer")]
    for o in item4.options:
        assert o.source_text == "a) Email    b) CPU    c) RAM    d) Printer"
        assert o.source_blocks == [35]
    assert any(w.type == "inline_options" and w.details.get("source_block") == 35
               for w in paper.warnings)


def test_sample_sub_questions():
    paper = analyze_document(extract_document(DOCX))
    by_num = {q.number: q for s in paper.sections for q in s.questions}
    assert [s.label for s in by_num[6].sub_questions] == ["a", "b"]
    assert [s.label for s in by_num[10].sub_questions] == ["i", "ii", "iii"]
    assert [s.label for s in by_num[11].sub_questions] == ["1", "2", "3"]
    assert [s.raw_label for s in by_num[11].sub_questions] == ["1)", "2)", "3)"]
    # Q3 True/False lettered lines are items, not options.
    assert len(by_num[3].sub_questions) == 4
    assert all(s.options == [] for s in by_num[3].sub_questions)


def test_sample_sections_detected_with_titles_and_marks():
    paper = analyze_document(extract_document(DOCX))
    assert len(paper.sections) == 2
    assert paper.sections[0].title == "SECTION A OBJECTIVE TYPE QUESTIONS 24 MARKS"
    assert paper.sections[0].marks is not None and paper.sections[0].marks.value == 24
    assert paper.sections[1].title == "SECTION B SUBJECTIVE TYPE QUESTIONS (26 MARKS)"
    assert paper.sections[1].marks is not None and paper.sections[1].marks.value == 26


def test_sample_instructions_detected():
    paper = analyze_document(extract_document(DOCX))
    assert paper.instructions[0].text == "General Instructions"
    assert len(paper.instructions) == 7  # heading + 6 items
    assert paper.instructions[1].source_blocks == [9]


def test_sample_metadata_detected():
    paper = analyze_document(extract_document(DOCX))
    meta = {m.key: m for m in paper.metadata}
    assert meta["school"].text == "VARANASI PUBLIC SCHOOL"
    assert meta["class"].text == "CLASS IX"
    assert meta["subject_code"].text == "SUBJECT CODE 402"
    assert meta["time"].source_block == 5
    assert meta["max_marks"].source_block == 6


def test_sample_missing_marks_warned_not_invented():
    paper = analyze_document(extract_document(DOCX))
    by_num = {q.number: q for s in paper.sections for q in s.questions}
    assert by_num[8].marks is None
    missing = {w.details.get("question") for w in paper.warnings if w.type == "missing_marks"}
    assert "Q8" in missing and "Q1" in missing
    # Questions WITH marks have no missing_marks warning.
    assert "Q2" not in missing and "Q7" not in missing


def test_sample_case_study_passage_and_subs():
    paper = analyze_document(extract_document(DOCX))
    q21 = [q for s in paper.sections for q in s.questions if q.number == 21][0]
    assert q21.type == "case_study"
    assert q21.passage is not None and q21.passage.startswith("Ravi is a student")
    assert q21.passage_blocks == [85]
    assert [s.label for s in q21.sub_questions] == ["a", "b", "c"]


def test_original_text_preserved_and_traceable():
    raw = extract_document(DOCX)
    paper = analyze_document(raw)
    by_idx = {p.index: p for p in raw.paragraphs}
    # Every source block resolves to the exact original paragraph.
    for s in paper.sections:
        for q in s.questions:
            assert by_idx[q.source_blocks[0]].cleaned_text == q.raw_text
            for sub in q.sub_questions:
                first = by_idx[sub.source_blocks[0]]
                assert first.cleaned_text == sub.raw_text or sub.raw_text in first.cleaned_text
    # Nothing unclassified in the sample doc besides expected flow.
    unclassified = [w for w in paper.warnings if w.type == "unclassified"]
    assert unclassified == []
    # Dict shape matches the Phase 2 contract.
    d = paper.to_dict()
    assert set(d) == {"metadata", "instructions", "sections", "warnings", "end_marker"}
    assert d["end_marker"] == {"text": "END", "source_block": 90}
    qd = d["sections"][0]["questions"][0]
    assert set(qd) >= {"number", "type", "text", "marks", "options", "sub_questions", "source_blocks"}
