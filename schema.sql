-- News digest schema (SQLite)
-- Run once at container start: sqlite3 /data/news.db < schema.sql
PRAGMA journal_mode = WAL;      -- collector writes, MCP server reads/writes
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;     -- wait instead of failing on a locked DB

-- 1. Where articles come from -------------------------------------------
CREATE TABLE IF NOT EXISTS sources (
  id          INTEGER PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE,            -- 'BBC News', 'UN News'
  feed_url    TEXT NOT NULL,
  kind        TEXT NOT NULL DEFAULT 'rss'      -- 'rss' | 'google_news_query' | 'api'
              CHECK (kind IN ('rss','google_news_query','api')),
  enabled     INTEGER NOT NULL DEFAULT 1,
  last_fetched_at TEXT,                        -- ISO 8601 UTC
  last_error  TEXT                             -- helps you spot dead feeds
);

-- 2. Topics and when they are active ------------------------------------
CREATE TABLE IF NOT EXISTS topics (
  id          INTEGER PRIMARY KEY,
  slug        TEXT NOT NULL UNIQUE,            -- 'energy', 'sustainability'
  name        TEXT NOT NULL,
  description TEXT                             -- hint for Claude when summarising
);

CREATE TABLE IF NOT EXISTS topic_keywords (
  topic_id    INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
  keyword     TEXT NOT NULL,
  PRIMARY KEY (topic_id, keyword)
);

-- A topic can have many schedule rows, so two topics can overlap on a day.
CREATE TABLE IF NOT EXISTS topic_schedule (
  id          INTEGER PRIMARY KEY,
  topic_id    INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
  start_date  TEXT NOT NULL,                   -- 'YYYY-MM-DD'
  end_date    TEXT,                            -- NULL = open ended
  weekdays    TEXT,                            -- NULL = every day, else 'mon,thu'
  CHECK (end_date IS NULL OR end_date >= start_date)
);

-- 3. Raw articles (headline, snippet, link only) ------------------------
CREATE TABLE IF NOT EXISTS articles (
  id           INTEGER PRIMARY KEY,
  source_id    INTEGER NOT NULL REFERENCES sources(id),
  url          TEXT NOT NULL,
  url_hash     TEXT NOT NULL UNIQUE,           -- hash of normalised URL: dedupe on insert
  title        TEXT NOT NULL,
  snippet      TEXT,                           -- keep short; link back for the rest
  published_at TEXT,                           -- ISO 8601 UTC, from the feed
  fetched_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);

-- Many-to-many: one article can match two topics
CREATE TABLE IF NOT EXISTS article_topics (
  article_id  INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  topic_id    INTEGER NOT NULL REFERENCES topics(id)   ON DELETE CASCADE,
  PRIMARY KEY (article_id, topic_id)
);

-- 4. Claude's output: digests, their stories, and the sources behind them
CREATE TABLE IF NOT EXISTS digests (
  id          INTEGER PRIMARY KEY,
  digest_date TEXT NOT NULL,                   -- 'YYYY-MM-DD'
  topic_id    INTEGER NOT NULL REFERENCES topics(id),
  kind        TEXT NOT NULL DEFAULT 'daily' CHECK (kind IN ('daily','weekly')),
  headline    TEXT NOT NULL,
  overview    TEXT,                            -- 2-3 sentence intro
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  UNIQUE (digest_date, topic_id, kind)         -- re-running replaces, not duplicates
);

CREATE TABLE IF NOT EXISTS digest_stories (
  id          INTEGER PRIMARY KEY,
  digest_id   INTEGER NOT NULL REFERENCES digests(id) ON DELETE CASCADE,
  position    INTEGER NOT NULL,                -- display order
  title       TEXT NOT NULL,
  summary     TEXT NOT NULL,                   -- Claude's own words
  UNIQUE (digest_id, position)
);

-- Which articles a story was built from (group + dedupe across outlets).
-- Also gives the page its "read more" links.
CREATE TABLE IF NOT EXISTS story_articles (
  story_id    INTEGER NOT NULL REFERENCES digest_stories(id) ON DELETE CASCADE,
  article_id  INTEGER NOT NULL REFERENCES articles(id),
  PRIMARY KEY (story_id, article_id)
);

-- 5. Handy view: articles not yet used in any digest, with their topics
CREATE VIEW IF NOT EXISTS unsummarised_articles AS
SELECT a.id, a.title, a.snippet, a.url, a.published_at,
       s.name AS source, t.slug AS topic
FROM articles a
JOIN sources s         ON s.id = a.source_id
JOIN article_topics at ON at.article_id = a.id
JOIN topics t          ON t.id = at.topic_id
WHERE a.id NOT IN (SELECT article_id FROM story_articles);

-- 6. Which topics are active on a given day (the MCP server runs this):
--   SELECT t.* FROM topics t
--   JOIN topic_schedule ts ON ts.topic_id = t.id
--   WHERE :today >= ts.start_date
--     AND (ts.end_date IS NULL OR :today <= ts.end_date)
--     AND (ts.weekdays IS NULL OR instr(ts.weekdays, :weekday_abbrev) > 0);

-- 7. Articles Claude reviewed for a topic and judged irrelevant, so they stop being offered
--    again. (mcp_server/server.py also creates this table at startup: keep the two in sync.)
CREATE TABLE IF NOT EXISTS dismissed_articles (
  article_id   INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  topic_id     INTEGER NOT NULL REFERENCES topics(id)   ON DELETE CASCADE,
  dismissed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  PRIMARY KEY (article_id, topic_id)
);
