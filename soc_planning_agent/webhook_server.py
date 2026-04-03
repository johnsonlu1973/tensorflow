"""Webhook server for receiving RSS articles from n8n.

Architecture:
  n8n (internet access)
    ├─ RSS Feed nodes → keyword filter → group by category
    ├─ Anthropic node (Haiku) → summarize filtered articles
    └─ HTTP Request → POST /ingest/analyzed  ← this server saves to DB

Two ingest modes:
  POST /ingest          raw articles  → agent calls Claude to summarize
  POST /ingest/analyzed pre-analyzed  → save directly (n8n already called Claude)
  POST /ingest/batch    multiple categories at once (raw)

Endpoints:
  GET  /health   — health check
  GET  /stats    — DB statistics
"""
import json
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))

from database import Database
from config import DB_PATH

VALID_CATEGORIES = {
    "agentic_ai", "chips_soc", "mobile", "5g_cpe",
    "csp_cloud", "3gpp", "vendors", "operators",
}


def _build_raw_content(articles: list) -> tuple[str, list]:
    """Format raw article list into readable content + source URL list."""
    lines = []
    sources = []
    for i, a in enumerate(articles[:30], 1):
        title = a.get("title", "No title")
        url = a.get("url", a.get("link", ""))
        summary = a.get("summary", a.get("description", ""))[:500]
        pub = a.get("published", a.get("pubDate", ""))
        source = a.get("source", "n8n-rss")
        lines.append(
            f"{i}. [{source}] {title}\n"
            f"   Date: {pub}\n"
            f"   URL: {url}\n"
            f"   {summary}"
        )
        if url:
            sources.append(url)
    return "\n\n".join(lines), list(dict.fromkeys(sources))


class WebhookHandler(BaseHTTPRequestHandler):
    db: Database = None  # injected by run_server()

    def log_message(self, fmt, *args):
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] {fmt % args}")

    def _send_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode())

    # ── GET ──────────────────────────────────────────────────────────────

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(200, {"status": "ok", "db": str(DB_PATH)})
        elif path == "/stats":
            self._send_json(200, self.db.get_stats())
        else:
            self._send_json(404, {"error": "not found"})

    # ── POST ─────────────────────────────────────────────────────────────

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self._read_json()
        except (json.JSONDecodeError, ValueError) as e:
            self._send_json(400, {"error": f"invalid JSON: {e}"})
            return

        if path == "/ingest":
            self._handle_ingest(body)
        elif path == "/ingest/analyzed":
            self._handle_analyzed(body)
        elif path == "/ingest/batch":
            self._handle_batch(body)
        else:
            self._send_json(404, {"error": "not found"})

    # ── Handlers ─────────────────────────────────────────────────────────

    def _handle_ingest(self, body: dict):
        """Receive raw articles from n8n (agent will summarize later)."""
        category = body.get("category", "").strip().lower()
        articles = body.get("articles", [])

        if category not in VALID_CATEGORIES:
            self._send_json(400, {"error": f"invalid category '{category}'"})
            return
        if not articles:
            self._send_json(200, {"saved": 0, "message": "no articles"})
            return

        today = datetime.now().strftime("%Y-%m-%d")
        content, sources = _build_raw_content(articles)
        coll_id = self.db.save_collection(
            category=category,
            topic=f"RSS via n8n — {category} ({len(articles)} articles, {today})",
            content=content,
            sources=sources,
        )
        print(f"  ✓ #{coll_id} [{category}] {len(articles)} raw articles saved")
        self._send_json(200, {"saved": 1, "collection_id": coll_id, "mode": "raw"})

    def _handle_analyzed(self, body: dict):
        """Receive pre-analyzed summary from n8n+Claude (skip local summarization).

        Expected payload:
        {
          "category": "agentic_ai",
          "summary": "# 摘要\\n...",   ← Claude's output from n8n Anthropic node
          "sources": ["https://...", ...],
          "article_count": 5
        }
        """
        category = body.get("category", "").strip().lower()
        summary = body.get("summary", "").strip()
        sources = body.get("sources", [])
        count = body.get("article_count", 0)

        if category not in VALID_CATEGORIES:
            self._send_json(400, {"error": f"invalid category '{category}'"})
            return
        if not summary:
            self._send_json(200, {"saved": 0, "message": "empty summary"})
            return

        today = datetime.now().strftime("%Y-%m-%d")
        coll_id = self.db.save_collection(
            category=category,
            topic=f"n8n+Claude digest — {category} ({count} articles, {today})",
            content=summary,
            sources=sources,
        )
        print(f"  ✓ #{coll_id} [{category}] pre-analyzed summary saved (n8n+Claude)")
        self._send_json(200, {"saved": 1, "collection_id": coll_id, "mode": "analyzed"})

    def _handle_batch(self, body):
        """Receive multiple categories as a JSON array."""
        if not isinstance(body, list):
            self._send_json(400, {"error": "expected JSON array"})
            return

        saved_ids = []
        today = datetime.now().strftime("%Y-%m-%d")
        for item in body:
            category = item.get("category", "").strip().lower()
            articles = item.get("articles", [])
            if category not in VALID_CATEGORIES or not articles:
                continue
            content, sources = _build_raw_content(articles)
            coll_id = self.db.save_collection(
                category=category,
                topic=f"RSS via n8n — {category} ({len(articles)} articles, {today})",
                content=content,
                sources=sources,
            )
            saved_ids.append(coll_id)
            print(f"  ✓ #{coll_id} [{category}] {len(articles)} articles (batch)")

        self._send_json(200, {"saved": len(saved_ids), "collection_ids": saved_ids})


def run_server(host: str = "0.0.0.0", port: int = 8080):
    """Start the n8n webhook HTTP server (no external dependencies)."""
    db = Database(DB_PATH)
    WebhookHandler.db = db

    server = HTTPServer((host, port), WebhookHandler)
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║         SOC Agent — n8n Webhook Server                       ║
╠══════════════════════════════════════════════════════════════╣
║  Listening : http://{host}:{port:<5}                         ║
║                                                              ║
║  Endpoints:                                                  ║
║    GET  /health            health check                      ║
║    GET  /stats             DB statistics                     ║
║    POST /ingest            raw articles  (agent summarizes)  ║
║    POST /ingest/analyzed   n8n+Claude summary (save direct)  ║
║    POST /ingest/batch      multiple categories at once       ║
║                                                              ║
║  n8n → /ingest/analyzed payload:                             ║
║    {{                                                         ║
║      "category": "agentic_ai",                               ║
║      "summary":  "<Claude output>",                          ║
║      "sources":  ["https://..."],                            ║
║      "article_count": 5                                      ║
║    }}                                                         ║
║                                                              ║
║  Valid categories:                                           ║
║    agentic_ai  chips_soc  mobile  5g_cpe                     ║
║    csp_cloud   3gpp       vendors operators                  ║
║                                                              ║
║  Press Ctrl+C to stop.                                       ║
╚══════════════════════════════════════════════════════════════╝
""")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Webhook server stopped]")
        server.server_close()
