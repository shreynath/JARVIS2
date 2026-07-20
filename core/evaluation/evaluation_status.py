"""Evaluation lifecycle status — incomplete is blocked, not a soft warning."""

from __future__ import annotations

from enum import Enum


class EvaluationStatus(Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    FAILED = "failed"
