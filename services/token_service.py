# services/token_service.py
from datetime import datetime
from flask import current_app
from repositories.token_repository import TokenRepository
from extensions.jwt import create_token, decode_token  # 你已有的工具


class TokenService:
    @staticmethod
    def revoke(token: str, ttl_seconds: int):
        if not token:
            return
        TokenRepository.blacklist(token, ttl_seconds=ttl_seconds)

    @staticmethod
    def issue(user):
        return create_token(user.id, user.username, user.role, user.password_version)
