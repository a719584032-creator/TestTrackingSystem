import re

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
# 国内简化（11 位），或可扩展
CN_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")  # E.164: 最长15位

def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))

def normalize_phone(phone: str) -> str:
    """
    处理逻辑：
      1. 去空格、去 - 与 ()
      2. 若以 + 开头并满足 E.164 => 返回
      3. 若全为数字且长度为 11 且符合国内手机号规则 => 加前缀 +86
      4. 其它情况判定失败
    """
    if phone is None:
        return None
    raw = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not raw:
        return None
    if raw.startswith("+"):
        return raw if E164_RE.match(raw) else None
    if CN_PHONE_RE.match(raw):
        return "+86" + raw
    return None

def validate_phone(phone: str) -> bool:
    if phone is None:
        return True
    return bool(E164_RE.match(phone))