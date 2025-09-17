"""A lightweight stub of the :mod:`requests` package used in unit tests.

本仓库的单元测试仅需导入 `requests.Session` 与 `requests.RequestException`
类型即可完成模块加载。为了避免在离线环境中安装第三方依赖，这里提供
一个最小可用的替身实现：

- ``Session.request`` 会抛出 ``RequestException``，提示不可用。
- ``Response`` 类仅用于类型注解，占位即可。
"""


class RequestException(RuntimeError):
    """Placeholder exception mimicking requests.RequestException."""


class Response:  # pragma: no cover - 仅占位
    def __init__(self, status_code: int = 0, text: str = "", headers: dict | None = None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}

    def json(self):  # pragma: no cover - 仅占位
        raise ValueError("No JSON payload")


class Session:  # pragma: no cover - 仅占位
    def request(self, *args, **kwargs):
        raise RequestException("requests stub does not support network operations")
