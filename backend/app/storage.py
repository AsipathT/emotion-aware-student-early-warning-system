"""Tiny JSON-file storage. Each file holds one list of records."""
import json
import os
import tempfile
import threading
from pathlib import Path


class JsonStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()

    def read(self) -> list:
        with self._lock:
            if not self.path.exists():
                return []
            with open(self.path, encoding="utf-8") as fh:
                return json.load(fh)

    def write(self, records: list) -> None:
        """Write to a temp file first, then swap it in, so a crash never leaves half a file."""
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(records, fh, indent=2, ensure_ascii=False)
                os.replace(tmp, self.path)
            except BaseException:
                if os.path.exists(tmp):
                    os.remove(tmp)
                raise

    def append(self, record: dict) -> dict:
        with self._lock:
            records = self.read()
            records.append(record)
            self.write(records)
            return record

    def update(self, record_id: str, changes: dict) -> dict | None:
        with self._lock:
            records = self.read()
            for record in records:
                if record.get("id") == record_id:
                    record.update(changes)
                    self.write(records)
                    return record
            return None
