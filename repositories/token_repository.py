# repositories/token_repository.py
import json
from datetime import datetime, timedelta
from typing import Optional
from extensions.redis_client import get_redis

BLACKLIST_PREFIX = "jwt:blacklist:"
REVOCATION_PREFIX = "jwt:revoked:"  # 备用


class TokenRepository:
    @staticmethod
    def blacklist(token: str, ttl_seconds: int):
        if not token:
            return
        r = get_redis()
        r.setex(BLACKLIST_PREFIX + token, ttl_seconds, "1")

    @staticmethod
    def is_blacklisted(token: str) -> bool:
        r = get_redis()
        return r.exists(BLACKLIST_PREFIX + token) == 1
