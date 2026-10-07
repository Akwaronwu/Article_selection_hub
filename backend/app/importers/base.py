"""Parsed-record types and normalisation helpers shared by all parsers.

Nothing here touches the database or FastAPI — parsers are pure functions
so they can be unit-tested exhaustively (docs/ARCHITECTURE.md §6).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
_NON_TITLE_CHARS = re.compile(r"[^a-z0-9]+")


@dataclass
class ParsedRecord:
    """One bibliographic record produced by a parser (pre-validation)."""

    title: str | None = None
    authors: list[str] = field(default_factory=list)
    abstract: str | None = None
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    keywords: list[str] = field(default_factory=list)
    affiliations: list[str] = field(default_factory=list)
    language: str | None = None
    publication_type: str | None = None
    citation_count: int | None = None
    source_key: str | None = None


@dataclass
class ParseOutcome:
    """Result of parsing one file: records plus human-readable problems."""

    records: list[ParsedRecord] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)  # capped sample of reasons
    invalid_count: int = 0

    def add_invalid(self, reason: str, cap: int = 50) -> None:
        """Record a rejected line/entry (keeps at most ``cap`` samples)."""
        self.invalid_count += 1
        if len(self.invalid) < cap:
            self.invalid.append(reason)


def normalize_doi(raw: str | None) -> str | None:
    """Canonicalise a DOI: strip URL/`doi:` prefixes, lower-case, trim.

    Returns ``None`` when the value is not a plausible DOI — garbage values
    (e.g. ``N/A``) are never stored as identifiers (§64: no silent fudging).
    """
    if not raw:
        return None
    value = raw.strip().rstrip(".,;)")
    for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "doi:"):
        if value.lower().startswith(prefix):
            value = value[len(prefix):].strip()
            break
    value = value.strip().strip('"').rstrip(".,;)")
    if _DOI_RE.match(value):
        return value.lower()
    return None


def normalize_title(title: str | None) -> str | None:
    """Lower-case and strip punctuation for near-exact title comparison."""
    if not title:
        return None
    collapsed = _NON_TITLE_CHARS.sub(" ", title.lower()).strip()
    return collapsed or None


def normalize_year(raw: str | int | None) -> int | None:
    """Extract a plausible publication year (1500–2100) from messy strings."""
    if raw is None:
        return None
    match = _YEAR_RE.search(str(raw))
    if not match:
        return None
    year = int(match.group(1))
    return year if 1500 <= year <= 2100 else None


def collapse_whitespace(text: str | None) -> str | None:
    """Collapse runs of whitespace (RIS continuation lines, CSV cells)."""
    if text is None:
        return None
    return " ".join(text.split()) or None
