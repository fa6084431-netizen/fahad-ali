"""Seed expansion via Google Autocomplete (no API key needed)."""

from __future__ import annotations

import hashlib
import json
import string
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Iterable

SUGGEST_URL = "https://suggestqueries.google.com/complete/search"

QUESTION_PREFIXES = ["how", "what", "why", "where", "when", "which", "who", "can", "is", "does", "are", "should"]
PREPOSITION_SUFFIXES = ["for", "with", "without", "near", "vs", "to", "in", "like", "or", "and"]
COMMERCIAL_SUFFIXES = ["best", "top", "cheap", "price", "cost", "review", "reviews", "alternative", "near me", "online"]

Fetcher = Callable[[str], list[str]]


class GoogleSuggest:
    """Fetches autocomplete suggestions with on-disk caching and polite rate limiting."""

    def __init__(self, lang: str = "en", country: str = "us", delay: float = 0.4,
                 cache_dir: str | Path | None = ".kws_cache", timeout: float = 10.0):
        self.lang = lang
        self.country = country
        self.delay = delay
        self.timeout = timeout
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_call = 0.0

    def _cache_path(self, query: str) -> Path | None:
        if not self.cache_dir:
            return None
        key = hashlib.sha1(f"{self.lang}|{self.country}|{query}".encode()).hexdigest()
        return self.cache_dir / f"{key}.json"

    def __call__(self, query: str) -> list[str]:
        path = self._cache_path(query)
        if path and path.exists():
            return json.loads(path.read_text(encoding="utf-8"))

        wait = self.delay - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        params = urllib.parse.urlencode({"client": "firefox", "q": query, "hl": self.lang, "gl": self.country})
        req = urllib.request.Request(f"{SUGGEST_URL}?{params}", headers={"User-Agent": "Mozilla/5.0 kws-research"})
        suggestions: list[str] = []
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                suggestions = [s for s in data[1] if isinstance(s, str)]
                break
            except Exception:
                if attempt == 2:
                    suggestions = []
                else:
                    time.sleep(2 ** attempt)
        self._last_call = time.monotonic()

        if path:
            path.write_text(json.dumps(suggestions), encoding="utf-8")
        return suggestions


def build_queries(seed: str, alphabet: bool = True, questions: bool = True,
                  prepositions: bool = True, commercial: bool = True) -> list[str]:
    """Generate the autocomplete probe queries for one seed."""
    seed = seed.strip()
    queries = [seed]
    if alphabet:
        queries += [f"{seed} {c}" for c in string.ascii_lowercase + string.digits]
    if questions:
        queries += [f"{q} {seed}" for q in QUESTION_PREFIXES]
    if prepositions:
        queries += [f"{seed} {p}" for p in PREPOSITION_SUFFIXES]
    if commercial:
        queries += [f"{c} {seed}" for c in COMMERCIAL_SUFFIXES[:3]] + [f"{seed} {c}" for c in COMMERCIAL_SUFFIXES[3:]]
    return queries


def expand_seeds(seeds: Iterable[str], fetch: Fetcher, depth: int = 1,
                 max_per_level: int = 50, progress: Callable[[str], None] | None = None,
                 **query_opts) -> dict[str, dict]:
    """Expand seeds through autocomplete.

    Returns {keyword: {"seed": str, "hits": int, "best_rank": int, "depth": int, "source": "autocomplete"}}.
    `hits` counts how many probe queries surfaced the keyword - a rough popularity signal.
    Depth >1 re-expands the top `max_per_level` new suggestions (by hits) of each level, base probe only.
    """
    results: dict[str, dict] = {}

    def record(kw: str, seed: str, rank: int, level: int) -> None:
        kw = " ".join(kw.lower().split())
        if not kw:
            return
        entry = results.get(kw)
        if entry is None:
            results[kw] = {"seed": seed, "hits": 1, "best_rank": rank, "depth": level, "source": "autocomplete"}
        else:
            entry["hits"] += 1
            entry["best_rank"] = min(entry["best_rank"], rank)

    for seed in seeds:
        seed = " ".join(seed.lower().split())
        if not seed:
            continue
        if progress:
            progress(f"Expanding seed: {seed}")
        frontier = [seed]
        for level in range(1, depth + 1):
            before = set(results)
            for term in frontier:
                probes = build_queries(term, **query_opts) if level == 1 else [term]
                for q in probes:
                    for rank, s in enumerate(fetch(q), start=1):
                        record(s, seed, rank, level)
            new = [k for k in results if k not in before and results[k]["seed"] == seed]
            new.sort(key=lambda k: (-results[k]["hits"], results[k]["best_rank"]))
            frontier = new[:max_per_level]
            if not frontier:
                break
    return results
