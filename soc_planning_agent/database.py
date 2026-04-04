"""SQLite database layer for SOC Planning Agent."""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS collections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collected_at TEXT NOT NULL,
                    category TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sources TEXT DEFAULT '[]'
                );

                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analyzed_at TEXT NOT NULL,
                    analysis_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    collection_ids TEXT DEFAULT '[]'
                );

                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id INTEGER NOT NULL,
                    comment TEXT NOT NULL,
                    tags TEXT DEFAULT '[]'
                );

                CREATE TABLE IF NOT EXISTS user_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    updated_at TEXT NOT NULL,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS product_insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    insight_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'open'
                );

                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    collected_at TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    source TEXT NOT NULL,
                    published TEXT DEFAULT '',
                    article_type TEXT NOT NULL DEFAULT 'info',
                    one_liner TEXT DEFAULT '',
                    rss_summary TEXT DEFAULT '',
                    full_text TEXT DEFAULT '',
                    analysis TEXT DEFAULT '',
                    FOREIGN KEY (collection_id) REFERENCES collections(id)
                );
            """)

    # --- Collections ---

    def save_collection(self, category: str, topic: str, content: str, sources: list) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO collections (collected_at, category, topic, content, sources) VALUES (?,?,?,?,?)",
                (datetime.now().isoformat(), category, topic, content, json.dumps(sources)),
            )
            return cur.lastrowid

    def get_recent_collections(self, days: int = 7, category: Optional[str] = None) -> list:
        query = """
            SELECT * FROM collections
            WHERE collected_at >= datetime('now', ?)
        """
        params = [f"-{days} days"]
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY collected_at DESC"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def get_collection_by_id(self, collection_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM collections WHERE id=?", (collection_id,)).fetchone()
            return dict(row) if row else None

    # --- Analyses ---

    def save_analysis(self, analysis_type: str, title: str, content: str, collection_ids: list) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO analyses (analyzed_at, analysis_type, title, content, collection_ids) VALUES (?,?,?,?,?)",
                (datetime.now().isoformat(), analysis_type, title, content, json.dumps(collection_ids)),
            )
            return cur.lastrowid

    def get_recent_analyses(self, days: int = 30, analysis_type: Optional[str] = None) -> list:
        query = """
            SELECT * FROM analyses
            WHERE analyzed_at >= datetime('now', ?)
        """
        params = [f"-{days} days"]
        if analysis_type:
            query += " AND analysis_type = ?"
            params.append(analysis_type)
        query += " ORDER BY analyzed_at DESC"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def get_analysis_by_id(self, analysis_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM analyses WHERE id=?", (analysis_id,)).fetchone()
            return dict(row) if row else None

    # --- Feedback ---

    def save_feedback(self, target_type: str, target_id: int, comment: str, tags: list = None) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO feedback (created_at, target_type, target_id, comment, tags) VALUES (?,?,?,?,?)",
                (datetime.now().isoformat(), target_type, target_id, comment, json.dumps(tags or [])),
            )
            return cur.lastrowid

    def get_all_feedback(self, target_type: Optional[str] = None) -> list:
        query = "SELECT * FROM feedback"
        params = []
        if target_type:
            query += " WHERE target_type = ?"
            params.append(target_type)
        query += " ORDER BY created_at DESC"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def get_feedback_for_target(self, target_type: str, target_id: int) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM feedback WHERE target_type=? AND target_id=? ORDER BY created_at DESC",
                (target_type, target_id),
            ).fetchall()
            return [dict(r) for r in rows]

    # --- User Preferences (learning) ---

    def set_preference(self, key: str, value: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO user_preferences (updated_at, key, value) VALUES (?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (datetime.now().isoformat(), key, value),
            )

    def get_preference(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM user_preferences WHERE key=?", (key,)).fetchone()
            return row["value"] if row else default

    def get_all_preferences(self) -> dict:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM user_preferences").fetchall()
            return {r["key"]: r["value"] for r in rows}

    # --- Product Insights ---

    def save_insight(self, insight_type: str, title: str, content: str, priority: str = "medium") -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO product_insights (created_at, insight_type, title, content, priority) VALUES (?,?,?,?,?)",
                (datetime.now().isoformat(), insight_type, title, content, priority),
            )
            return cur.lastrowid

    def get_insights(self, status: str = "open", days: int = 90) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM product_insights WHERE status=? AND created_at >= datetime('now', ?) ORDER BY created_at DESC",
                (status, f"-{days} days"),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_insight_status(self, insight_id: int, status: str):
        with self._connect() as conn:
            conn.execute("UPDATE product_insights SET status=? WHERE id=?", (status, insight_id))

    # --- Articles ---

    def save_article(self, collection_id: int, category: str, title: str, url: str,
                     source: str, published: str, article_type: str, one_liner: str,
                     rss_summary: str = "", full_text: str = "", analysis: str = "") -> int:
        with self._connect() as conn:
            # Skip duplicate URLs within same collection
            exists = conn.execute(
                "SELECT id FROM articles WHERE collection_id=? AND url=?",
                (collection_id, url),
            ).fetchone()
            if exists:
                return exists["id"]
            cur = conn.execute(
                """INSERT INTO articles
                   (collection_id, category, collected_at, title, url, source, published,
                    article_type, one_liner, rss_summary, full_text, analysis)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (collection_id, category, datetime.now().isoformat(), title, url, source,
                 published, article_type, one_liner, rss_summary, full_text, analysis),
            )
            return cur.lastrowid

    def get_articles_by_collection(self, collection_id: int) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM articles WHERE collection_id=? ORDER BY id",
                (collection_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_article_by_id(self, article_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
            return dict(row) if row else None

    # --- Stats ---

    def get_stats(self) -> dict:
        with self._connect() as conn:
            return {
                "total_collections": conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0],
                "total_analyses": conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0],
                "total_feedback": conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0],
                "total_insights": conn.execute("SELECT COUNT(*) FROM product_insights").fetchone()[0],
                "collections_this_week": conn.execute(
                    "SELECT COUNT(*) FROM collections WHERE collected_at >= datetime('now', '-7 days')"
                ).fetchone()[0],
                "analyses_this_month": conn.execute(
                    "SELECT COUNT(*) FROM analyses WHERE analyzed_at >= datetime('now', '-30 days')"
                ).fetchone()[0],
            }
