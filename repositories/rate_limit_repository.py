# repositories/rate_limit_repository.py
from extensions.redis_client import get_redis


class RateLimitRepository:
    @staticmethod
    def get_fail_count(key: str) -> int:
        r = get_redis()
        v = r.get(key)
        return int(v) if v else 0

    @staticmethod
    def incr_fail(key: str, block_seconds: int) -> int:
        r = get_redis()
        v = r.incr(key)
        if v == 1:
            r.expire(key, block_seconds)
        return v

    @staticmethod
    def get_ttl(key: str) -> int:
        r = get_redis()
        return r.ttl(key)

    @staticmethod
    def clear(key: str):
        r = get_redis()
        r.delete(key)
