import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from app.business import DomainIssue

SCHEMA = """CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY, report TEXT NOT NULL, created TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING', revision INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '', reviewed TEXT
);
CREATE TABLE IF NOT EXISTS releases (
    id TEXT PRIMARY KEY, seq INTEGER NOT NULL UNIQUE, parent TEXT,
    status TEXT NOT NULL, report TEXT NOT NULL, created TEXT NOT NULL
);"""


class Store:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=15)) as db, db:
            db.row_factory = sqlite3.Row
            db.executescript(SCHEMA)
            yield db

    def register(self, run_id, report):
        with self.connect() as db:
            db.execute(
                "INSERT INTO runs(id,report,created) VALUES (?,?,?) ON CONFLICT(id) DO NOTHING",
                (
                    run_id,
                    json.dumps(report, ensure_ascii=False),
                    report["manifest"]["created"],
                ),
            )
        return self.load(run_id)

    def load(self, run_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise DomainIssue("RUN_NOT_FOUND")
        result = dict(row)
        result["report"] = json.loads(result["report"])
        return result

    def list(self):
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,created,status,revision,note FROM runs ORDER BY created DESC,id LIMIT 50"
                )
            ]

    def revise(self, run_id, revision, status, note, now):
        with self.connect() as db:
            cursor = db.execute(
                "UPDATE runs SET status=?,note=?,reviewed=?,revision=revision+1 WHERE id=? AND revision=?",
                (status, note, now, run_id, revision),
            )
            if cursor.rowcount != 1:
                raise DomainIssue("STALE_REVIEW")
        return self.load(run_id)

    @staticmethod
    def release_row(row):
        result = dict(row)
        result["report"] = json.loads(result["report"])
        return result

    def current_release(self):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM releases WHERE status='PUBLISHED' ORDER BY seq DESC LIMIT 1"
            ).fetchone()
        return self.release_row(row) if row else None

    def find_release(self, release_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT id,seq,parent,status,created FROM releases WHERE id=?",
                (release_id,),
            ).fetchone()
        return dict(row) if row else None

    def load_release(self, release_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM releases WHERE id=?", (release_id,)
            ).fetchone()
        if row is None:
            raise DomainIssue("RELEASE_NOT_FOUND")
        return self.release_row(row)

    def list_releases(self):
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,seq,parent,status,created FROM releases ORDER BY seq DESC,id LIMIT 50"
                )
            ]

    def register_release(self, release_id, parent, status, report):
        with self.connect() as db:
            db.execute(
                "INSERT INTO releases(id,seq,parent,status,report,created) "
                "SELECT ?, COALESCE(MAX(seq),0)+1, ?,?,?,? FROM releases WHERE true "
                "ON CONFLICT(id) DO NOTHING",
                (
                    release_id,
                    parent,
                    status,
                    json.dumps(report, ensure_ascii=False),
                    report["manifest"]["created"],
                ),
            )
        return self.load_release(release_id)
