"""GitHub Actions collector — new architecture (v3).

Flow:
  1. Fetch RSS from all categories (rss_collector.py)
  2. Deduplicate against seen_urls.json (skip already-processed)
  3. Translate English titles + summaries to Chinese (Haiku, batch)
  4. Save daily RSS archive → archive/rss/{today}.json
  5. Generate HTML reports → docs/
  6. Output new_articles count for workflow condition

No deep analysis here. Analysis is on-demand in the browser.
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import anthropic
from rss_collector import RSSCollector

MODEL         = "claude-haiku-4-5"
DATA_DIR      = ROOT / "data"
ARCHIVE_DIR   = ROOT / "archive" / "rss"
SEEN_FILE     = ROOT / "archive" / "seen_urls.json"
MAX_TRANSLATE = 80       # max articles per translation batch call
SEEN_TTL_DAYS = 14       # prune seen URLs older than this


# ---------------------------------------------------------------------------
# Seen-URL cache
# ---------------------------------------------------------------------------

def _load_seen() -> dict:
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_seen(seen: dict, today: str):
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=SEEN_TTL_DAYS)).strftime("%Y-%m-%d")
    pruned = {u: d for u, d in seen.items() if d >= cutoff}
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(pruned, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

def _is_english(text: str) -> bool:
    """Rough check: if >60% ASCII letters → English."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    ascii_letters = [c for c in letters if ord(c) < 128]
    return len(ascii_letters) / len(letters) > 0.6


# ---------------------------------------------------------------------------
# Batch translation (Haiku)
# ---------------------------------------------------------------------------

def translate_batch(client: anthropic.Anthropic, items: list[dict]) -> list[dict]:
    """Translate a batch of {title, summary} from English to Traditional Chinese.

    Returns same list with added fields: title_zh, summary_zh.
    Items that are already Chinese are returned unchanged (title_zh = title_en).
    """
    to_translate = [(i, a) for i, a in enumerate(items) if _is_english(a["title"])]
    if not to_translate:
        for a in items:
            a["title_zh"]   = a["title"]
            a["summary_zh"] = a.get("summary", "")
        return items

    lines = []
    for seq, (orig_idx, a) in enumerate(to_translate, 1):
        lines.append(
            f"{seq}. TITLE: {a['title']}\n"
            f"   SUMMARY: {a.get('summary','')[:300]}"
        )

    prompt = (
        "Translate each article's TITLE and SUMMARY from English to Traditional Chinese (繁體中文).\n"
        "Return a JSON array (no markdown):\n"
        '[{"index":1,"title_zh":"...","summary_zh":"..."},{"index":2,...}]\n\n'
        "Rules:\n"
        "- Keep company names, product names, technical terms in English\n"
        "- summary_zh: 1-2 sentences max, keep it concise\n"
        "- If SUMMARY is empty, set summary_zh to empty string\n\n"
        "Articles:\n" + "\n\n".join(lines)
    )

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            system="You are a professional tech translator. Return only valid JSON array.",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        translations = {t["index"]: t for t in json.loads(raw)}
    except Exception as e:
        print(f"    ⚠ Translation error: {e} — using original text")
        translations = {}

    # Apply translations
    for seq, (orig_idx, a) in enumerate(to_translate, 1):
        t = translations.get(seq, {})
        items[orig_idx]["title_zh"]   = t.get("title_zh", a["title"])
        items[orig_idx]["summary_zh"] = t.get("summary_zh", a.get("summary", ""))

    # Non-English articles: copy as-is
    translated_idxs = {orig_idx for _, (orig_idx, _) in enumerate(to_translate)}
    for i, a in enumerate(items):
        if i not in translated_idxs:
            a["title_zh"]   = a["title"]
            a["summary_zh"] = a.get("summary", "")

    return items


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    today  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"=== SOC Planning Agent v3 — Collector ({today}) ===\n")

    # ── Step 1: Load dedup cache ──
    seen = _load_seen()
    print(f"📋 Seen URL cache: {len(seen)} entries\n")

    # ── Step 2: Fetch RSS ──
    print("📡 Fetching RSS feeds...")
    collector = RSSCollector(max_age_days=1)
    raw_by_cat = collector.collect_daily()

    # Filter seen URLs
    new_by_cat = {}
    for cat, articles in raw_by_cat.items():
        fresh = [a for a in articles if a["url"] not in seen]
        if fresh:
            new_by_cat[cat] = fresh
            print(f"  [{cat}] {len(fresh)} new / {len(articles)} total")

    total_new = sum(len(v) for v in new_by_cat.values())
    print(f"\n✓ {total_new} new articles across {len(new_by_cat)} categories\n")

    if total_new == 0:
        print("ℹ️  No new articles — nothing to do.")
        _write_output(0, today)
        return

    # ── Step 3: Translate English titles + summaries ──
    print("🌐 Translating English content...")
    translated_by_cat = {}
    for cat, articles in new_by_cat.items():
        # Process in chunks to stay within token limits
        chunk_size = 30
        translated = []
        for i in range(0, len(articles), chunk_size):
            chunk = articles[i:i + chunk_size]
            translated.extend(translate_batch(client, chunk))
            if i + chunk_size < len(articles):
                time.sleep(1)
        translated_by_cat[cat] = translated
        print(f"  [{cat}] ✓ {len(translated)} articles translated")

    # ── Step 4: Save daily RSS archive ──
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = ARCHIVE_DIR / f"{today}.json"

    # Merge with existing today's archive if it exists
    existing = []
    if archive_path.exists():
        try:
            existing = json.loads(archive_path.read_text(encoding="utf-8")).get("articles", [])
        except Exception:
            pass

    existing_urls = {a["url"] for a in existing}
    new_articles_flat = []
    for cat, articles in translated_by_cat.items():
        for a in articles:
            if a["url"] not in existing_urls:
                new_articles_flat.append({**a, "category": cat})

    all_articles = existing + new_articles_flat
    archive_data = {
        "date":         today,
        "updated_at":   datetime.now(timezone.utc).isoformat(),
        "total":        len(all_articles),
        "new_this_run": len(new_articles_flat),
        "articles":     all_articles,
    }
    archive_path.write_text(json.dumps(archive_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n💾 Archive saved: {archive_path} ({len(all_articles)} total, {len(new_articles_flat)} new)")

    # ── Step 5: Generate HTML ──
    print("\n📄 Generating HTML reports...")
    from generate_html import generate_reports
    generate_reports(translated_by_cat, today)

    # ── Step 6: Update seen-URL cache ──
    for articles in translated_by_cat.values():
        for a in articles:
            if a.get("url"):
                seen[a["url"]] = today
    _save_seen(seen, today)
    print(f"✓ Seen URL cache updated: {len(seen)} entries")

    # ── Step 7: Signal to workflow ──
    _write_output(len(new_articles_flat), today)
    print(f"\n✅ Done — {len(new_articles_flat)} new articles")


def _write_output(new_count: int, today: str):
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"new_articles={new_count}\n")
            f.write(f"today={today}\n")


if __name__ == "__main__":
    main()
