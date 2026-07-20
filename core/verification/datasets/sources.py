"""Provenance helpers for external validation sources."""

from __future__ import annotations

from typing import Any


def manufacturer_source(
    *,
    name: str,
    citation: str | None = None,
    year: int | None = None,
) -> dict[str, Any]:
    return {
        "kind": "manufacturer",
        "name": name,
        "citation": citation,
        "year": year,
    }


def publication_source(*, title: str, citation: str | None = None) -> dict[str, Any]:
    return {"kind": "publication", "name": title, "citation": citation}


def paper_source(*, title: str, citation: str | None = None) -> dict[str, Any]:
    return {"kind": "paper", "name": title, "citation": citation}


def test_data_source(*, name: str, citation: str | None = None) -> dict[str, Any]:
    return {"kind": "test_data", "name": name, "citation": citation}
