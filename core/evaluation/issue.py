"""Lightweight evaluation issue type — import-safe (no physics / pipeline deps)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Issue:
    """Blocking or diagnostic evaluation issue."""

    code: str
    message: str
    severity: str = "blocking"
    field: str | None = None
