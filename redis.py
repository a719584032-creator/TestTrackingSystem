"""A tiny stub of the redis client used for offline unit testing."""


class RedisStub:  # pragma: no cover - 占位实现
    def __init__(self, url: str):
        self.url = url

    def get(self, *_args, **_kwargs):
        return None

    def set(self, *_args, **_kwargs):
        return True

    def close(self):  # pragma: no cover
        pass


def from_url(url: str, *_args, **_kwargs) -> RedisStub:  # pragma: no cover
    return RedisStub(url)
