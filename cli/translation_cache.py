from __future__ import annotations

import json
import hashlib
import threading
from pathlib import Path


class TranslationCache:
    def __init__(self, run_dir: str | Path | None, language: str) -> None:
        self._path: Path | None = None
        self._data: dict[str, str] = {}
        self._lock = threading.RLock()
        if not run_dir:
            return
        root = Path(run_dir)
        self._path = root / "translated" / f"{language}.json"
        if self._path.exists():
            try:
                payload = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    self._data = {str(k): str(v) for k, v in payload.items()}
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                self._data = {}

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> str | None:
        with self._lock:
            return self._data.get(self._key(text))

    def all(self) -> dict[str, str]:
        with self._lock:
            return dict(self._data)

    def set(self, text: str, translated: str) -> None:
        key = self._key(text)
        with self._lock:
            if self._data.get(key) == translated:
                return
            self._data[key] = translated
            if self._path is None:
                return
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
