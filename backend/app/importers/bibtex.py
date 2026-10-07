"""Minimal BibTeX parser (no external dependency).

Handles the practical subset of BibTeX: balanced-brace values (including
nested braces), quoted values, bare values (years), ``and``-separated
authors, ``@comment``/``@preamble`` skipping, and ``%`` line comments.
Malformed entries are reported through ``ParseOutcome.invalid`` instead of
crashing the whole import.
"""

from __future__ import annotations

from app.importers.base import ParsedRecord, ParseOutcome, collapse_whitespace, normalize_year

_SKIPPED_TYPES = {"comment", "preamble", "string"}


def _read_balanced(text: str, start: int, open_ch: str, close_ch: str) -> tuple[str, int]:
    """Return (content, index_after_close) for a balanced ``{…}``/``(…)`` span."""
    depth = 0
    i = start
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
        i += 1
    raise ValueError("unbalanced braces")


def _split_fields(body: str) -> dict[str, str]:
    """Parse ``key, field = value, field = value`` body of an entry."""
    fields: dict[str, str] = {}
    i = 0
    n = len(body)
    # Skip the citation key up to the first comma.
    comma = body.find(",")
    if comma == -1:
        return fields
    i = comma + 1
    while i < n:
        while i < n and (body[i].isspace() or body[i] == ","):
            i += 1
        if i >= n:
            break
        # Field name.
        name_start = i
        while i < n and (body[i].isalnum() or body[i] in "_-:"):
            i += 1
        name = body[name_start:i].strip().lower()
        while i < n and body[i].isspace():
            i += 1
        if i < n and body[i] == "=":
            i += 1
        else:
            # Malformed segment — skip to next comma.
            next_comma = body.find(",", i)
            if next_comma == -1:
                break
            i = next_comma + 1
            continue
        while i < n and body[i].isspace():
            i += 1
        if i >= n:
            break
        if body[i] in "{(":
            close_ch = "}" if body[i] == "{" else ")"
            try:
                value, i = _read_balanced(body, i, body[i], close_ch)
            except ValueError:
                value, i = body[i + 1:], n
        elif body[i] == '"':
            i += 1
            start = i
            while i < n and body[i] != '"':
                i += 1
            value = body[start:i]
            i += 1
        else:
            start = i
            while i < n and body[i] != ",":
                i += 1
            value = body[start:i]
        if name:
            fields[name] = value.strip()
        while i < n and body[i] != ",":
            i += 1
    return fields


def _strip_braces(value: str | None) -> str | None:
    """Remove BibTeX case-protection braces: ``{Code}`` → ``Code``."""
    if value is None:
        return None
    return value.replace("{", "").replace("}", "")


def _to_record(key: str, fields: dict[str, str]) -> ParsedRecord:
    authors_raw = fields.get("author", "")
    authors = [
        collapse_whitespace(a) or ""
        for a in authors_raw.split(" and ")
        if a.strip()
    ]
    venue = fields.get("journal") or fields.get("booktitle") or fields.get("publisher")
    keywords_raw = fields.get("keywords", "")
    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
    return ParsedRecord(
        title=collapse_whitespace(_strip_braces(fields.get("title"))),
        authors=authors,
        abstract=collapse_whitespace(_strip_braces(fields.get("abstract"))),
        year=normalize_year(fields.get("year")),
        venue=collapse_whitespace(_strip_braces(venue)),
        doi=fields.get("doi") or None,
        url=fields.get("url") or None,
        keywords=keywords,
        language=collapse_whitespace(fields.get("language")),
        source_key=key or None,
    )


def parse_bibtex(content: str) -> ParseOutcome:
    """Parse BibTeX text into records; malformed entries are reported."""
    outcome = ParseOutcome()
    i = 0
    n = len(content)
    found_entry = False
    while True:
        at = content.find("@", i)
        if at == -1:
            break
        j = at + 1
        while j < n and content[j].isspace():
            j += 1
        type_start = j
        while j < n and (content[j].isalnum() or content[j] in "_-"):
            j += 1
        entry_type = content[type_start:j].lower()
        if not entry_entry_type_guard(entry_type):
            i = at + 1
            continue
        if entry_type in _SKIPPED_TYPES:
            i = j
            continue
        while j < n and content[j].isspace():
            j += 1
        if j >= n or content[j] != "{":
            outcome.add_invalid(f"@{entry_type}: missing opening '{{'")
            i = j + 1
            continue
        try:
            body, after = _read_balanced(content, j, "{", "}")
        except ValueError:
            outcome.add_invalid(f"@{entry_type}: unbalanced braces (entry skipped)")
            break
        i = after
        found_entry = True
        fields = _split_fields(body)
        key = ""
        comma = body.find(",")
        if comma != -1:
            key = body[:comma].strip()
        if not fields.get("title") and not fields.get("doi"):
            outcome.add_invalid(f"@{entry_type} {key}: no title or DOI")
            continue
        outcome.records.append(_to_record(key, fields))

    if not found_entry:
        outcome.add_invalid("no BibTeX entries found (expected @type{...})")
    return outcome


def entry_entry_type_guard(entry_type: str) -> bool:
    """True when ``entry_type`` looks like a real citation type."""
    return bool(entry_type) and entry_type.isalpha()
