# utils/password.py
import re
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app

UPPER = re.compile(r'[A-Z]')
LOWER = re.compile(r'[a-z]')
DIGIT = re.compile(r'\d')
SYMBOL = re.compile(r'[!@#$%^&*()_\-+=\[\]{};:\'",.<>/?\\|`~]')


def hash_password(plain: str) -> str:
    return generate_password_hash(plain)


def verify_password(hashed: str, plain: str) -> bool:
    return check_password_hash(hashed, plain)


def validate_password_policy(username: str, pwd: str) -> list[str]:
    cfg = current_app.config
    errs = []
    if len(pwd) < cfg.get("PASSWORD_MIN_LENGTH", 12):
        errs.append(f"长度至少 {cfg.get('PASSWORD_MIN_LENGTH', 12)}")
    if not UPPER.search(pwd):
        errs.append("需包含大写字母")
    if not LOWER.search(pwd):
        errs.append("需包含小写字母")
    if not DIGIT.search(pwd):
        errs.append("需包含数字")
    if cfg.get("REQUIRE_COMPLEX_SYMBOL", True) and not SYMBOL.search(pwd):
        errs.append("需包含符号")
    if username.lower() in pwd.lower():
        errs.append("不能包含用户名")
    return errs
