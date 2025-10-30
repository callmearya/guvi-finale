import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Optional

from app.config import CACHE_DIR


class JsonCache:
    """Simple JSON-based cache to survive intermittent connectivity."""

    def __init__(self, namespace: str, ttl_seconds: int = 3 * 3600) -> None:
        self.cache_dir = CACHE_DIR / namespace
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    def _key_path(self, key: str) -> Path:
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", key)[:60]
        prefix = cleaned or "cache"
        return self.cache_dir / f"{prefix}_{digest}.json"

    def get(self, key: str) -> Optional[Any]:
        path = self._key_path(key)
        if not path.exists():
            return None

        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            return None

        expires_at = payload.get("expires_at", 0)
        if expires_at and expires_at < time.time():
            return None
        return payload.get("value")

    def set(self, key: str, value: Any, override_ttl: Optional[int] = None) -> None:
        ttl = override_ttl or self.ttl_seconds
        payload = {
            "value": value,
            "expires_at": int(time.time()) + ttl if ttl else None,
        }
        path = self._key_path(key)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
