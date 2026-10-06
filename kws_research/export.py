"""Write results to CSV and a multi-sheet XLSX report."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

KEYWORD_COLUMNS = ["keyword", "score", "cluster", "intent_auto", "intent_tool", "funnel", "type", "content_type",
                   "volume", "kd", "cpc", "position", "impressions", "url", "words", "hits", "best_rank",
                   "local", "has_year", "seed", "sources"]
CLUSTER_COLUMNS = ["cluster", "size", "total_volume", "avg_kd", "avg_score", "dominant_intent", "content_type", "keywords"]


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in columns})


def summary_rows(rows: list[dict], clusters: list[dict], meta: dict) -> list[tuple[str, object]]:
    out: list[tuple[str, object]] = [(k, v) for k, v in meta.items()]
    out += [("Total keywords", len(rows)), ("Total clusters", len(clusters)),
            ("Keywords with volume data", sum(1 for r in rows if r.get("volume")))]
    for label, key in (("Intent", "intent_auto"), ("Type", "type"), ("Funnel", "funnel")):
        for value, count in Counter(r[key] for r in rows).most_common():
            out.append((f"{label}: {value}", count))
    return out


def write_xlsx(path: Path, rows: list[dict], clusters: list[dict], meta: dict) -> bool:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        return False

    wb = Workbook()
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F4E78")

    def sheet(ws, columns, data):
        ws.append(columns)
        for cell in ws[1]:
            cell.font, cell.fill = header_font, header_fill
        for r in data:
            ws.append([r.get(c) if not isinstance(r.get(c), bool) else ("yes" if r.get(c) else "") for c in columns])
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for i, c in enumerate(columns, start=1):
            width = max([len(str(c))] + [len(str(r.get(c) or "")) for r in data[:500]])
            ws.column_dimensions[get_column_letter(i)].width = min(max(width + 2, 8), 60)

    ws = wb.active
    ws.title = "Summary"
    ws.append(["Metric", "Value"])
    for cell in ws[1]:
        cell.font, cell.fill = header_font, header_fill
    for k, v in summary_rows(rows, clusters, meta):
        ws.append([k, v])
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 34, 40

    sheet(wb.create_sheet("Keywords"), KEYWORD_COLUMNS, rows)
    sheet(wb.create_sheet("Clusters"), CLUSTER_COLUMNS, clusters)
    sheet(wb.create_sheet("Questions"), KEYWORD_COLUMNS, [r for r in rows if r["type"] == "question"])
    sheet(wb.create_sheet("Quick Wins"), KEYWORD_COLUMNS, quick_wins(rows))
    wb.save(path)
    return True


def quick_wins(rows: list[dict]) -> list[dict]:
    """Low-difficulty keywords with demand, or GSC queries ranking on page 2 (positions 8-20)."""
    out = []
    for r in rows:
        low_kd = r.get("kd") is not None and r["kd"] <= 30 and (r.get("volume") or 0) >= 50
        striking = r.get("position") is not None and 8 <= r["position"] <= 20
        if low_kd or striking:
            out.append(r)
    return out


def export_all(out_dir: str | Path, rows: list[dict], clusters: list[dict], meta: dict) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = [out / "keywords.csv", out / "clusters.csv", out / "questions.csv", out / "quick_wins.csv"]
    write_csv(written[0], rows, KEYWORD_COLUMNS)
    write_csv(written[1], clusters, CLUSTER_COLUMNS)
    write_csv(written[2], [r for r in rows if r["type"] == "question"], KEYWORD_COLUMNS)
    write_csv(written[3], quick_wins(rows), KEYWORD_COLUMNS)
    if write_xlsx(out / "kws_report.xlsx", rows, clusters, meta):
        written.append(out / "kws_report.xlsx")
    return written
