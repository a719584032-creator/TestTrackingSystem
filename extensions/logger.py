# extensions/logger.py
import os, sys, logging, json, uuid, time
from logging.handlers import RotatingFileHandler
from flask import g, request
from werkzeug.exceptions import HTTPException

_REQUEST_ID_KEY = "request_id"


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            data["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            data["user_id"] = record.user_id
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        from flask import has_request_context
        if has_request_context():
            record.request_id = getattr(g, _REQUEST_ID_KEY, "-")
        else:
            record.request_id = "-"
        return True


def _ensure_request_id():
    if not hasattr(g, _REQUEST_ID_KEY):
        setattr(g, _REQUEST_ID_KEY, uuid.uuid4().hex)
    return getattr(g, _REQUEST_ID_KEY)


def init_logger(app):
    cfg = app.config
    log_dir = cfg["LOG_DIR"]
    os.makedirs(log_dir, exist_ok=True)
    level = getattr(logging, cfg["LOG_LEVEL"].upper(), logging.INFO)

    root = logging.getLogger()
    # 避免重复添加
    if root.handlers:
        return

    root.setLevel(level)

    text_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(request_id)s | %(name)s | %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )
    json_fmt = JsonFormatter()

    def make_handler(filename, lvl=None):
        h = RotatingFileHandler(
            os.path.join(log_dir, filename),
            maxBytes=cfg["LOG_MAX_BYTES"],
            backupCount=cfg["LOG_BACKUP_COUNT"],
            encoding="utf-8"
        )
        h.setLevel(lvl or level)
        h.setFormatter(json_fmt if cfg["LOG_JSON"] else text_fmt)
        h.addFilter(RequestIdFilter())
        return h

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(json_fmt if cfg["LOG_JSON"] else text_fmt)
    console.addFilter(RequestIdFilter())

    root.addHandler(console)
    root.addHandler(make_handler("app.log"))
    err_handler = make_handler("error.log", logging.ERROR)
    root.addHandler(err_handler)

    # 降低 noisy 包
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.INFO)

    app.logger.info("Logger initialized")

    # 注册请求钩子（也可分离到 middleware 文件）
    @app.before_request
    def _before():
        g._req_start = time.time()
        _ensure_request_id()
        app.logger.info(f"REQ {request.method} {request.path} from {request.remote_addr}")

    @app.after_request
    def _after(resp):
        duration = (time.time() - getattr(g, "_req_start", time.time())) * 1000
        app.logger.info(f"RESP {request.method} {request.path} {resp.status_code} {duration:.1f}ms")
        return resp

    @app.errorhandler(Exception)
    def _err(e):
        if isinstance(e, HTTPException):
            code = e.code
            msg = e.description
        else:
            code = 500
            msg = "服务器内部错误"
            app.logger.exception("UNHANDLED EXCEPTION")
        from utils.response import json_response
        return json_response(code=code, message=msg), code
