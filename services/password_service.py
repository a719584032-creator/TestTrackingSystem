# services/password_service.py
from flask import current_app
from repositories.user_repository import UserRepository
from services.policy_service import validate_password_policy
from services.rate_limit_service import PasswordChangeRateLimiter
from services.token_service import TokenService
from utils.exceptions import BizError
from utils.password import verify_password, hash_password
from extensions.database import db


class PasswordService:

    @staticmethod
    def change_password(user, old_password: str, new_password: str, confirm_password: str, current_token: str | None):
        cfg = current_app.config
        fail_limit = cfg.get("PASSWORD_CHANGE_FAIL_LIMIT", 5)
        block_seconds = cfg.get("PASSWORD_CHANGE_BLOCK_SECONDS", 900)
        history_size = cfg.get("PASSWORD_HISTORY_SIZE", 5)
        blacklist_on_change = cfg.get("BLACKLIST_ON_PASSWORD_CHANGE", True)

        # 基本校验
        if not old_password or not new_password or not confirm_password:
            raise BizError("参数不能为空")
        if new_password != confirm_password:
            raise BizError("两次新密码不一致")

        # 速率限制
        limiter = PasswordChangeRateLimiter(user.id, fail_limit, block_seconds)
        limiter.ensure_not_blocked()

        # 验证旧密码
        if not verify_password(user.password_hash, old_password):
            limiter.record_failure()
            print("出现校验错误")
            raise BizError("旧密码不正确")

        # 策略
        policy_errors = validate_password_policy(user.username, new_password)
        if policy_errors:
            limiter.record_failure()
            raise BizError("; ".join(policy_errors))

        # 不得与当前一致
        if verify_password(user.password_hash, new_password):
            limiter.record_failure()
            raise BizError("新密码不能与旧密码相同")

        # 历史检查
        if history_size > 0:
            histories = UserRepository.get_recent_password_histories(user.id, history_size)
            for h in histories:
                if verify_password(h.password_hash, new_password):
                    limiter.record_failure()
                    raise BizError("新密码不得与最近使用的旧密码重复")

        # 生成新 hash 与事务更新
        new_hash = hash_password(new_password)
        try:
            UserRepository.add_password_history(user.id, user.password_hash)
            UserRepository.update_password(user, new_hash)
        except Exception as e:
            db.session.rollback()
            raise BizError(f"密码更新失败: {e}")

        # 历史滚动（单独：避免主事务失败影响核心更新）
        if history_size > 0:
            UserRepository.trim_password_histories(user.id, history_size)

        # 清空失败计数
        limiter.clear()

        # 黑名单当前 token
        if blacklist_on_change and current_token:
            # token 的 TTL 通常为原 JWT 剩余时间，此处简单用 block_seconds 或另行计算
            TokenService.revoke(current_token, ttl_seconds=block_seconds)

        # 签发新 token
        new_token = TokenService.issue(user)

        return {
            "message": "密码修改成功",
            "password_version": user.password_version,
            "token": new_token
        }
