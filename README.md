# KWS Research Automation

Automated keyword research pipeline:

1. **Expand** seed keywords with Google Autocomplete (no API key) — alphabet soup (`seed a…z, 0…9`),
   question words (`how/what/why… seed`), prepositions (`seed for/vs/with…`) and commercial modifiers
   (`best/top/cheap seed`, `seed price/review/near me…`). Optional depth-2 re-expansion.
2. **Import** exports from Semrush, Ahrefs, Google Search Console, Google Keyword Planner and similar tools
   (columns are auto-detected; CSV/TSV, UTF-8 or UTF-16) and merge them with autocomplete results.
3. **Enrich** every keyword: search intent (informational / commercial / transactional / navigational),
   type (head / body / long-tail / question), funnel stage (TOFU/MOFU/BOFU), local & year flags and a
   suggested content type.
4. **Score** each keyword 0–100 (volume, KD and CPC when available; autocomplete frequency/rank otherwise).
5. **Cluster** keywords by shared stemmed terms so each cluster maps to one page.
6. **Export** CSVs plus an Excel report with *Summary, Keywords, Clusters, Questions* and *Quick Wins*
   (low-KD keywords with demand, and GSC queries ranking in positions 8–20).

## Usage

```bash
pip install -r requirements.txt

# Seeds from the command line
python -m kws_research -s "seo services, keyword research" --country us --lang en

# Seeds from a file + merge tool exports, drop unwanted terms
python -m kws_research -f seeds.txt -i semrush.csv -i gsc-queries.csv --exclude "free,jobs,reddit"

# Only analyse/cluster existing exports (no Google requests)
python -m kws_research --no-expand -i ahrefs.csv -o output/ahrefs-analysis
```

Results go to `output/<timestamp>/` (or `-o DIR`): `keywords.csv`, `clusters.csv`, `questions.csv`,
`quick_wins.csv`, `kws_report.xlsx`.

Useful options: `--depth 2` (deeper expansion), `--brand "acme"` (brand terms → navigational),
`--min-words/--max-words`, `--cluster-threshold 0.4` (looser clusters), `--no-alphabet`, `--no-questions`,
`--no-prepositions`, `--no-commercial`. Run `python -m kws_research --help` for all flags.

Autocomplete responses are cached in `.kws_cache/` and requests are rate-limited, so re-runs are fast.

## GitHub Actions automation

`.github/workflows/kws-research.yml`:

- **Run on demand**: *Actions → KWS Research → Run workflow*, enter seeds, country, language, depth and
  negative words. The report is attached to the run as an artifact (`kws-report-N`).
- **Weekly schedule**: every Monday it researches the seeds in `seeds.txt`.
- Any CSV/TSV placed in `imports/` is merged automatically.
- Tests run on every change to the code.

## Tests

```bash
pip install pytest && python -m pytest -q
```
