"""Phase 4: DETERMINISTIC SPELL CHECKING (pyspellchecker, no AI).

Produces reviewable suggestions; never modifies teacher content.

Token skip rules (in order, all deterministic):
  1. Single characters (``a``, ``I``, ``x`` in formulae).
  2. Tokens containing digits (``v1``, ``3d``).
  3. Tokens glued to ``. / @ _ # +`` in the source text, i.e. parts of
     URLs, emails, filenames, identifiers (``pdf`` in ``report.pdf``,
     ``com`` in ``a@b.com``).
  4. Short ALL-CAPS tokens (length <= 4): abbreviations (``CPU``).
     Longer ALL-CAPS is still checked lowercased (``KEYBORD``).
  5. Tokens with uppercase beyond the first letter: camelCase names /
     identifiers (``McDonald``, ``eMail``).
  6. Titlecase tokens (``Ravi``): possible names. This is deliberately
     conservative: a sentence-initial typo is missed rather than a
     name being "corrected". Documented limitation.
  7. Custom dictionary hits (case-insensitive).
  8. Base dictionary hits (lowercased, apostrophes stripped).

Anything else takes the single best ``correction()`` candidate; if the
library returns nothing usable, the token is left alone (no guessing).

Confidence is the Levenshtein distance between the lowercased token and
the suggestion: 1 -> "high", 2 -> "medium", otherwise "low".

Checked fields: instruction text, question text, case-study passage,
sub-question text, option text. Never checked: numbers, labels, marks,
metadata, section titles/numbering.
"""

from __future__ import annotations

import re
from pathlib import Path

from spellchecker import SpellChecker

from app.models.paper import NormalizedPaper
from app.spelling.dictionary import DEFAULT_DICTIONARY_PATH, load_dictionary
from app.spelling.models import SpellCheckResult, Suggestion

_TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_ABBREV_MAX_LEN = 4
_IDENTIFIER_CHARS = frozenset("./@_#+")
_CONTEXT_RADIUS = 30


def levenshtein(a: str, b: str) -> int:
    """Deterministic edit distance for the confidence rating."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[len(b)]


def _match_case(template: str, word: str) -> str:
    if template.isupper():
        return word.upper()
    return word  # Titlecase never reaches here; anything else stays lower


class SpellCheckerService:
    def __init__(self, dictionary_path: str | Path | None = None,
                 extra_words: set[str] | None = None) -> None:
        self.spell = SpellChecker()
        self.custom_words = load_dictionary(dictionary_path or DEFAULT_DICTIONARY_PATH)
        if extra_words:
            self.custom_words |= {w.lower() for w in extra_words}

    # -- token classification ------------------------------------------
    def _skip_reason(self, token: str) -> str | None:
        """Why this token is not checked; None means 'check it'."""
        if len(token) <= 1:
            return "single_char"
        if any(ch.isdigit() for ch in token):
            return "has_digit"
        if token.isupper() and len(token) <= _ABBREV_MAX_LEN:
            return "abbreviation"
        if not token.isupper() and any(ch.isupper() for ch in token[1:]):
            return "inner_caps"  # camelCase / names like McDonald
        if token[0].isupper() and token[1:].islower():
            return "titlecase_name_guard"
        return None

    def _lookup_forms(self, token: str) -> list[str]:
        low = token.lower()
        forms = [low]
        nospace = low.replace("'", "")
        if nospace != low:
            forms.append(nospace)
        return forms

    # -- text checking ---------------------------------------------------
    def check_text(self, text: str, *, source_blocks: list[int],
                   question_number: int | None = None) -> tuple[list[Suggestion], int]:
        """Check one text unit. Returns (suggestions, tokens_seen)."""
        suggestions: list[Suggestion] = []
        tokens_seen = 0
        for m in _TOKEN_RE.finditer(text):
            token = m.group(0)
            tokens_seen += 1
            # Identifier part? The neighbour punctuation only counts as glue
            # when it is itself glued to a non-space on its outer side, so a
            # sentence-final period ("keybord. Next") does not mark a filename
            # ("pdf" in "report.pdf" stays skipped).
            before = text[m.start() - 1] if m.start() > 0 else ""
            after = text[m.end()] if m.end() < len(text) else ""
            after_next = text[m.end() + 1] if m.end() + 1 < len(text) else ""
            before_outer = text[m.start() - 2] if m.start() >= 2 else ""
            if before in _IDENTIFIER_CHARS and before_outer and not before_outer.isspace():
                continue
            if after in _IDENTIFIER_CHARS and after_next and not after_next.isspace():
                continue
            if self._skip_reason(token) is not None:
                continue
            forms = self._lookup_forms(token)
            if any(f in self.custom_words for f in forms):
                continue
            if any(f in self.spell for f in forms):
                continue
            best = self.spell.correction(forms[0])
            if not best or best == forms[0]:
                continue  # no usable candidate: leave alone, don't guess
            dist = levenshtein(forms[0], best)
            confidence = "high" if dist <= 1 else ("medium" if dist == 2 else "low")
            start = max(0, m.start() - _CONTEXT_RADIUS)
            end = min(len(text), m.end() + _CONTEXT_RADIUS)
            suggestions.append(Suggestion(
                original=token,
                suggested=_match_case(token, best),
                source_blocks=list(source_blocks),
                question_number=question_number,
                context=text[start:end].strip(),
                confidence=confidence,
                status="pending",
            ))
        return suggestions, tokens_seen

    # -- paper checking ----------------------------------------------------
    def check_paper(self, paper: NormalizedPaper) -> SpellCheckResult:
        result = SpellCheckResult(
            custom_dictionary_size=len(self.custom_words))
        for inst in paper.instructions:
            self._check_unit(result, inst.text, inst.source_blocks, None)
        for section in paper.sections:
            for q in section.questions:
                head_blocks = q.source_blocks[:1]
                self._check_unit(result, q.text, head_blocks, q.number)
                if q.passage:
                    self._check_unit(result, q.passage, list(q.passage_blocks), q.number)
                for o in q.options:
                    self._check_unit(result, o.text, list(o.source_blocks), q.number)
                for sq in q.sub_questions:
                    self._check_unit(result, sq.text, sq.source_blocks[:1], q.number)
                    for o in sq.options:
                        self._check_unit(result, o.text, list(o.source_blocks), q.number)
        return result

    def _check_unit(self, result: SpellCheckResult, text: str,
                    blocks: list[int], qnum: int | None) -> None:
        if not text or not text.strip():
            return
        result.texts_checked += 1
        found, seen = self.check_text(text, source_blocks=list(blocks),
                                      question_number=qnum)
        result.words_checked += seen
        result.suggestions.extend(found)


def spellcheck_docx(path: str | Path,
                    dictionary_path: str | Path | None = None,
                    extra_words: set[str] | None = None) -> SpellCheckResult:
    """Phase 1 -> Phase 2 -> Phase 4 convenience entry point."""
    from app.parser.analyzer import analyze_docx  # deferred: spelling is downstream
    service = SpellCheckerService(dictionary_path=dictionary_path,
                                  extra_words=extra_words)
    return service.check_paper(analyze_docx(path))
