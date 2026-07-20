"""Load gitignored `.env` files into `os.environ` without adding a dotenv dependency."""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: str | Path | None = None, *, override: bool = False) -> Path | None:
    """Parse KEY=VALUE lines from `.env` and set them in the process environment.

    Returns the path loaded, or None if no file was found.
    Existing env vars are preserved unless ``override`` is True.
    """
    candidates: list[Path] = []
    if path is not None:
        candidates.append(Path(path))
    else:
        here = Path(__file__).resolve().parent.parent
        candidates.append(here / ".env")
        candidates.append(Path.cwd() / ".env")

    for candidate in candidates:
        if not candidate.is_file():
            continue
        for raw in candidate.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if not key:
                continue
            if override or key not in os.environ:
                os.environ[key] = value
        return candidate
    return None
