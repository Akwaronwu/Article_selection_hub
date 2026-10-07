"""RIS format parser (EndNote/Zotero/Scopus/WoS exports).

Format: ``TAG  - value`` lines; a record starts at ``TY  -`` and ends at
``ER  -``. Continuation lines (indented) are appended to the current field.
"""

from __future__ import annotations

import re

from app.importers.base import ParsedRecord, ParseOutcome, collapse_whitespace, normalize_year

_TAG_RE = re.compile(r"^([A-Z][A-Z0-9]{1,3})\s{0,3}-\s?(.*)$")

_TITLE_TAGS = {"TI", "T1"}
_VENUE_TAGS = {"JO", "JF", "JA", "T2", "BT"}
_AUTHOR_TAGS = {"AU", "A1"}
_ABSTRACT_TAGS = {"AB", "N2"}
_YEAR_TAGS = {"PY", "Y1"}


def _to_record(fields: dict) -> ParsedRecord:
    """Map collected RIS fields onto a ``ParsedRecord``."""
    return ParsedRecord(
        title=collapse_whitespace(fields.get("title")),
        authors=[collapse_whitespace(a) or "" for a in fields.get("authors", []) if a.strip()],
        abstract=collapse_whitespace(fields.get("abstract")),
        year=normalize_year(fields.get("year")),
        venue=collapse_whitespace(fields.get("venue")),
        doi=fields.get("doi") or None,
        url=fields.get("url") or None,
        keywords=[k for k in fields.get("keywords", []) if k.strip()],
        language=collapse_whitespace(fields.get("language")),
        publication_type=collapse_whitespace(fields.get("type")),
        source_key=fields.get("id") or None,
    )


def parse_ris(content: str) -> ParseOutcome:
    """Parse RIS text into an outcome of records + invalid-entry reasons."""
    outcome = ParseOutcome()
    fields: dict | None = None
    last_tag: str | None = None

    def _finish() -> None:
        nonlocal fields
        if fields is not None:
            if fields.get("title") or fields.get("doi"):
                outcome.records.append(_to_record(fields))
            else:
                outcome.add_invalid("entry skipped: no title or DOI")
        fields = None

    for raw_line in content.splitlines():
        line = raw_line.rstrip("\n")
        match = _TAG_RE.match(line.strip())
        if match:
            tag, value = match.group(1), match.group(2).strip()
            if tag == "TY":
                _finish()
                fields = {"authors": [], "keywords": [], "id": None}
                last_tag = None
                if value:
                    fields["type"] = value
                continue
            if tag == "ER":
                _finish()
                last_tag = None
                continue
            if fields is None:
                continue  # file header (e.g. "VR  - PT")
            if tag == "TY":
                fields["type"] = value
            elif tag in _TITLE_TAGS:
                fields["title"] = (fields.get("title") or "") + value
            elif tag in _VENUE_TAGS:
                fields.setdefault("venue", value)
            elif tag in _AUTHOR_TAGS:
                fields["authors"].append(value)
            elif tag in _ABSTRACT_TAGS:
                fields["abstract"] = ((fields.get("abstract") or "") + " " + value).strip()
            elif tag in _YEAR_TAGS:
                fields.setdefault("year", value)
            elif tag == "DO":
                fields["doi"] = value
            elif tag == "UR":
                fields["url"] = value
            elif tag == "KW":
                fields["keywords"].append(value)
            elif tag == "LA":
                fields["language"] = value
            elif tag == "ID":
                fields["id"] = value
            last_tag = tag
        elif fields is not None and last_tag is not None and line.strip():
            # Continuation of the previous field.
            if last_tag in _ABSTRACT_TAGS:
                fields["abstract"] = ((fields.get("abstract") or "") + " " + line.strip()).strip()
            elif last_tag in _TITLE_TAGS:
                fields["title"] = (fields.get("title") or "") + line.strip()

    _finish()  # tolerate files missing the final ER line
    if not outcome.records and not outcome.invalid:
        outcome.add_invalid("no RIS entries found (expected TY  - … ER  - blocks)")
    return outcome
