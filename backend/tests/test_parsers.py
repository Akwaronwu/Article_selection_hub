"""Parser unit tests: RIS, BibTeX, CSV, DOI list, sniffing, normalisation."""

import pytest

from app.importers import UnsupportedFormatError, detect_format, parse_file
from app.importers.base import normalize_doi, normalize_title, normalize_year

# --- Normalisation ----------------------------------------------------------


def test_normalize_doi_variants():
    assert normalize_doi("10.1000/ABC.2024.001") == "10.1000/abc.2024.001"
    assert normalize_doi("https://doi.org/10.1000/x") == "10.1000/x"
    assert normalize_doi("doi:10.1000/y.") == "10.1000/y"
    assert normalize_doi("  10.1000/z; ") == "10.1000/z"
    # Garbage is never stored as an identifier.
    assert normalize_doi("N/A") is None
    assert normalize_doi(None) is None
    assert normalize_doi("") is None


def test_normalize_title_and_year():
    assert normalize_title("Large Language Models for {Code} Security!") == (
        "large language models for code security"
    )
    assert normalize_title(None) is None
    assert normalize_year("2024") == 2024
    assert normalize_year("2024-01-15") == 2024
    assert normalize_year("Vol. 3, 1999") == 1999
    assert normalize_year("n.d.") is None


# --- RIS --------------------------------------------------------------------


def test_ris_parses_records(fixture_bytes):
    outcome = parse_file("ris", fixture_bytes("sample.ris"))

    assert len(outcome.records) == 3
    first = outcome.records[0]
    assert first.title.startswith("Large Language Models")
    assert first.authors == ["Smith, Jane", "Doe, John"]
    assert first.year == 2024
    assert first.doi == "10.1000/llm-vuln.2024.001"
    assert first.venue == "Empirical Software Engineering"
    # Continuation line joined into the abstract.
    assert "12 open-source projects" in (first.abstract or "")
    assert first.keywords == ["LLM", "vulnerability detection"]
    # Third record: DOI-only, no title — legal at import time.
    assert outcome.records[2].title is None
    assert outcome.records[2].doi == "10.1000/doi-only.2023.009"


def test_ris_entry_without_title_or_doi_reported():
    outcome = parse_file("ris", b"TY  - JOUR\nAU  - Nobody\nER  - \n")
    assert outcome.records == []
    assert outcome.invalid_count == 1


def test_ris_garbage_reports_no_entries():
    outcome = parse_file("ris", b"just some text\nnot ris at all")
    assert outcome.records == []
    assert any("no RIS entries" in reason for reason in outcome.invalid)


# --- BibTeX -----------------------------------------------------------------


def test_bibtex_parses_entries(fixture_bytes):
    outcome = parse_file("bibtex", fixture_bytes("sample.bib"))

    # Third entry is intentionally malformed (unbalanced braces).
    assert len(outcome.records) == 2
    first = outcome.records[0]
    assert first.title == "Retrieval-Augmented Generation for Code Review"
    assert first.authors == ["Chen, Li", "Garcia, Maria"]
    assert first.venue == "Journal of Software Maintenance"
    assert first.year == 2023
    assert first.doi == "10.1000/rag.2023.003"
    second = outcome.records[1]
    assert second.venue == "ICSE"  # booktitle
    assert second.year == 2021
    assert "IoT" in second.title
    assert outcome.invalid_count >= 1


def test_bibtex_no_entries_reported():
    outcome = parse_file("bibtex", b"no citations here at all")
    assert outcome.records == []
    assert any("no BibTeX entries" in reason for reason in outcome.invalid)


# --- CSV --------------------------------------------------------------------


def test_csv_maps_database_export_headers(fixture_bytes):
    outcome = parse_file("csv", fixture_bytes("sample.csv"))

    assert len(outcome.records) == 2  # empty row is rejected
    first = outcome.records[0]
    assert first.title == "Deep Learning for Malware Detection"
    assert first.authors == ["Kim, Soo", "Park, Ji"]
    assert first.year == 2023
    assert first.doi == "10.1000/malware.2023.004"
    assert first.venue == "Journal of Cybersecurity"
    assert first.keywords == ["malware", "deep learning"]
    assert first.citation_count == 42
    assert outcome.invalid_count == 1


def test_csv_tab_delimited():
    content = "Title\tYear\tdoi\nTab Study\t2021\t10.1000/tab.2021.006\n"
    outcome = parse_file("csv", content.encode())
    assert len(outcome.records) == 1
    assert outcome.records[0].title == "Tab Study"
    assert outcome.records[0].year == 2021


def test_csv_without_title_or_doi_column_raises():
    with pytest.raises(ValueError, match="title or DOI column"):
        parse_file("csv", b"Name,Price\nWidget,10\n")


# --- DOI list ---------------------------------------------------------------


def test_doi_list_extracts_and_reports(fixture_bytes):
    outcome = parse_file("doi_list", fixture_bytes("dois.txt"))

    dois = [r.doi for r in outcome.records]
    assert dois == [
        "10.1000/alpha.2020.001",
        "10.1000/beta.2021.002",
        "10.1000/gamma.2022.003",
        "10.1000/delta.2024.004",
    ]
    assert all(r.title is None for r in outcome.records)
    assert outcome.invalid_count == 1  # the line without a DOI


# --- Format sniffing --------------------------------------------------------


def test_detect_format_by_content(fixture_bytes):
    assert detect_format("export.txt", fixture_bytes("sample.ris")) == "ris"
    assert detect_format("refs.dat", fixture_bytes("sample.bib")) == "bibtex"
    assert detect_format("results", fixture_bytes("dois.txt")) == "doi_list"


def test_detect_format_by_extension(fixture_bytes):
    assert detect_format("x.ris", b"anything") == "ris"
    assert detect_format("x.bib", b"anything") == "bibtex"
    assert detect_format("x.csv", b"anything") == "csv"


def test_detect_format_unknown_raises():
    with pytest.raises(UnsupportedFormatError):
        detect_format("mystery.xyz", b"binary-looking \x00\x01 content")


def test_unsupported_format_dispatch_rejected():
    with pytest.raises(UnsupportedFormatError):
        parse_file("paradox", b"data")
