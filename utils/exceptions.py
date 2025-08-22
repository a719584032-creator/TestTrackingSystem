# utils/exceptions.py
from typing import Any, Optional
from werkzeug.exceptions import HTTPException


class BizError(HTTPException):
    code: int  # HTTP 状态码
    message: str  # 业务提示
    data: Optional[Any]  # 附加数据

    def __init__(self, message: str = "业务异常", code: int = 400, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(description=message)
