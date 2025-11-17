# extensions/jwt.py
import time, json, base64, hmac, hashlib, uuid, os
from flask import current_app
from extensions.redis_client import get_redis


def _b64(data: bytes):
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def _b64json(obj):
    return _b64(json.dumps(obj, separators=(",", ":")).encode())


class TokenError(ValueError):
    pass


def create_token(user_id: int, username: str, role: str, pwdv: int, expires_seconds: int = 8 * 3600):
    secret = current_app.config["JWT_SECRET_KEY"].encode()
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "pwdv": pwdv,              # 新增
        "exp": now + expires_seconds,
        "iat": now,
        "jti": uuid.uuid4().hex
    }
    h_b = _b64json(header)
    p_b = _b64json(payload)
    signing = h_b + b"." + p_b
    sig = _b64(hmac.new(secret, signing, hashlib.sha256).digest())
    return (signing + b"." + sig).decode()


def _decode_segment(seg: str):
    pad = "=" * (-len(seg) % 4)
    return json.loads(base64.urlsafe_b64decode(seg + pad).decode())


def decode_token(token: str, check_revoked: bool = True):
    secret = current_app.config["JWT_SECRET_KEY"].encode()
    try:
        h_b, p_b, sig_b = token.split(".")
        signing = f"{h_b}.{p_b}".encode()
        expected = _b64(hmac.new(secret, signing, hashlib.sha256).digest()).decode()
        if not hmac.compare_digest(expected, sig_b):
            raise TokenError("签名不匹配")

        payload = _decode_segment(p_b)
        exp = payload.get("exp")
        if exp and time.time() > exp:
            raise TokenError("token已过期")

        if check_revoked:
            jti = payload.get("jti")
            if jti and is_token_revoked(jti):
                raise TokenError("token已失效")
        return payload
    except TokenError:
        raise
    except Exception:
        raise TokenError("token不合法")


def revoke_token(token: str):
    """
    解析 token -> jti+exp 写入 Redis 黑名单。
    幂等：解析失败或过期直接返回。
    """
    try:
        payload = decode_token(token, check_revoked=False)
    except TokenError:
        return
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return
    now = int(time.time())
    ttl = max(exp - now, 1)
    r = get_redis()
    r.setex(f"jwt:blk:{jti}", ttl, "1")


def is_token_revoked(jti: str) -> bool:
    r = get_redis()
    return bool(r.get(f"jwt:blk:{jti}"))
