"""End-to-end pipeline: seeds -> expansion + imports -> merge -> enrich -> cluster -> export."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from .analyze import enrich
from .cluster import cluster_keywords
from .expand import Fetcher, GoogleSuggest, expand_seeds
from .export import export_all
from .sources import import_export


def merge(records: dict[str, dict], incoming: dict[str, dict]) -> None:
    """Merge incoming {kw: data} into records; metric fields fill gaps, sources accumulate."""
    for kw, data in incoming.items():
        src = data.get("source", "")
        if kw not in records:
            records[kw] = {**data, "sources": src}
            continue
        rec = records[kw]
        for k, v in data.items():
            if k in ("source", "sources"):
                continue
            if rec.get(k) in (None, "") and v not in (None, ""):
                rec[k] = v
        existing = [s for s in str(rec.get("sources", "")).split("; ") if s]
        if src and src not in existing:
            rec["sources"] = "; ".join(existing + [src])


def run(seeds: list[str], out_dir: str | Path, imports: list[str | Path] = (), expand: bool = True,
        fetch: Fetcher | None = None, depth: int = 1, lang: str = "en", country: str = "us",
        brand_terms: list[str] | None = None, negatives: list[str] | None = None,
        cluster_threshold: float = 0.5, min_words: int = 1, max_words: int = 10,
        log: Callable[[str], None] = print, **query_opts) -> dict:
    records: dict[str, dict] = {}

    if expand and seeds:
        fetch = fetch or GoogleSuggest(lang=lang, country=country)
        expanded = expand_seeds(seeds, fetch, depth=depth, progress=log, **query_opts)
        merge(records, expanded)
        log(f"Autocomplete: {len(expanded)} keywords")

    for path in imports:
        data = import_export(path)
        merge(records, data)
        log(f"Imported {len(data)} keywords from {Path(path).name}")

    # Seeds themselves are always candidates.
    merge(records, {" ".join(s.lower().split()): {"seed": s, "source": "seed"} for s in seeds})

    rows = enrich(records, brand_terms=brand_terms, negatives=negatives, min_words=min_words, max_words=max_words)
    clusters = cluster_keywords(rows, threshold=cluster_threshold)
    meta = {"Date": date.today().isoformat(), "Seeds": ", ".join(seeds), "Language / Country": f"{lang} / {country}",
            "Imports": ", ".join(Path(p).name for p in imports) or "-"}
    files = export_all(out_dir, rows, clusters, meta)
    log(f"Done: {len(rows)} keywords in {len(clusters)} clusters -> {Path(out_dir)}")
    return {"rows": rows, "clusters": clusters, "files": files}
