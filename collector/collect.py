"""Fetch enabled RSS feeds and store articles that match any topic's keywords.

Run from the my_newsroom folder:
    python collector/collect.py
Set NEWS_DB to use a different database path (Docker will do this).
"""
import calendar
import hashlib
import html
import os
import re
import sqlite3
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser

DB_PATH = os.environ.get("NEWS_DB", "data/news.db")
SNIPPET_MAX = 300  # keep snippets short; the link covers the rest

# Query parameters that only track clicks and would defeat de-duplication
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
                   "utm_content", "at_medium", "at_campaign", "ocid", "cmpid"}

feedparser.USER_AGENT = "my_newsroom/0.1 (personal news digest project)"


SCHEMA_PATH = os.environ.get("SCHEMA_PATH", "schema.sql")
SEED_PATH = os.environ.get("SEED_PATH", "config/seed.sql")


def init_db(conn: sqlite3.Connection) -> None:
    """Make sure tables exist. Load the starter seed only into an empty database."""
    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            conn.executescript(f.read())
    empty = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0
    if empty and os.path.exists(SEED_PATH):
        with open(SEED_PATH, encoding="utf-8") as f:
            conn.executescript(f.read())


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def normalise_url(url: str) -> str:
    """Lower-case host, drop fragment and tracking params so the same story hashes the same."""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in TRACKING_PARAMS]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(normalise_url(url).encode("utf-8")).hexdigest()


def clean_snippet(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")      # strip HTML tags
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    if len(text) > SNIPPET_MAX:
        text = text[:SNIPPET_MAX].rsplit(" ", 1)[0] + "..."
    return text


def published_iso(entry) -> str | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    ts = calendar.timegm(parsed)  # feedparser gives UTC struct_time
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def keyword_to_regex(keyword: str) -> str:
    """Escape the keyword for regex, then let * mean 'any further letters'."""
    return re.escape(keyword.strip()).replace(r"\*", r"\w*")

def load_topic_patterns(conn: sqlite3.Connection) -> dict[int, re.Pattern]:
    """One compiled regex per topic. Word boundaries stop 'oil' matching 'toilet'."""
    keywords: dict[int, list[str]] = {}
    for topic_id, keyword in conn.execute("SELECT topic_id, keyword FROM topic_keywords"):
        keywords.setdefault(topic_id, []).append(keyword_to_regex(keyword))
    return {
        tid: re.compile(r"\b(?:" + "|".join(words) + r")\b", re.IGNORECASE)
        for tid, words in keywords.items() if words
    }


def collect_source(conn, source_id, name, feed_url, patterns) -> tuple[int, int]:
    """Fetch one feed. Returns (entries_seen, articles_saved)."""
    feed = feedparser.parse(feed_url)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if feed.bozo and not feed.entries:   # unreadable feed: record why and move on
        error = str(feed.get("bozo_exception", "unknown error"))[:500]
        conn.execute("UPDATE sources SET last_fetched_at=?, last_error=? WHERE id=?",
                     (now, error, source_id))
        print(f"  ! {name}: {error}")
        return 0, 0

    saved = 0
    for entry in feed.entries:
        link, title = entry.get("link"), (entry.get("title") or "").strip()
        if not link or not title:
            continue
        snippet = clean_snippet(entry.get("summary", ""))
        haystack = f"{title} {snippet}"
        matched = [tid for tid, pattern in patterns.items() if pattern.search(haystack)]
        if not matched:
            continue                      # not about any topic: don't store it

        cur = conn.execute(
            """INSERT OR IGNORE INTO articles
               (source_id, url, url_hash, title, snippet, published_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source_id, link, url_hash(link), title, snippet, published_iso(entry)),
        )
        if cur.rowcount:
            article_id = cur.lastrowid
            saved += 1
        else:  # already stored: look it up so new topic tags can still be added
            article_id = conn.execute(
                "SELECT id FROM articles WHERE url_hash = ?", (url_hash(link),)
            ).fetchone()[0]
        conn.executemany(
            "INSERT OR IGNORE INTO article_topics (article_id, topic_id) VALUES (?, ?)",
            [(article_id, tid) for tid in matched],
        )
        
    conn.execute("UPDATE sources SET last_fetched_at=?, last_error=NULL WHERE id=?",
                 (now, source_id))
    return len(feed.entries), saved


def main() -> None:
    conn = connect()
    init_db(conn)
    patterns = load_topic_patterns(conn)
    if not patterns:
        print("No topics with keywords found. Add some rows to topics and topic_keywords first.")
        return

    sources = conn.execute(
        "SELECT id, name, feed_url FROM sources WHERE enabled = 1 AND kind = 'rss'"
    ).fetchall()
    if not sources:
        print("No enabled RSS sources found. Add a row to the sources table first.")
        return

    total_seen = total_saved = 0
    for source_id, name, feed_url in sources:
        try:
            seen, saved = collect_source(conn, source_id, name, feed_url, patterns)
            conn.commit()                 # commit per source so one failure keeps the rest
            print(f"  {name}: {seen} entries, {saved} new matching articles")
            total_seen += seen
            total_saved += saved
        except Exception as exc:          # a bad feed must not stop the others
            conn.rollback()
            print(f"  ! {name}: failed ({exc})")

    print(f"Done: {total_saved} new articles saved from {total_seen} entries.")
    conn.close()


if __name__ == "__main__":
    main()
