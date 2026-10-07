"""CSV/TSV importer with header aliasing for database exports.

Handles Scopus/WoS/IEEE-style column names, comma/tab/semicolon delimiters,
and Excel BOMs. A missing title *and* DOI column is a hard error — the file
is not a literature export the system can use.
"""

from __future__ import annotations

import csv
import io

from app.importers.base import ParsedRecord, ParseOutcome, collapse_whitespace, normalize_year

# Canonical field → accepted header spellings (compared lower-cased/stripped).
_HEADER_ALIASES: dict[str, set[str]] = {
    "title": {"title", "document title", "article title", "article/title", "ti"},
    "authors": {
        "authors",
        "author",
        "author full names",
        "author(s)",
        "au",
        "first authors",
    },
    "abstract": {"abstract", "abstract/summary", "summary"},
    "year": {"year", "publication year", "date", "py"},
    "doi": {"doi", "doi identifier", "article doi"},
    "url": {"url", "link", "link to full text"},
    "venue": {
        "source title",
        "source",
        "journal",
        "journal name",
        "publication name",
        "conference",
        "conference name",
        "booktitle",
        "secondary title",
        "venue",
    },
    "keywords": {"keywords", "author keywords", "index keywords", "terms"},
    "affiliations": {"affiliations", "affiliation"},
    "language": {"language"},
    "publication_type": {"document type", "type", "publication type"},
    "citation_count": {"cited by", "citation count", "times cited"},
}


def _norm_header(header: str) -> str:
    """Normalise a header cell for alias lookup."""
    return " ".join(header.strip().lower().rstrip(":").split())


def _detect_delimiter(sample: str) -> str:
    """Pick comma/tab/semicolon from the header line."""
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;").delimiter
    except csv.Error:
        first_line = sample.splitlines()[0] if sample.splitlines() else ""
        if "\t" in first_line:
            return "\t"
        if ";" in first_line:
            return ";"
        return ","


def _split_multi(value: str, seps: tuple[str, ...]) -> list[str]:
    """Split a multi-value cell on any of ``seps``."""
    parts = [value]
    for sep in seps:
        parts = [p for chunk in parts for p in chunk.split(sep)]
    return [collapse_whitespace(p) or "" for p in parts if p.strip()]


def _cell(row: dict, column_map: dict[str, str], field_name: str) -> str:
    """Read one canonical field from a CSV row via the header mapping."""
    col = column_map.get(field_name)
    if col is None:
        return ""
    value = row.get(col)
    return str(value).strip() if value is not None else ""


def parse_csv(content: str) -> ParseOutcome:
    """Parse CSV/TSV text into records; raises ``ValueError`` for unusable files."""
    outcome = ParseOutcome()
    sample = content[:4096]
    if not sample.strip():
        raise ValueError("CSV file is empty")
    delimiter = _detect_delimiter(sample)
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("CSV file has no header row")

    column_map: dict[str, str] = {}  # canonical field → CSV column
    for header in reader.fieldnames:
        if header is None:
            continue
        norm = _norm_header(header)
        for canonical, aliases in _HEADER_ALIASES.items():
            if norm in aliases and canonical not in column_map:
                column_map[canonical] = header
                break

    if "title" not in column_map and "doi" not in column_map:
        found = ", ".join(h for h in reader.fieldnames if h) or "<none>"
        raise ValueError(
            "CSV must contain a title or DOI column "
            f"(accepted headers include 'Title'/'Document Title'/'DOI'; found: {found})"
        )

    for line_no, row in enumerate(reader, start=2):
        title = collapse_whitespace(_cell(row, column_map, "title"))
        doi_raw = _cell(row, column_map, "doi") or None
        if not title and not doi_raw:
            outcome.add_invalid(f"row {line_no}: no title or DOI — skipped")
            continue
        year_cell = _cell(row, column_map, "year") or None
        cite_raw = _cell(row, column_map, "citation_count")
        citation_count: int | None = None
        if cite_raw:
            try:
                citation_count = int("".join(c for c in cite_raw if c.isdigit()) or "x")
            except ValueError:
                citation_count = None
        outcome.records.append(
            ParsedRecord(
                title=title,
                authors=_split_multi(_cell(row, column_map, "authors"), (";", " and ")),
                abstract=collapse_whitespace(_cell(row, column_map, "abstract")),
                year=normalize_year(year_cell),
                venue=collapse_whitespace(_cell(row, column_map, "venue")),
                doi=doi_raw,
                url=_cell(row, column_map, "url") or None,
                keywords=_split_multi(_cell(row, column_map, "keywords"), (",", ";")),
                affiliations=_split_multi(
                    _cell(row, column_map, "affiliations"), (";", "|")
                ),
                language=collapse_whitespace(_cell(row, column_map, "language")),
                publication_type=collapse_whitespace(
                    _cell(row, column_map, "publication_type")
                ),
                citation_count=citation_count,
            )
        )

    if not outcome.records and not outcome.invalid:
        outcome.add_invalid("CSV contains a header but no data rows")
    return outcome
