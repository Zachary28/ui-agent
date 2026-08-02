from __future__ import annotations
import json
import threading
import sqlite3
from pathlib import Path


class JsonCheckpoint:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def put(self, key, state):
        with self.lock:
            data = json.loads(self.path.read_text()) if self.path.exists() else {}
            data[key] = state
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get(self, key):
        if not self.path.exists():
            return None
        return json.loads(self.path.read_text()).get(key)


class SqliteCheckpoint:
    def __init__(self, path):
        self.connection = sqlite3.connect(str(path), check_same_thread=False)
        self.connection.execute("PRAGMA busy_timeout=5000")
        self.connection.execute("CREATE TABLE IF NOT EXISTS checkpoints (key TEXT PRIMARY KEY, state TEXT NOT NULL)")
        self.connection.commit()
        self.lock = threading.Lock()

    def put(self, key, state):
        with self.lock:
            self.connection.execute(
                "INSERT INTO checkpoints(key,state) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET state=excluded.state",
                (key, json.dumps(state)),
            )
            self.connection.commit()

    def get(self, key):
        row = self.connection.execute("SELECT state FROM checkpoints WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def close(self):
        self.connection.close()


class DurableWorkflow:
    def __init__(self, max_retries=2):
        self.max_retries = max_retries

    def execute(self, operation):
        for attempt in range(self.max_retries + 1):
            try:
                return operation()
            except Exception:
                if attempt >= self.max_retries:
                    raise
