"""Plain DOI-list importer (one DOI per line, comments allowed)."""

from __future__ import annotations

import re

from app.importers.base import ParsedRecord, ParseOutcome, normalize_doi

_DOI_LINE_RE = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)


def parse_doi_list(content: str) -> ParseOutcome:
    """Extract DOIs from a text file; each becomes a title-less record.

    Studies without titles are legal at import time (§8: DOI lists are a
    supported source); title resolution happens later via DOI lookup.
    """
    outcome = ParseOutcome()
    seen: set[str] = set()
    for line_no, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue
        match = _DOI_LINE_RE.search(stripped)
        if not match:
            outcome.add_invalid(f"line {line_no}: no DOI found — skipped")
            continue
        doi = normalize_doi(match.group(0))
        if not doi:
            outcome.add_invalid(f"line {line_no}: malformed DOI — skipped")
            continue
        if doi in seen:
            continue  # duplicate line inside the same file
        seen.add(doi)
        outcome.records.append(ParsedRecord(doi=doi))

    if not outcome.records and not outcome.invalid:
        outcome.add_invalid("no DOIs found (expected one DOI per line)")
    return outcome
