# extensions/redis_client.py
import os
import redis

_redis_client = None

def get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    _redis_client = redis.from_url(url)
    return _redis_client
