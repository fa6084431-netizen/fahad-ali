import csv
from pathlib import Path

from kws_research.analyze import classify_intent, enrich, keyword_type
from kws_research.cli import main
from kws_research.cluster import cluster_keywords
from kws_research.expand import build_queries, expand_seeds
from kws_research.pipeline import run
from kws_research.sources import import_export

FAKE = {
    "seo tools": ["seo tools", "seo tools free", "seo tools for small business"],
    "seo tools f": ["seo tools free", "seo tools for wordpress"],
    "how seo tools": ["how seo tools work", "how to use seo tools"],
    "best seo tools": ["best seo tools 2026", "best seo tools free"],
    "seo tools price": ["seo tools price comparison"],
}


def fake_fetch(q):
    return FAKE.get(q, [])


def test_build_queries_includes_modifiers():
    qs = build_queries("seo tools")
    assert "seo tools" in qs and "seo tools a" in qs and "how seo tools" in qs and "best seo tools" in qs
    assert build_queries("x", alphabet=False, questions=False, prepositions=False, commercial=False) == ["x"]


def test_expand_counts_hits_and_rank():
    res = expand_seeds(["SEO  Tools"], fake_fetch)
    assert res["seo tools free"]["hits"] == 2
    assert res["seo tools free"]["best_rank"] == 1
    assert res["how to use seo tools"]["seed"] == "seo tools"


def test_intent_and_type():
    assert classify_intent("buy running shoes") == "transactional"
    assert classify_intent("best running shoes") == "commercial"
    assert classify_intent("nike login") == "navigational"
    assert classify_intent("how to clean running shoes") == "informational"
    assert classify_intent("nike running shoes", brand_terms=["nike"]) == "navigational"
    assert keyword_type("how to tie shoes") == "question"
    assert keyword_type("shoes") == "head"
    assert keyword_type("red running shoes for women") == "long-tail"


def test_import_semrush_and_keyword_planner(tmp_path):
    sem = tmp_path / "semrush.csv"
    sem.write_text("Keyword,Intent,Volume,Keyword Difficulty,CPC (USD)\nSEO Tools,commercial,\"12,100\",78,4.5\n")
    kp = tmp_path / "kp.csv"
    kp.write_text("Keyword Stats 2026\nAll locations\nKeyword\tAvg. monthly searches\tCompetition\n"
                  "seo audit\t1K – 10K\tHigh\n", encoding="utf-16")
    s = import_export(sem)
    assert s["seo tools"]["volume"] == 12100 and s["seo tools"]["kd"] == 78 and s["seo tools"]["cpc"] == 4.5
    k = import_export(kp)
    assert k["seo audit"]["volume"] == 1000


def test_enrich_filters_and_scores():
    recs = {"cheap seo tools": {"volume": 1000, "kd": 20}, "seo tools reddit": {"hits": 3},
            "seo tools": {"volume": 10, "kd": 90}}
    rows = enrich(recs, negatives=["reddit"])
    assert [r["keyword"] for r in rows] == ["cheap seo tools", "seo tools"]
    assert 0 <= rows[1]["score"] < rows[0]["score"] <= 100


def test_clustering_groups_similar():
    rows = enrich({"seo tools free": {"hits": 5}, "free seo tools": {"hits": 4}, "keyword research guide": {"hits": 1}})
    clusters = cluster_keywords(rows)
    assert len(clusters) == 2
    assert rows[0]["cluster"] == rows[1]["cluster"]


def test_pipeline_end_to_end(tmp_path):
    gsc = tmp_path / "Queries.csv"
    gsc.write_text("Top queries,Clicks,Impressions,CTR,Position\nseo tools free,10,900,1.1%,12.4\n")
    result = run(["seo tools"], tmp_path / "out", imports=[gsc], fetch=fake_fetch, log=lambda m: None)
    names = {p.name for p in result["files"]}
    assert {"keywords.csv", "clusters.csv", "questions.csv", "quick_wins.csv", "kws_report.xlsx"} <= names
    rows = list(csv.DictReader((tmp_path / "out" / "keywords.csv").open(encoding="utf-8-sig")))
    free = next(r for r in rows if r["keyword"] == "seo tools free")
    assert free["position"] == "12.4" and "Queries.csv" in free["sources"] and "autocomplete" in free["sources"]
    wins = list(csv.DictReader((tmp_path / "out" / "quick_wins.csv").open(encoding="utf-8-sig")))
    assert [w["keyword"] for w in wins] == ["seo tools free"]


def test_cli_import_only(tmp_path, capsys):
    exp = tmp_path / "ahrefs.csv"
    exp.write_text("Keyword,Volume,KD,CPC\nlink building,5000,60,7\n")
    assert main(["--no-expand", "-i", str(exp), "-o", str(tmp_path / "o")]) == 0
    assert Path(tmp_path / "o" / "kws_report.xlsx").exists()
    assert main([]) == 2
