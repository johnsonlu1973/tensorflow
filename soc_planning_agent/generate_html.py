"""Read today's JSON data and generate HTML reports in docs/.

Called by GitHub Actions after github_collector.py finishes.
Outputs:
  docs/collection_<id>_<category>_<date>.html  (one per category)
  docs/index.html                               (rebuilt from all files)

Sets GITHUB_OUTPUT variables for use in subsequent Slack notification step:
  new_reports  - number of HTML files generated
  trend_total  - total trend articles across all categories
  date         - collection date (YYYY-MM-DD)
  pages_url    - GitHub Pages base URL
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from export_html import generate_collection_html, generate_index_html

PAGES_URL = "https://johnsonlu1973.github.io/tensorflow"


def _next_collection_id(docs_dir: Path) -> int:
    ids = []
    for f in docs_dir.glob("collection_*.html"):
        parts = f.stem.split("_")
        if len(parts) >= 2 and parts[1].isdigit():
            ids.append(int(parts[1]))
    return max(ids, default=0) + 1


def _set_output(name: str, value: str):
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"{name}={value}\n")


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data_file = ROOT / "data" / f"{today}.json"

    if not data_file.exists():
        print(f"⚠ No data file for {today}: {data_file}")
        _set_output("new_reports", "0")
        _set_output("trend_total", "0")
        _set_output("date", today)
        _set_output("pages_url", PAGES_URL)
        sys.exit(0)

    data = json.loads(data_file.read_text(encoding="utf-8"))
    collections = data.get("collections", [])

    docs_dir = ROOT.parent / "docs"
    docs_dir.mkdir(exist_ok=True)

    next_id = _next_collection_id(docs_dir)
    new_files = []
    trend_total = 0

    for i, coll in enumerate(collections):
        coll_id = next_id + i
        category = coll["category"]
        collected_at = data.get("collected_at", today)
        articles = coll.get("articles", [])

        html = generate_collection_html(
            {
                "category": category,
                "topic": coll.get("topic", f"Daily RSS digest — {category}"),
                "collected_at": collected_at,
            },
            articles,
        )

        fname = f"collection_{coll_id}_{category}_{today}.html"
        (docs_dir / fname).write_text(html, encoding="utf-8")
        print(f"  ✓ {fname}  ({coll['article_count']} 篇, {coll['trend_count']} 趨勢)")

        trend_total += coll.get("trend_count", 0)
        new_files.append(
            {
                "filename": fname,
                "category": category,
                "date": today,
                "total": coll["article_count"],
                "trend": coll["trend_count"],
            }
        )

    # Rebuild index — merge new + existing collection pages
    fresh_fnames = {c["filename"] for c in new_files}
    existing = []
    for f in sorted(docs_dir.glob("collection_*.html"), reverse=True):
        if f.name in fresh_fnames:
            continue
        parts = f.stem.split("_")
        if len(parts) >= 4:
            existing.append(
                {
                    "filename": f.name,
                    "category": "_".join(parts[2:-1]),
                    "date": parts[-1],
                    "total": "?",
                    "trend": "?",
                }
            )

    merged = new_files + existing
    index_html = generate_index_html(merged)
    (docs_dir / "index.html").write_text(index_html, encoding="utf-8")
    print(f"  ✓ index.html updated ({len(merged)} 份報告)")

    print(f"\n✅ 生成 {len(new_files)} 份報告，共 {trend_total} 篇趨勢文章")

    _set_output("new_reports", str(len(new_files)))
    _set_output("trend_total", str(trend_total))
    _set_output("date", today)
    _set_output("pages_url", PAGES_URL)


if __name__ == "__main__":
    main()
