# -*- coding: utf-8 -*-
"""附件访问接口."""

from __future__ import annotations

import os

from flask import Blueprint, abort, current_app, send_file


attachment_bp = Blueprint("attachment", __name__, url_prefix="/api/attachments")


@attachment_bp.get("/<path:file_path>")
def serve_attachment(file_path: str):
    """根据存储路径返回附件内容."""

    storage_dir = current_app.config.get("ATTACHMENT_STORAGE_DIR")
    if not storage_dir:
        abort(404)

    normalized_path = os.path.normpath(file_path).lstrip(os.sep)
    storage_root = os.path.abspath(storage_dir)
    target_path = os.path.abspath(os.path.join(storage_root, normalized_path))

    # 防止路径穿越访问其他目录
    storage_root_with_sep = storage_root + os.sep
    if not target_path.startswith(storage_root_with_sep) and target_path != storage_root:
        abort(404)
    if not os.path.exists(target_path):
        abort(404)

    return send_file(target_path, conditional=True)
