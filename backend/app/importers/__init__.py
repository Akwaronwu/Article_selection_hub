"""Literature file import: format detection and parser dispatch (§8).

Parsers are pure; this module only decodes bytes and routes to them.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.importers.base import (
    ParsedRecord,
    ParseOutcome,
    normalize_doi,
    normalize_title,
    normalize_year,
)
from app.importers.bibtex import parse_bibtex
from app.importers.csv_import import parse_csv
from app.importers.doi_list import parse_doi_list
from app.importers.ris import parse_ris

SUPPORTED_FORMATS = ("ris", "bibtex", "csv", "doi_list")

_RIS_HEADER_RE = re.compile(r"(?m)^(?:TY|VR)\s{0,3}-")
_DOI_ANY_RE = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)


class UnsupportedFormatError(ValueError):
    """Raised when a file's format cannot be determined or is unsupported."""


def detect_format(filename: str | None, content: bytes) -> str:
    """Choose a parser: file extension first, then content sniffing."""
    suffix = Path(filename or "").suffix.lower()
    if suffix in (".bib", ".bibtex"):
        return "bibtex"
    if suffix == ".ris":
        return "ris"
    if suffix in (".csv", ".tsv"):
        return "csv"

    text = content.decode("utf-8-sig", errors="replace")
    stripped = text.lstrip()
    if stripped.startswith("@") and "{" in stripped[:256]:
        return "bibtex"
    if _RIS_HEADER_RE.search(text[:4096]):
        return "ris"

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.startswith(("#", "//"))
    ]
    # DOI-list heuristic: at least 80% of the first 50 lines contain a DOI —
    # one junk line must not defeat detection (real files always have some).
    window = lines[:50]
    if window:
        doi_hits = sum(1 for line in window if _DOI_ANY_RE.search(line))
        if doi_hits >= max(1, int(len(window) * 0.8)):
            return "doi_list"
    if lines and ("," in lines[0] or "\t" in lines[0]):
        return "csv"

    raise UnsupportedFormatError(
        "Could not detect file format: expected RIS (TY  - …), BibTeX (@…), "
        "CSV with a header row, or a plain DOI list"
    )


def parse_file(fmt: str, content: bytes) -> ParseOutcome:
    """Decode ``content`` and run the parser for ``fmt``."""
    if fmt not in SUPPORTED_FORMATS:
        raise UnsupportedFormatError(
            f"Unsupported format '{fmt}'; expected one of: {', '.join(SUPPORTED_FORMATS)}"
        )
    # utf-8-sig strips Excel/EndNote BOMs; undecodable bytes become replacement
    # chars rather than crashing the import (records are validated afterwards).
    text = content.decode("utf-8-sig", errors="replace")
    if fmt == "ris":
        return parse_ris(text)
    if fmt == "bibtex":
        return parse_bibtex(text)
    if fmt == "csv":
        return parse_csv(text)
    return parse_doi_list(text)


__all__ = [
    "SUPPORTED_FORMATS",
    "ParseOutcome",
    "ParsedRecord",
    "UnsupportedFormatError",
    "detect_format",
    "normalize_doi",
    "normalize_title",
    "normalize_year",
    "parse_file",
]
