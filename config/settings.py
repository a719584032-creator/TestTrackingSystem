# config/settings.py
import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))  # 自动加载环境变量


def _as_bool(val, default=False):
    if val is None:
        return default
    return str(val).lower() in ("1", "true", "yes", "on")


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret-key")
    REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

    # AWS 配置
    AWS_USER_ID = os.getenv("AWS_USER_ID")
    AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
    AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
    AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL")
    AWS_REGION_NAME = os.getenv("AWS_REGION_NAME")
    AWS_SIGNATURE_VERSION = os.getenv("AWS_SIGNATURE_VERSION")

    # 日志相关
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR = os.getenv("LOG_DIR", "./logs")
    LOG_JSON = os.getenv("LOG_JSON", "1") == "1"  # 是否 JSON 格式
    LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", 5 * 1024 * 1024))
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 5))
    APP_NAME = os.getenv("APP_NAME", "test-tracking-system")
    ATTACHMENT_STORAGE_DIR = os.getenv(
        "ATTACHMENT_STORAGE_DIR", os.path.join(BASE_DIR, "storage")
    )

    # 默认管理员（首次启动自动创建，可选）
    ADMIN_INIT_USERNAME = os.getenv("ADMIN_INIT_USERNAME", "admin")
    ADMIN_INIT_PASSWORD = os.getenv("ADMIN_INIT_PASSWORD", "Admin123!")
    ADMIN_INIT_EMAIL = os.getenv("ADMIN_INIT_EMAIL", "admin@example.com")

    # ========= 密码策略 & 修改密码相关 =========
    # 最小长度
    PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", 8))
    # 历史避免重复数量
    PASSWORD_HISTORY_SIZE = int(os.getenv("PASSWORD_HISTORY_SIZE", 5))
    # 修改密码失败尝试上限
    PASSWORD_CHANGE_FAIL_LIMIT = int(os.getenv("PASSWORD_CHANGE_FAIL_LIMIT", 5))
    # 达到上限后封禁秒数
    PASSWORD_CHANGE_BLOCK_SECONDS = int(os.getenv("PASSWORD_CHANGE_BLOCK_SECONDS", 900))
    # 是否必须包含符号
    REQUIRE_COMPLEX_SYMBOL = _as_bool(os.getenv("REQUIRE_COMPLEX_SYMBOL", "1"), False)
    # 修改密码后是否将当前 token 拉入黑名单（双保险）
    BLACKLIST_ON_PASSWORD_CHANGE = _as_bool(os.getenv("BLACKLIST_ON_PASSWORD_CHANGE", "1"), True)
    # 默认重置密码
    DEFAULT_RESET_PASSWORD = os.getenv("DEFAULT_RESET_PASSWORD", "password123")

    # =========================================


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv("DEV_DATABASE_URI")


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI")


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URI", "sqlite:///:memory:")


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config(config_name):
    return config_map.get(config_name, DevelopmentConfig)
