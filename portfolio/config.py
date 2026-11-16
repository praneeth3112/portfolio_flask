"""Application configuration, read from environment variables with safe defaults."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent


def load_config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the config dict for the Flask app.

    Environment variables win over defaults; ``overrides`` (used by the tests)
    win over everything.
    """
    config: dict[str, Any] = {
        "SECRET_KEY": os.environ.get("SECRET_KEY", "dev-only-change-me"),
        "DATABASE": os.environ.get("DATABASE", str(BASE_DIR / "instance" / "portfolio.db")),
        "GITHUB_USER": os.environ.get("GITHUB_USER", "praneeth3112"),
        "GITHUB_CACHE_SECONDS": int(os.environ.get("GITHUB_CACHE_SECONDS", "600")),
        "GITHUB_TIMEOUT_SECONDS": float(os.environ.get("GITHUB_TIMEOUT_SECONDS", "4")),
        "ADMIN_TOKEN": os.environ.get("ADMIN_TOKEN", ""),
        "CONTACT_LIMIT_PER_HOUR": int(os.environ.get("CONTACT_LIMIT_PER_HOUR", "5")),
        "TRUST_PROXY": os.environ.get("TRUST_PROXY") == "1",
        "SITE_URL": os.environ.get("SITE_URL", "http://localhost:5000").rstrip("/"),
    }
    if overrides:
        config.update(overrides)
    return config
