"""SQLite storage: scan cache, play history and small key/value state (e.g. the saved queue).

A single connection is shared by all threads and guarded by a lock; every
operation here is short, so this is simpler than one connection per thread.
"""
import json, os, sqlite3, threading

_conn = None
_lock = threading.RLock()

# Each entry upgrades the schema by one version (stored in PRAGMA user_version).
MIGRATIONS = [
    """
    CREATE TABLE files (                 -- tags read from each audio file, to skip re-reading unchanged files
        path     TEXT PRIMARY KEY,
        mtime_ns INTEGER NOT NULL,
        size     INTEGER NOT NULL,
        meta     TEXT NOT NULL           -- JSON
    );
    CREATE TABLE plays (                 -- one row per track listened to
        id        INTEGER PRIMARY KEY,
        track_id  TEXT NOT NULL,
        played_at INTEGER NOT NULL,      -- unix time
        title     TEXT NOT NULL,         -- copied so the history survives renames and deletions
        artist    TEXT NOT NULL,
        album     TEXT NOT NULL,
        output    TEXT NOT NULL          -- "remote" (mpv) or "local" (browser)
    );
    CREATE INDEX plays_time ON plays(played_at);
    CREATE INDEX plays_track ON plays(track_id, played_at);
    CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """,
    # plays.dur: track length in seconds (hours listened). No SQL comment here: SQLite copies the
    # column definition, comments included, into the stored CREATE TABLE and would break it.
    "ALTER TABLE plays ADD COLUMN dur INTEGER NOT NULL DEFAULT 0",
]


def open_db(path):
    global _conn
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)   # autocommit; explicit BEGIN below
    conn.execute("PRAGMA journal_mode=WAL")       # readers don't block the writer
    conn.execute("PRAGMA synchronous=NORMAL")     # safe with WAL, much faster on phone storage
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for i, sql in enumerate(MIGRATIONS[version:], start=version + 1):
        conn.execute("BEGIN")
        _run_script(conn, sql)
        conn.execute(f"PRAGMA user_version={i}")
        conn.execute("COMMIT")
    _conn = conn


def _run_script(conn, sql):
    # executescript() would commit the open transaction, so run statement by statement
    for stmt in sql.split(";"):
        if stmt.strip():
            conn.execute(stmt)


def query(sql, args=()):
    with _lock:
        return _conn.execute(sql, args).fetchall()


def execute(sql, args=()):
    with _lock:
        _conn.execute(sql, args)


# ---------------------------------------------------------------- key/value

def kv_get(key, default=None):
    rows = query("SELECT value FROM kv WHERE key = ?", (key,))
    return json.loads(rows[0][0]) if rows else default


def kv_set(key, value):
    execute("INSERT INTO kv(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)))


def kv_delete(key):
    execute("DELETE FROM kv WHERE key = ?", (key,))


# ---------------------------------------------------------------- scan cache

def files_load():
    """path -> (mtime_ns, size, meta) for every cached file."""
    return {p: (m, s, json.loads(meta)) for p, m, s, meta in query("SELECT path, mtime_ns, size, meta FROM files")}


def files_update(changed, removed):
    """Stores new/changed entries ({path: (mtime_ns, size, meta)}) and forgets removed paths, in one transaction."""
    if not changed and not removed:
        return
    with _lock:
        _conn.execute("BEGIN")
        try:
            _conn.executemany(
                "INSERT INTO files(path, mtime_ns, size, meta) VALUES(?, ?, ?, ?) "
                "ON CONFLICT(path) DO UPDATE SET mtime_ns = excluded.mtime_ns, size = excluded.size, meta = excluded.meta",
                [(p, m, s, json.dumps(meta)) for p, (m, s, meta) in changed.items()])
            _conn.executemany("DELETE FROM files WHERE path = ?", [(p,) for p in removed])
            _conn.execute("COMMIT")
        except Exception:
            _conn.execute("ROLLBACK")
            raise
