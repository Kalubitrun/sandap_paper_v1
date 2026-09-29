"""Phase 4 tests: deterministic spell checking.

Covers: obvious misspellings, correct words, dictionary terms,
abbreviations, punctuation, capitalization, multiple misspellings,
source-block traceability, content preservation, custom dictionary
loading, empty text, and conservative name/identifier handling.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from app.models.document import ParagraphInfo, RawDocument, RunInfo
from app.parser.analyzer import analyze_document
from app.parser.extractor import clean_text
from app.spelling import (
    SpellCheckerService,
    Suggestion,
    load_dictionary,
    spellcheck_docx,
)

DOCX = Path(__file__).resolve().parents[1] / "input" / "amateur_teacher_question_paper.docx"


@pytest.fixture(scope="module")
def svc() -> SpellCheckerService:
    return SpellCheckerService()


def check(svc: SpellCheckerService, text: str, **kw):
    found, _ = svc.check_text(text, source_blocks=kw.pop("source_blocks", [0]),
                              question_number=kw.pop("question_number", None))
    return found


# 1. obvious misspelling
def test_obvious_misspelling_suggests(svc):
    found = check(svc, "Which keybord is used?", source_blocks=[35], question_number=1)
    assert len(found) == 1
    s = found[0]
    assert s.original == "keybord" and s.suggested == "keyboard"
    assert s.source_blocks == [35] and s.question_number == 1
    assert s.status == "pending" and s.confidence == "high"
    assert "keybord" in s.context


# 2. correct word
def test_correct_word_no_suggestion(svc):
    assert check(svc, "The keyboard is an input device.") == []


# 3. technical dictionary term
def test_dictionary_term_no_suggestion(svc):
    assert check(svc, "What does QWERTY stand for?") == []
    assert check(svc, "Nearshore BPO centers handle calls.") == []
    assert check(svc, "Read about cybersecurity.") == []


# 4. abbreviation
def test_abbreviation_no_suggestion(svc):
    assert check(svc, "CPU RAM ROM ICT BPO ALU WPM CU MU") == []


# 5. punctuation
def test_punctuation_handling(svc):
    found = check(svc, "Hello, keybord! (Which one?)")
    assert [(s.original, s.suggested) for s in found] == [("keybord", "keyboard")]
    assert check(svc, "Well-known (already, correct) words.") == []


# 6. capitalization
def test_capitalization(svc):
    found = check(svc, "The KEYBORD is broken.")
    assert len(found) == 1 and found[0].suggested == "KEYBOARD"
    # Titlecase is guarded as a possible name: missed rather than mis-corrected.
    guarded = check(svc, "Keybord is a word.")
    assert all(s.original != "Keybord" for s in guarded)


# 7. multiple misspellings
def test_multiple_misspellings(svc):
    found = check(svc, "The keybord and teh mouse recieve input.")
    assert [(s.original, s.suggested) for s in found] == [
        ("keybord", "keyboard"), ("teh", "the"), ("recieve", "receive")]


# 8. source block traceability
def test_source_block_traceability(svc):
    raw = RawDocument(
        source="t.docx",
        paragraphs=[ParagraphInfo(
            index=i, original_text=t, cleaned_text=clean_text(t),
            style="Normal", alignment=None, is_empty=(t.strip() == ""),
            runs=[RunInfo(text=t)])
            for i, t in enumerate(["SECTION A", "Q1. What is a keybord?",
                                   "a) Keybord", "b) Mouse"])],
        tables=[])
    paper = analyze_document(raw)
    assert paper.sections[0].questions[0].number == 1
    result = svc.check_paper(paper)
    assert len(result.suggestions) == 1  # option "Keybord" guarded (Titlecase)
    s = result.suggestions[0]
    assert s.original == "keybord" and s.question_number == 1
    assert s.source_blocks == [1]


# 9. original text remains unchanged
def test_original_text_unchanged(svc):
    raw = RawDocument(
        source="t.docx",
        paragraphs=[ParagraphInfo(
            index=0, original_text="Q1. What is a keybord?", cleaned_text="Q1. What is a keybord?",
            style="Normal", alignment=None, is_empty=False, runs=[RunInfo(text="x")])],
        tables=[])
    paper = analyze_document(raw)
    before_paper = copy.deepcopy(paper.to_dict())
    before_raw = raw.paragraphs[0].original_text
    svc.check_paper(paper)
    assert paper.to_dict() == before_paper
    assert raw.paragraphs[0].original_text == before_raw
    assert "keybord" in paper.sections[0].questions[0].raw_text  # not replaced


# 10. custom dictionary loading
def test_custom_dictionary_loading(tmp_path):
    d = tmp_path / "custom.txt"
    d.write_text("# comment\n\nKeybord\nCPU\n")
    assert load_dictionary(d) == {"keybord", "cpu"}
    assert load_dictionary(tmp_path / "missing.txt") == set()
    svc2 = SpellCheckerService(dictionary_path=d)
    assert svc2.check_text("keybord", source_blocks=[0])[0] == []
    # extra_words overlay without a file
    svc3 = SpellCheckerService(extra_words={"keybord"})
    assert svc3.check_text("keybord", source_blocks=[0])[0] == []


# 11. empty text
def test_empty_text(svc):
    assert svc.check_text("", source_blocks=[0])[0] == []
    assert svc.check_text("   ", source_blocks=[0])[0] == []
    empty_paper = analyze_document(RawDocument(source="e.docx", paragraphs=[], tables=[]))
    res = svc.check_paper(empty_paper)
    assert res.suggestions == [] and res.summary()["total_suggestions"] == 0


# 12. names / identifiers not aggressively changed
def test_names_and_identifiers_guarded(svc):
    assert check(svc, "Ravi is a student of class IX.") == []
    assert check(svc, "Contact teacher@school.com for details.") == []
    found = check(svc, "Open report.pdf with the keybord.")
    assert [(s.original, s.suggested) for s in found] == [("keybord", "keyboard")]
    assert check(svc, "Use v2 of the driver.") == []


def test_suggestion_shape():
    s = Suggestion(original="keybord", suggested="keyboard", source_blocks=[35],
                   question_number=1, context="...", confidence="high")
    assert s.to_dict() == {"original": "keybord", "suggested": "keyboard",
                           "source_blocks": [35], "question_number": 1,
                           "context": "...", "confidence": "high", "status": "pending"}


def test_sample_document_has_no_obvious_misspellings(svc):
    result = spellcheck_docx(DOCX)
    assert result.suggestions == []
    assert result.summary()["texts_checked"] > 0
    assert result.summary()["words_checked"] > 0
