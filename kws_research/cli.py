"""Command-line interface: python -m kws_research --help"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from . import __version__
from .pipeline import run
from .sources import load_seeds


def _split(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kws_research", description="Automated keyword research: "
                                "expand seeds via Google Autocomplete, merge Semrush/Ahrefs/GSC/Keyword Planner "
                                "exports, classify intent, cluster and score keywords, export CSV + XLSX.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("-s", "--seeds", help="Comma-separated seed keywords")
    p.add_argument("-f", "--seed-file", help="File with one seed per line")
    p.add_argument("-i", "--import", dest="imports", action="append", default=[],
                   help="CSV/TSV export to merge (repeatable): Semrush, Ahrefs, GSC, Keyword Planner...")
    p.add_argument("-o", "--out", default=None, help="Output directory (default: output/<timestamp>)")
    p.add_argument("--no-expand", action="store_true", help="Skip Google Autocomplete; only use imports + seeds")
    p.add_argument("--depth", type=int, default=1, help="Autocomplete expansion depth (default 1)")
    p.add_argument("--lang", default="en", help="Language code for autocomplete (default en)")
    p.add_argument("--country", default="us", help="Country code for autocomplete (default us)")
    p.add_argument("--no-alphabet", action="store_true", help="Skip 'seed a..z 0..9' probes")
    p.add_argument("--no-questions", action="store_true", help="Skip question-word probes")
    p.add_argument("--no-prepositions", action="store_true", help="Skip preposition probes")
    p.add_argument("--no-commercial", action="store_true", help="Skip commercial-modifier probes")
    p.add_argument("--brand", help="Comma-separated brand terms (treated as navigational)")
    p.add_argument("--exclude", help="Comma-separated negative words; matching keywords are dropped")
    p.add_argument("--min-words", type=int, default=1)
    p.add_argument("--max-words", type=int, default=10)
    p.add_argument("--cluster-threshold", type=float, default=0.5,
                   help="Token-overlap similarity (0-1) required to join a cluster (default 0.5)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    seeds = _split(args.seeds) + (load_seeds(args.seed_file) if args.seed_file else [])
    if not seeds and not args.imports:
        print("error: provide --seeds, --seed-file or --import", file=sys.stderr)
        return 2
    out = args.out or f"output/{datetime.now():%Y%m%d-%H%M%S}"
    run(seeds, out, imports=args.imports, expand=not args.no_expand, depth=args.depth,
        lang=args.lang, country=args.country, brand_terms=_split(args.brand), negatives=_split(args.exclude),
        cluster_threshold=args.cluster_threshold, min_words=args.min_words, max_words=args.max_words,
        alphabet=not args.no_alphabet, questions=not args.no_questions,
        prepositions=not args.no_prepositions, commercial=not args.no_commercial)
    return 0


if __name__ == "__main__":
    sys.exit(main())
