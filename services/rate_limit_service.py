# services/rate_limit_service.py
from repositories.rate_limit_repository import RateLimitRepository
from utils.exceptions import BizError


class PasswordChangeRateLimiter:
    def __init__(self, user_id: int, fail_limit: int, block_seconds: int):
        self.key = f"pwdchg:fail:{user_id}"
        self.fail_limit = fail_limit
        self.block_seconds = block_seconds

    def ensure_not_blocked(self):
        count = RateLimitRepository.get_fail_count(self.key)
        if count >= self.fail_limit:
            ttl = RateLimitRepository.get_ttl(self.key)
            raise BizError(message=f"尝试过多，请 {ttl} 秒后重试")

    def record_failure(self):
        new_count = RateLimitRepository.incr_fail(self.key, self.block_seconds)
        return new_count

    def clear(self):
        RateLimitRepository.clear(self.key)
