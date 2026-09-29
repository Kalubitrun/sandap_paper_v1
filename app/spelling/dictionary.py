"""Custom dictionary loading for Phase 4 spell checking.

Plain-text format: one term per line, case-insensitive. Blank lines and
lines starting with '#' are ignored. Lookup is always done on the
lowercased form, so file casing does not matter.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_DICTIONARY_PATH = Path(__file__).resolve().parent / "dictionary.txt"


def load_dictionary(path: str | Path | None = None) -> set[str]:
    """Load custom terms as a lowercased set. Missing file -> empty set."""
    if path is None:
        path = DEFAULT_DICTIONARY_PATH
    p = Path(path)
    if not p.is_file():
        return set()
    terms: set[str] = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        terms.add(line.lower())
    return terms
