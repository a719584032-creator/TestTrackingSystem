"""A tiny stub of the redis client used for offline unit testing."""

import time
from typing import Any, Dict, Optional, Tuple


class RedisStub:  # pragma: no cover - 占位实现
    def __init__(self, url: str):
        self.url = url
        self._store: Dict[str, Tuple[Any, Optional[float]]] = {}

    def get(self, name: str, *_args, **_kwargs):
        value_with_expiry = self._store.get(name)
        if value_with_expiry is None:
            return None
        value, expires_at = value_with_expiry
        if expires_at is not None and expires_at <= time.time():
            # 过期后移除并表现为不存在
            self._store.pop(name, None)
            return None
        return value

    def set(self, name: str, value: Any, *_args, **_kwargs):
        self._store[name] = (value, None)
        return True

    def setex(self, name: str, time_to_live: int, value: Any):
        expires_at = time.time() + int(time_to_live)
        self._store[name] = (value, expires_at)
        return True

    def close(self):  # pragma: no cover
        pass


def from_url(url: str, *_args, **_kwargs) -> RedisStub:  # pragma: no cover
    return RedisStub(url)
