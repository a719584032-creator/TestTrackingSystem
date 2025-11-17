"""OTA 升级相关接口."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Iterable, Optional, Tuple

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


def _iter_releases(metadata: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    if not isinstance(metadata, dict):
        return
    releases = metadata.get("releases")
    if isinstance(releases, list):
        for item in releases:
            if isinstance(item, dict):
                yield item
        return
    if isinstance(metadata, dict):
        yield metadata


def _resolve_release(
    metadata: Optional[Dict[str, Any]], version: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    if not metadata or not isinstance(metadata, dict):
        return None
    releases = list(_iter_releases(metadata))
    if not releases:
        return None
    if version:
        for item in releases:
            if item.get("version") == version:
                return item
        return None
    latest_version = metadata.get("latest")
    if latest_version:
        for item in releases:
            if item.get("version") == latest_version:
                return item
    return releases[0]


def _build_release_payload(
    release: Dict[str, Any],
    *,
    include_file_name: bool = False,
    require_package: bool = True,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    version = release.get("version")
    file_name = release.get("file_name")
    notes = release.get("notes", "")

    if not version:
        return None, "OTA 版本号未配置"
    if not file_name:
        return None, "OTA 包文件未配置"

    package_dir = _get_package_dir()
    safe_path = _safe_join(package_dir, file_name)
    if not safe_path or not os.path.exists(safe_path):
        message = f"OTA 包文件 {file_name} 不存在"
        current_app.logger.warning(message)
        if require_package:
            return None, message
        payload = {
            "version": version,
            "notes": notes,
            "download_url": None,
            "checksum": None,
        }
        if include_file_name:
            payload["file_name"] = file_name
        return payload, None

    download_url = url_for("ota.download_package", filename=file_name, _external=True)
    checksum = _calculate_sha256(safe_path)

    payload = {
        "version": version,
        "notes": notes,
        "download_url": download_url,
        "checksum": checksum,
    }
    if include_file_name:
        payload["file_name"] = file_name
    return payload, None


@ota_bp.get("/latest")
def latest_release():
    metadata = _load_metadata()
    if not metadata:
        return json_response(code=404, message="暂无OTA版本信息")

    release = _resolve_release(metadata)
    if not release:
        return json_response(code=503, message="OTA 版本信息未配置")

    payload, error = _build_release_payload(release, require_package=True)
    if error:
        return json_response(code=503, message=error)

    return json_response(data=payload)


@ota_bp.get("/packages/<path:filename>")
def download_package(filename: str):
    package_dir = _get_package_dir()
    safe_path = _safe_join(package_dir, filename)
    if not safe_path or not os.path.exists(safe_path):
        abort(404)
    rel_path = os.path.relpath(safe_path, package_dir)
    return send_from_directory(package_dir, rel_path, as_attachment=True)


@ota_bp.get("/history")
def release_history():
    metadata = _load_metadata()
    if not metadata:
        return json_response(data={"items": []})

    items = []
    for release in _iter_releases(metadata):
        payload, _ = _build_release_payload(
            release, include_file_name=True, require_package=False
        )
        if payload:
            items.append(payload)

    return json_response(data={"items": items})
