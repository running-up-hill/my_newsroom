"""Build a static news page from saved digests. Standard library only.

Reads digests (written by the MCP server's save_digest tool) and writes:
    <SITE_OUT>/index.html   the page
    <SITE_OUT>/.nojekyll    tells GitHub Pages to serve the files as they are

The output is deterministic: the page only changes when a digest changes, so re-running it
every few minutes causes no needless file writes (or git changes).
"""
import html
import os
import sqlite3
import sys
import zlib
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit

DB_PATH = os.environ.get("NEWS_DB", "data/news.db")
OUT_DIR = os.environ.get("SITE_OUT", "docs")
DAYS = int(os.environ.get("SITE_DAYS", "14"))           # how far back the page reaches
SITE_TITLE = os.environ.get("SITE_TITLE", "My Newsroom")


# ---------- helpers ----------

def esc(text) -> str:
    return html.escape(str(text or ""), quote=True)


def safe_url(url: str) -> str | None:
    """Article links come from external feeds, so only ever allow plain http(s) links."""
    parts = urlsplit((url or "").strip())
    return url.strip() if parts.scheme in ("http", "https") and parts.netloc else None


def nice_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B %Y')}"


# Badge colours as HSL hues (0 = red, 140 = green, 215 = blue). New topics get a stable colour
# from the palette below, chosen to stay clear of red, green and blue.
TOPIC_HUES = {"war": 0, "sustainability": 140, "energy": 215}
FALLBACK_HUES = [30, 280, 175, 320, 50, 245]            # orange, purple, teal, pink, yellow, indigo


def hue(slug: str) -> int:
    if slug in TOPIC_HUES:
        return TOPIC_HUES[slug]
    return FALLBACK_HUES[zlib.crc32(slug.encode("utf-8")) % len(FALLBACK_HUES)]


# ---------- data ----------

def load_digests(conn: sqlite3.Connection, since: str) -> list[dict]:
    digests = []
    for d in conn.execute(
            """SELECT d.id, d.digest_date, d.kind, d.headline, d.overview, d.created_at,
                      t.slug, t.name AS topic_name
               FROM digests d JOIN topics t ON t.id = d.topic_id
               WHERE d.digest_date >= ?
               ORDER BY d.digest_date DESC, t.name, d.kind""", (since,)):
        stories = []
        for s in conn.execute(
                "SELECT id, title, summary FROM digest_stories WHERE digest_id = ? ORDER BY position",
                (d["id"],)):
            links = conn.execute(
                """SELECT a.title, a.url, src.name AS source
                   FROM story_articles sa JOIN articles a ON a.id = sa.article_id
                   JOIN sources src ON src.id = a.source_id
                   WHERE sa.story_id = ? ORDER BY src.name, a.id""", (s["id"],)).fetchall()
            stories.append({"title": s["title"], "summary": s["summary"], "links": links})
        digests.append({**dict(d), "stories": stories})
    return digests


# ---------- rendering ----------

MAX_LINKS_PER_OUTLET = 2   # four BBC links for one story is clutter, not help


def outlet(name: str) -> str:
    """'BBC News - World' -> 'BBC News': readers care about the outlet, not the feed section."""
    return name.split(" - ")[0].strip()


def render_links(links) -> str:
    seen: dict[str, int] = {}
    out = []
    for link in links:
        url = safe_url(link["url"])
        if not url:
            continue
        name = outlet(link["source"])
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > MAX_LINKS_PER_OUTLET:
            continue
        label = name if seen[name] == 1 else f"{name} ({seen[name]})"
        out.append(f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer" '
                   f'title="{esc(link["title"])}">{esc(label)}</a>')
    return f'<p class="sources">Read more: {" · ".join(out)}</p>' if out else ""


def render_digest(d: dict) -> str:
    kind = '<span class="kind">Weekly</span>' if d["kind"] == "weekly" else ""
    overview = f'<p class="overview">{esc(d["overview"])}</p>' if d["overview"] else ""
    stories = "".join(
        f'<li><h4>{esc(s["title"])}</h4><p>{esc(s["summary"])}</p>{render_links(s["links"])}</li>'
        for s in d["stories"])
    return (f'<article class="digest" data-topic="{esc(d["slug"])}" style="--hue:{hue(d["slug"])}">'
            f'<header><div class="meta"><span class="badge">{esc(d["topic_name"])}</span>{kind}</div>'
            f'<h3>{esc(d["headline"])}</h3>{overview}</header><ol class="stories">{stories}</ol></article>')


