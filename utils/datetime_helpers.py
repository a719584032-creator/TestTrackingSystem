# -*- coding: utf-8 -*-
"""Datetime helpers for timezone conversions.

当前系统所有存储在数据库中的 ``datetime`` 均视为 UTC（无时区信息）。
为了在接口层统一返回东八区(北京时间)的时间字符串，这里提供
几个轻量的转换工具。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

BEIJING_TZ = timezone(timedelta(hours=8))


def _ensure_utc(dt: datetime) -> datetime:
    """将给定 ``datetime`` 统一转换为带 UTC 时区的对象。"""

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_beijing_time(dt: datetime) -> datetime:
    """将 ``datetime`` 转换为北京时间(东八区)。"""

    return _ensure_utc(dt).astimezone(BEIJING_TZ)


def datetime_to_beijing_iso(dt: Optional[datetime]) -> Optional[str]:
    """将 ``datetime`` 格式化为北京时间 ISO 字符串。

    :param dt: 需要转换的时间; ``None`` 时直接返回 ``None``。
    :return: 带 ``+08:00`` 时区偏移的 ISO 8601 格式字符串。
    """

    if dt is None:
        return None
    return to_beijing_time(dt).isoformat()

