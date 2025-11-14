"""OTA 升级相关接口."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Optional

from flask import (
    Blueprint,
    abort,
    current_app,
    send_from_directory,
    url_for,
)

from utils.response import json_response


ota_bp = Blueprint("ota", __name__, url_prefix="/api/ota")


def _load_metadata() -> Optional[Dict[str, Any]]:
    meta_path = current_app.config.get("OTA_METADATA_FILE")
    if not meta_path or not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as fp:
            return json.load(fp)
    except json.JSONDecodeError as exc:
        current_app.logger.error("OTA metadata 文件解析失败 %s: %s", meta_path, exc)
        return None


def _get_package_dir() -> str:
    package_dir = current_app.config.get("OTA_PACKAGE_DIR")
    if not package_dir:
        package_dir = os.path.join(current_app.root_path, "ota_packages")
    os.makedirs(package_dir, exist_ok=True)
    return package_dir


def _safe_join(root: str, filename: str) -> Optional[str]:
    root_abs = os.path.abspath(root)
    target = os.path.abspath(os.path.join(root_abs, filename))
    if not target.startswith(root_abs + os.sep):
        return None
    return target


def _calculate_sha256(path: str) -> str:
    sha256 = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


@ota_bp.get("/latest")
def latest_release():
    metadata = _load_metadata()
    if not metadata:
        return json_response(code=404, message="暂无OTA版本信息")

    version = metadata.get("version")
    notes = metadata.get("notes", "")
    file_name = metadata.get("file_name")
    download_url = metadata.get("download_url") or None
    checksum = metadata.get("checksum") or None

    package_dir = _get_package_dir()

    if file_name:
        safe_path = _safe_join(package_dir, file_name)
        if safe_path and os.path.exists(safe_path):
            if not download_url:
                download_url = url_for(
                    "ota.download_package", filename=file_name, _external=True
                )
            if not checksum:
                checksum = _calculate_sha256(safe_path)
        else:
            current_app.logger.warning(
                "OTA 包文件 %s 在目录 %s 中不存在", file_name, package_dir
            )
    else:
        current_app.logger.warning("OTA metadata 没有 file_name 字段")

    if not version:
        return json_response(code=503, message="OTA 版本号未配置")
    if not download_url:
        return json_response(code=503, message="OTA 下载地址不可用")
    if not checksum:
        return json_response(code=503, message="OTA 校验码未配置")

    return json_response(
        data={
            "version": version,
            "notes": notes,
            "download_url": download_url,
            "checksum": checksum,
        }
    )


@ota_bp.get("/packages/<path:filename>")
def download_package(filename: str):
    package_dir = _get_package_dir()
    safe_path = _safe_join(package_dir, filename)
    if not safe_path or not os.path.exists(safe_path):
        abort(404)
    rel_path = os.path.relpath(safe_path, package_dir)
    return send_from_directory(package_dir, rel_path, as_attachment=True)
