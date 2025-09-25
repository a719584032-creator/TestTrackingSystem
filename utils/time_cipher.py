# -*- coding: utf-8 -*-
"""时间戳加/解密工具。

目前约定的规则：

* 前端会将毫秒级时间戳(UTC)与基于 SECRET_KEY 的 HMAC 签名拼接，
  形成 ``<timestamp_ms>.<signature>`` 的明文字符串；
* 明文再经过 URL Safe Base64 编码后作为接口参数传递；
* 后端收到参数后完成 Base64 解码与签名校验，最终还原出毫秒时间戳。

该实现旨在提供一个轻量的“加密”协议，防止时间戳被随意篡改。
如需更强的安全性，可替换为成熟的加密组件。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime
from typing import Optional

from flask import current_app

from utils.exceptions import BizError


def _decode_token(token: str) -> tuple[str, str]:
    try:
        decoded = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
    except Exception as exc:  # pragma: no cover - 捕获所有异常统一抛业务错误
        raise BizError("时间参数格式不正确", 400) from exc

    try:
        timestamp_part, signature = decoded.split(".", 1)
    except ValueError as exc:  # pragma: no cover - 捕获所有异常统一抛业务错误
        raise BizError("时间参数缺少签名", 400) from exc
    return timestamp_part, signature


def _validate_signature(timestamp_part: str, signature: str):
    secret_key = current_app.config.get("SECRET_KEY", "")
    expected_signature = hmac.new(
        secret_key.encode("utf-8"), timestamp_part.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        raise BizError("时间参数签名验证失败", 400)


def decode_encrypted_timestamp(token: str) -> datetime:
    """解密前端传递的时间戳并转换为 ``datetime``。

    :raises BizError: 当 token 校验失败或格式错误。
    """

    if not token:
        raise BizError("时间参数不能为空", 400)

    timestamp_part, signature = _decode_token(token)
    _validate_signature(timestamp_part, signature)

    try:
        millis = int(timestamp_part)
    except ValueError as exc:
        raise BizError("时间参数格式不正确", 400) from exc

    if millis < 0:
        raise BizError("时间参数不能为负数", 400)

    # 使用 UTC 时间，数据库字段存储 naive datetime（UTC）。
    return datetime.utcfromtimestamp(millis / 1000.0)


def decode_encrypted_timestamp_optional(token: Optional[str]) -> Optional[datetime]:
    if token is None:
        return None
    token = token.strip()
    if not token:
        return None
    return decode_encrypted_timestamp(token)