CSS = """
:root{--bg:#fafaf7;--card:#fff;--text:#1d1d1b;--muted:#5f5f5a;--line:#e4e2da;--link:#0a58ca;--badge-l:88%;--badge-t:20%}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--card:#1e1e1c;--text:#eceae3;--muted:#a3a199;--line:#33322e;--link:#7db3ff;--badge-l:26%;--badge-t:90%}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:17px/1.55 Georgia,'Times New Roman',serif}
.wrap{max-width:780px;margin:0 auto;padding:2rem 1.1rem 4rem}
h1{font-size:2rem;margin:.2rem 0 .1rem;letter-spacing:-.01em}
.updated{color:var(--muted);font:.85rem system-ui,sans-serif;margin:0 0 1.4rem}
.filters{display:flex;flex-wrap:wrap;gap:.5rem;margin:0 0 1.6rem;font:.9rem system-ui,sans-serif}
.filters button{border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:999px;padding:.35rem .9rem;cursor:pointer}
.filters button[aria-pressed=true]{background:var(--text);color:var(--bg);border-color:var(--text)}
.day h2{font:600 .95rem system-ui,sans-serif;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:2.2rem 0 .8rem;border-bottom:1px solid var(--line);padding-bottom:.4rem}
.digest{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:1.2rem 1.3rem;margin:0 0 1.2rem}
.digest h3{font-size:1.35rem;line-height:1.3;margin:.5rem 0 .4rem}
.meta{display:flex;gap:.5rem;align-items:center;font:.78rem system-ui,sans-serif}
.badge{background:hsl(var(--hue) 55% var(--badge-l));color:hsl(var(--hue) 60% var(--badge-t));padding:.15rem .6rem;border-radius:999px;font-weight:600}
.kind{color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.overview{color:var(--muted);margin:.2rem 0 .8rem}
.stories{margin:1rem 0 0;padding-left:1.3rem}
.stories li{margin:0 0 1.1rem}
.stories h4{font-size:1.05rem;margin:0 0 .15rem}
.stories p{margin:.1rem 0}
.sources{font:.85rem system-ui,sans-serif;color:var(--muted)}
a{color:var(--link)}
.empty{color:var(--muted);text-align:center;padding:3rem 0}
footer{color:var(--muted);font:.8rem/1.5 system-ui,sans-serif;margin-top:3rem;border-top:1px solid var(--line);padding-top:1rem}
"""

JS = """
(function(){
  var buttons=document.querySelectorAll('.filters button');
  function apply(topic){
    document.querySelectorAll('.digest').forEach(function(d){d.hidden=topic!=='all'&&d.dataset.topic!==topic;});
    document.querySelectorAll('.day').forEach(function(day){day.hidden=!day.querySelector('.digest:not([hidden])');});
    buttons.forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.topic===topic));});
  }
  buttons.forEach(function(b){b.addEventListener('click',function(){apply(b.dataset.topic);});});
})();
"""


def render_page(digests: list[dict]) -> str:
    if digests:
        topics = {}
        for d in digests:
            topics.setdefault(d["slug"], d["topic_name"])
        filters = ""
        if len(topics) > 1:
            filters = ('<nav class="filters" aria-label="Filter by topic">'
                       '<button data-topic="all" aria-pressed="true">All</button>'
                       + "".join(f'<button data-topic="{esc(slug)}" aria-pressed="false">{esc(name)}</button>'
                                 for slug, name in sorted(topics.items(), key=lambda kv: kv[1]))
                       + "</nav>")
        days: dict[str, list[dict]] = {}
        for d in digests:
            days.setdefault(d["digest_date"], []).append(d)
        body = filters + "".join(
            f'<section class="day"><h2>{esc(nice_date(day))}</h2>{"".join(render_digest(d) for d in items)}</section>'
            for day, items in days.items())
        latest = max(d["created_at"] for d in digests)
        updated = f"Last updated {latest[:10]} {latest[11:16]} UTC"
    else:
        body = '<p class="empty">No digests yet. Run a digest session in Claude and they will appear here.</p>'
        updated = ""

    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(SITE_TITLE)}</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E%F0%9F%97%9E%3C/text%3E%3C/svg%3E">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<h1>{esc(SITE_TITLE)}</h1>
<p class="updated">{esc(updated)}</p>
{body}
<footer>A personal, non-commercial news digest. Summaries are written by an AI assistant from the
headlines and short snippets that the linked outlets publish, so check the original article for
the full story. Every story links back to its sources.</footer>
</div>
<script>{JS}</script>
</body>
</html>
"""


# ---------- main ----------

def main() -> int:
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}; nothing to build yet.", file=sys.stderr)
        return 0
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA query_only = ON")
    try:
        since = (datetime.now(timezone.utc).date() - timedelta(days=DAYS)).isoformat()
        digests = load_digests(conn, since)
    except sqlite3.OperationalError as exc:             # e.g. tables not created yet
        print(f"Could not read digests yet: {exc}", file=sys.stderr)
        return 0
    finally:
        conn.close()

    page = render_page(digests)
    os.makedirs(OUT_DIR, exist_ok=True)
    target = os.path.join(OUT_DIR, "index.html")
    previous = None
    if os.path.exists(target):
        with open(target, encoding="utf-8") as f:
            previous = f.read()
    if page != previous:
        with open(target, "w", encoding="utf-8", newline="\n") as f:
            f.write(page)
        print(f"Wrote {target}: {len(digests)} digest(s) from the last {DAYS} days.")
    else:
        print("No changes.")
    open(os.path.join(OUT_DIR, ".nojekyll"), "a").close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
