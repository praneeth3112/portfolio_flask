"""Fetch and cache public repositories from the GitHub REST API.

Uses only the standard library. Failures never break the page: if GitHub is
unreachable we serve the last good response (even if stale) or an empty list.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from typing import Any, Callable

API_ROOT = "https://api.github.com"

Fetcher = Callable[[str, float], Any]


def default_fetcher(url: str, timeout: float) -> Any:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "portfolio-flask-app"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.load(response)


def summarise_repo(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep only the fields the site needs."""
    return {
        "name": raw.get("name", ""),
        "description": raw.get("description") or "",
        "language": raw.get("language"),
        "stars": int(raw.get("stargazers_count", 0)),
        "url": raw.get("html_url", ""),
        "updated": (raw.get("pushed_at") or raw.get("updated_at") or "")[:10],
    }


def language_breakdown(repos: list[dict[str, Any]]) -> dict[str, int]:
    """Number of repos per primary language, most common first."""
    counts = Counter(r["language"] for r in repos if r.get("language"))
    return dict(counts.most_common())


class GitHubService:
    def __init__(self, username: str, ttl: float = 600.0, timeout: float = 4.0,
                 fetcher: Fetcher = default_fetcher,
                 clock: Callable[[], float] = time.monotonic):
        self.username = username
        self.ttl = ttl
        self.timeout = timeout
        self._fetch = fetcher
        self._clock = clock
        self._lock = threading.Lock()
        self._cached: list[dict[str, Any]] | None = None
        self._cached_at = 0.0

    def _fresh(self) -> bool:
        return self._cached is not None and self._clock() - self._cached_at < self.ttl

    def repos(self) -> dict[str, Any]:
        """Return ``{"repos", "languages", "source"}`` where source is
        ``live``, ``cache``, ``stale`` or ``unavailable``."""
        with self._lock:
            if self._fresh():
                return self._payload(self._cached or [], "cache")
            url = f"{API_ROOT}/users/{self.username}/repos?per_page=100&sort=pushed"
            try:
                raw = self._fetch(url, self.timeout)
                repos = [summarise_repo(r) for r in raw if not r.get("fork")]
                repos.sort(key=lambda r: r["updated"], reverse=True)
            except (urllib.error.URLError, TimeoutError, ValueError, OSError):
                if self._cached is not None:
                    return self._payload(self._cached, "stale")
                return self._payload([], "unavailable")
            self._cached, self._cached_at = repos, self._clock()
            return self._payload(repos, "live")

    @staticmethod
    def _payload(repos: list[dict[str, Any]], source: str) -> dict[str, Any]:
        return {"repos": repos, "languages": language_breakdown(repos), "source": source}
