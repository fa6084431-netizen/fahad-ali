"""Load seeds and import keyword exports from Semrush, Ahrefs, Google Search Console, Keyword Planner, etc."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

# Lower-cased header aliases -> canonical field.
COLUMN_ALIASES = {
    "keyword": ["keyword", "keywords", "query", "top queries", "search term", "phrase", "term"],
    "volume": ["volume", "search volume", "avg. monthly searches", "avg monthly searches", "sv", "monthly volume"],
    "kd": ["keyword difficulty", "kd", "difficulty", "kd %", "keyword difficulty index", "competition (indexed value)"],
    "cpc": ["cpc", "cpc (usd)", "top of page bid (high range)", "cost per click"],
    "clicks": ["clicks"],
    "impressions": ["impressions"],
    "position": ["position", "avg. position", "current position"],
    "url": ["url", "current url", "page", "top pages", "landing page"],
    "intent": ["intent", "intents", "search intent"],
}

NUMERIC_FIELDS = {"volume", "kd", "cpc", "clicks", "impressions", "position"}


def load_seeds(path: str | Path) -> list[str]:
    """One seed per line; blank lines and lines starting with # are ignored."""
    seeds = []
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            seeds.append(line)
    return seeds


def _to_number(value: str) -> float | None:
    if value is None:
        return None
    v = str(value).strip().replace(",", "").replace("$", "").replace("%", "")
    if not v or v in {"-", "n/a", "N/A"}:
        return None
    # Keyword Planner ranges like "1K – 10K" -> lower bound
    v = re.split(r"\s*[–-]\s*", v)[0] if re.search(r"\d[KkMm]?\s*[–-]\s*\d", v) else v
    mult = 1
    if v[-1:].upper() == "K":
        mult, v = 1_000, v[:-1]
    elif v[-1:].upper() == "M":
        mult, v = 1_000_000, v[:-1]
    try:
        return float(v) * mult
    except ValueError:
        return None


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _find_header(rows: list[list[str]]) -> int:
    """Keyword Planner exports have title rows before the header; find the first row naming a keyword column."""
    names = set(COLUMN_ALIASES["keyword"])
    for i, row in enumerate(rows[:10]):
        if any(c.strip().lower() in names for c in row):
            return i
    return 0


def import_export(path: str | Path) -> dict[str, dict]:
    """Import a CSV/TSV keyword export into {keyword: {field: value, "source": filename}}."""
    path = Path(path)
    text = _read_text(path)
    delimiter = "\t" if text.count("\t") > text.count(",") else ","
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    if not rows:
        return {}
    h = _find_header(rows)
    header = [c.strip().lower() for c in rows[h]]

    mapping: dict[str, int] = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in header:
                mapping[field] = header.index(alias)
                break
    if "keyword" not in mapping:
        raise ValueError(f"{path}: no keyword/query column found in header {rows[h]}")

    out: dict[str, dict] = {}
    for row in rows[h + 1:]:
        if len(row) <= mapping["keyword"]:
            continue
        kw = " ".join(row[mapping["keyword"]].lower().split())
        if not kw:
            continue
        rec: dict = {"source": path.name}
        for field, idx in mapping.items():
            if field == "keyword" or idx >= len(row):
                continue
            rec[field] = _to_number(row[idx]) if field in NUMERIC_FIELDS else row[idx].strip()
        if kw in out:  # keep the richer/higher-volume duplicate
            if (rec.get("volume") or 0) <= (out[kw].get("volume") or 0):
                continue
        out[kw] = rec
    return out
