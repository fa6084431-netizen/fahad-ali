"""Keyword enrichment: intent, type, modifiers, filtering and opportunity scoring."""

from __future__ import annotations

import math
import re

QUESTION_WORDS = {"how", "what", "why", "where", "when", "which", "who", "whom", "whose",
                  "can", "is", "are", "does", "do", "should", "will", "could", "would"}

INTENT_PATTERNS = {
    "transactional": r"\b(buy|order|purchase|price|prices|pricing|cost|costs|cheap|cheapest|discount|coupon|deal|deals|"
                     r"for sale|hire|book|booking|quote|subscription|download|free trial|near me|shop|store)\b",
    "commercial": r"\b(best|top|review|reviews|vs|versus|compare|comparison|alternative|alternatives|"
                  r"rated|affordable|premium|recommended|pros and cons)\b",
    "navigational": r"\b(login|log in|sign in|signup|sign up|account|website|official|app|dashboard|portal|contact|"
                    r"customer service|phone number|address)\b",
    "informational": r"\b(how|what|why|where|when|who|which|guide|tutorial|tips|ideas|examples|meaning|definition|"
                     r"learn|ways|steps|benefits|history|types of|is|does|can)\b",
}

LOCAL_PATTERN = r"\b(near me|nearby|in my area|open now|closest)\b"
YEAR_PATTERN = r"\b(19|20)\d{2}\b"


def classify_intent(keyword: str, brand_terms: list[str] | None = None) -> str:
    kw = keyword.lower()
    if brand_terms and any(re.search(rf"\b{re.escape(b.lower())}\b", kw) for b in brand_terms):
        if not re.search(INTENT_PATTERNS["commercial"], kw):
            return "navigational"
    for intent in ("transactional", "commercial", "navigational", "informational"):
        if re.search(INTENT_PATTERNS[intent], kw):
            return intent
    # Short head terms are ambiguous; long phrases without modifiers lean informational.
    return "informational" if len(kw.split()) >= 4 else "mixed"


def keyword_type(keyword: str) -> str:
    words = keyword.split()
    if words and words[0] in QUESTION_WORDS:
        return "question"
    if len(words) <= 2:
        return "head"
    if len(words) == 3:
        return "body"
    return "long-tail"


def funnel_stage(intent: str) -> str:
    return {"informational": "TOFU", "commercial": "MOFU", "transactional": "BOFU",
            "navigational": "BOFU"}.get(intent, "TOFU")


def content_suggestion(intent: str, ktype: str, keyword: str) -> str:
    if re.search(LOCAL_PATTERN, keyword):
        return "Local landing page / GBP"
    if intent == "transactional":
        return "Product / service page"
    if intent == "commercial":
        return "Comparison or listicle" if re.search(r"\b(best|top|vs|versus|alternative)", keyword) else "Review / category page"
    if intent == "navigational":
        return "Brand / utility page"
    if ktype == "question":
        return "Blog post / FAQ"
    return "Blog post / guide" if intent == "informational" else "Pillar page (check SERP)"


def is_excluded(keyword: str, negatives: list[str]) -> bool:
    kw = keyword.lower()
    return any(re.search(rf"\b{re.escape(n.lower())}\b", kw) for n in negatives if n.strip())


def opportunity_score(rec: dict, max_hits: int) -> float:
    """0-100 score. Uses volume/KD/CPC when present (from imports); falls back to autocomplete signals."""
    volume, kd, cpc = rec.get("volume"), rec.get("kd"), rec.get("cpc")
    if volume:
        vol_part = min(math.log10(volume + 1) / 5, 1.0)          # 100k searches ~= 1.0
        kd_part = 1 - (min(kd, 100) / 100) if kd is not None else 0.5
        cpc_part = min((cpc or 0) / 10, 1.0)                     # $10+ CPC ~= 1.0
        score = 0.5 * vol_part + 0.35 * kd_part + 0.15 * cpc_part
    else:
        hits = rec.get("hits", 0)
        rank = rec.get("best_rank") or 10
        hit_part = math.log1p(hits) / math.log1p(max(max_hits, 1))
        rank_part = 1 - (min(rank, 10) - 1) / 10
        score = 0.6 * hit_part + 0.4 * rank_part
        score *= 0.8  # unverified demand: never outrank keywords with real volume data at the same strength
    if rec.get("intent_auto") in ("transactional", "commercial"):
        score = min(score * 1.1, 1.0)
    return round(score * 100, 1)


def enrich(records: dict[str, dict], brand_terms: list[str] | None = None,
           negatives: list[str] | None = None, min_words: int = 1, max_words: int = 10) -> list[dict]:
    """Turn merged {keyword: data} into scored, filtered rows sorted by score."""
    negatives = negatives or []
    max_hits = max((r.get("hits", 0) for r in records.values()), default=1)
    rows = []
    for kw, rec in records.items():
        n = len(kw.split())
        if n < min_words or n > max_words or is_excluded(kw, negatives):
            continue
        intent = classify_intent(kw, brand_terms)
        ktype = keyword_type(kw)
        row = {
            "keyword": kw,
            "seed": rec.get("seed", ""),
            "intent_auto": intent,
            "intent_tool": rec.get("intent", ""),
            "type": ktype,
            "funnel": funnel_stage(intent),
            "words": n,
            "volume": rec.get("volume"),
            "kd": rec.get("kd"),
            "cpc": rec.get("cpc"),
            "position": rec.get("position"),
            "impressions": rec.get("impressions"),
            "url": rec.get("url", ""),
            "hits": rec.get("hits", 0),
            "best_rank": rec.get("best_rank"),
            "local": bool(re.search(LOCAL_PATTERN, kw)),
            "has_year": bool(re.search(YEAR_PATTERN, kw)),
            "content_type": content_suggestion(intent, ktype, kw),
            "sources": rec.get("sources", rec.get("source", "")),
        }
        row["score"] = opportunity_score(row, max_hits)
        rows.append(row)
    rows.sort(key=lambda r: (-r["score"], -(r["volume"] or 0), r["keyword"]))
    return rows
