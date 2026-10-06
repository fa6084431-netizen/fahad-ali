"""Lightweight keyword clustering by shared stemmed tokens (no external NLP dependencies)."""

from __future__ import annotations

STOPWORDS = {"a", "an", "the", "for", "to", "of", "in", "on", "and", "or", "with", "without", "near", "me", "my",
             "is", "are", "do", "does", "can", "how", "what", "why", "where", "when", "which", "who", "best", "top",
             "vs", "i", "you", "your", "it", "be", "by", "at", "from", "that", "this", "should", "will"}


def stem(word: str) -> str:
    for suffix in ("ing", "ies", "es", "ers", "er", "ed", "ly", "s"):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


def tokens(keyword: str) -> frozenset[str]:
    toks = frozenset(stem(w) for w in keyword.lower().split() if w not in STOPWORDS)
    return toks or frozenset(keyword.lower().split())


def jaccard(a: frozenset, b: frozenset) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def cluster_keywords(rows: list[dict], threshold: float = 0.5) -> list[dict]:
    """Greedy clustering: rows are visited in score order; each joins the most similar existing
    cluster head if similarity >= threshold, otherwise starts a new cluster. Mutates rows with
    `cluster` and returns cluster summaries sorted by total volume/score."""
    clusters: list[dict] = []
    for row in rows:
        toks = tokens(row["keyword"])
        best, best_sim = None, 0.0
        for c in clusters:
            sim = jaccard(toks, c["tokens"])
            if sim > best_sim:
                best, best_sim = c, sim
        if best is not None and best_sim >= threshold:
            best["members"].append(row)
        else:
            clusters.append({"tokens": toks, "members": [row]})

    summaries = []
    for c in clusters:
        members = c["members"]
        head = members[0]["keyword"]  # highest-scored member (rows arrive sorted)
        for m in members:
            m["cluster"] = head
        intents = [m["intent_auto"] for m in members]
        summaries.append({
            "cluster": head,
            "size": len(members),
            "total_volume": sum(m["volume"] or 0 for m in members) or None,
            "avg_kd": round(sum(m["kd"] for m in members if m["kd"] is not None) /
                            max(1, sum(1 for m in members if m["kd"] is not None)), 1)
            if any(m["kd"] is not None for m in members) else None,
            "avg_score": round(sum(m["score"] for m in members) / len(members), 1),
            "dominant_intent": max(set(intents), key=intents.count),
            "content_type": members[0]["content_type"],
            "keywords": ", ".join(m["keyword"] for m in members[:15]) + (" ..." if len(members) > 15 else ""),
        })
    summaries.sort(key=lambda s: (-(s["total_volume"] or 0), -s["avg_score"] * s["size"]))
    return summaries
