"""Make a consistent, self-contained copy of a newsroom database.

Usage:  python backup_db.py <source.db> <destination.db>

Uses SQLite's online backup, so it is safe while the collector is running and it picks up
recent writes that are still in the WAL file (a plain file copy can miss them). The copy is
switched out of WAL mode so it is a single file you can open anywhere, such as DB Browser.
"""
import sqlite3
import sys

if len(sys.argv) != 3:
    sys.exit("usage: backup_db.py <source.db> <destination.db>")
src_path, dest_path = sys.argv[1], sys.argv[2]

src = sqlite3.connect(src_path, timeout=30)
src.execute("PRAGMA query_only = ON")        # this script can never change the live database
dest = sqlite3.connect(dest_path)
src.backup(dest)
dest.execute("PRAGMA journal_mode = DELETE")  # one standalone file, no -wal/-shm
check = dest.execute("PRAGMA integrity_check").fetchone()[0]

counts = {}
for table in ("articles", "digests", "topics", "sources"):
    try:
        counts[table] = dest.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.OperationalError:          # e.g. a brand-new database with no tables yet
        counts[table] = "n/a"
dest.close()
src.close()

if check != "ok":
    sys.exit(f"INTEGRITY CHECK FAILED: {check}")
print("backup ok:", counts)
