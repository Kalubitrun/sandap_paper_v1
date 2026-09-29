"""Phase 1 demo entry point: print a summary + sample of the raw representation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.parser.analyzer import analyze_document
from app.parser.extractor import extract_document


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1 DOCX raw extractor")
    parser.add_argument(
        "docx",
        nargs="?",
        default="input/amateur_teacher_question_paper.docx",
        help="Path to the input DOCX file",
    )
    parser.add_argument("--json", dest="json_out", default=None, help="Write raw JSON here")
    parser.add_argument("--sample", type=int, default=8, help="How many paragraphs to preview")
    parser.add_argument("--analyze", action="store_true", help="Also run Phase 2 structural analysis")
    parser.add_argument("--validate", action="store_true", help="Also run Phase 3 validation")
    parser.add_argument("--max-marks", type=int, default=None, help="Maximum marks for validation")
    parser.add_argument("--spellcheck", action="store_true", help="Also run Phase 4 spell checking")
    parser.add_argument("--render", action="store_true", help="Also run Phase 5 DOCX rendering")
    parser.add_argument("--render-out", default="output/vps_question_paper.docx",
                        help="Output path for the rendered paper")
    args = parser.parse_args()

    raw = extract_document(args.docx)
    data = raw.to_dict()

    blanks = [p.index for p in raw.paragraphs if p.is_empty]
    print(f"source     : {raw.source}")
    print(f"paragraphs : {len(raw.paragraphs)}")
    print(f"blank idx  : {blanks}")
    print(f"tables     : {len(raw.tables)}")
    print(f"\n--- first {args.sample} paragraphs ---")
    for p in raw.paragraphs[: args.sample]:
        print(
            f"[{p.index}] style={p.style!r} align={p.alignment!r} "
            f"empty={p.is_empty} runs={len(p.runs)} text={p.original_text!r}"
        )

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\nwrote {args.json_out}")

    if args.analyze:
        paper = analyze_document(raw)
        pdata = paper.to_dict()
        print("\n=== PHASE 2: normalized structure ===")
        print(f"metadata fields : {len(paper.metadata)}")
        print(f"instructions    : {len(paper.instructions)}")
        print(f"sections        : {len(paper.sections)}")
        for s in paper.sections:
            mk = s.marks.value if s.marks else None
            print(f"  [{s.section_id}] {s.title!r} marks={mk} questions={len(s.questions)}")
            for q in s.questions:
                qm = q.marks.value if q.marks else None
                print(
                    f"    Q{q.number} ({q.type}) marks={qm} "
                    f"subs={len(q.sub_questions)} opts={len(q.options)} "
                    f"text={q.text[:60]!r}"
                )
        print(f"warnings        : {len(paper.warnings)}")
        for w in paper.warnings:
            print(f"  - [{w.type}] {w.message}")
        if args.json_out:
            stem = Path(args.json_out).with_suffix("")
            out2 = str(stem) + ".normalized.json"
            Path(out2).write_text(json.dumps(pdata, indent=2, ensure_ascii=False))
            print(f"\nwrote {out2}")

    if args.validate:
        from app.validation import validate_paper

        if not args.analyze:
            paper = analyze_document(raw)
        result = validate_paper(paper, maximum_marks=args.max_marks)
        print("\n=== PHASE 3: validation ===")
        print(f"summary: {result.summary()}")
        for issue in result.issues:
            print(f"  - [{issue.severity}] {issue.code}: {issue.message}")

    if args.spellcheck:
        from app.spelling import SpellCheckerService

        if not args.analyze:
            paper = analyze_document(raw)
        service = SpellCheckerService()
        spell_result = service.check_paper(paper)
        print("\n=== PHASE 4: spell check ===")
        print(f"summary: {spell_result.summary()}")
        for s in spell_result.suggestions:
            print(f"  - {s.original!r} -> {s.suggested!r} "
                  f"(Q{s.question_number}, blocks={s.source_blocks}, "
                  f"confidence={s.confidence}) context={s.context!r}")

    if args.render:
        from app.renderer import PaperSettings, SchoolConfig, render_question_paper
        from app.validation import validate_paper as _validate

        _paper = analyze_document(raw) if not args.analyze else paper
        _result = _validate(_paper, maximum_marks=args.max_marks)
        out = render_question_paper(_paper, SchoolConfig(), PaperSettings(),
                                    _result, args.render_out)
        print(f"\n=== PHASE 5: rendered {out} ===")


if __name__ == "__main__":
    main()
