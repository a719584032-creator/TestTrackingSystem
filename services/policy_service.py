# services/policy_service.py
from typing import List
from flask import current_app
from utils.password import verify_password


def validate_password_policy(username: str, new_password: str) -> list[str]:
    cfg = current_app.config
    min_len = cfg.get("PASSWORD_MIN_LENGTH", 12)
    require_symbol = cfg.get("REQUIRE_COMPLEX_SYMBOL", True)

    errors = []
    if len(new_password) < min_len:
        errors.append(f"密码长度至少 {min_len} 位")
    # if require_symbol and not any(c in "!@#$%^&*()-_=+[]{};:,<.>/?\\|" for c in new_password):
    #     errors.append("需包含至少一个符号")
    if not any(c.isdigit() for c in new_password):
        errors.append("需包含数字")
    if not any(c.islower() for c in new_password):
        errors.append("需包含小写字母")
    # if not any(c.isupper() for c in new_password):
    #     errors.append("需包含大写字母")
    # if username.lower() in new_password.lower():
    #     errors.append("密码不能包含用户名")
    return errors
