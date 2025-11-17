"""
修改密码相关测试
依赖现有 conftest.py 中:
  - api_client  (管理员身份)
  - config
说明：
  - 若你的实际路径与常量不同，请调整路径常量
  - 若无 /api/users/me 接口，可删除相关调用
"""
import uuid
import pytest

# ==== 接口路径常量（按需修改） ====
CREATE_USER_PATH = "/api/users/create"
LOGIN_PATH = "/api/auth/login"
CHANGE_PASSWORD_PATH = "/api/auth/change-password"
ME_PATH = "/api/departments/1"   # 受保护接口，用于检测 token 是否有效


# ==== 工具函数 ====
def _unique_username(prefix: str = "ut_pwd") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _admin_create_user(admin_client, username: str, password: str, role: str = "user") -> dict:
    """使用管理员客户端创建用户"""
    resp = admin_client.request(
        "POST",
        CREATE_USER_PATH,
        json_data={
            "username": username,
            "password": password,
            "role": role
        }
    )
    assert resp.get("_http_status") == 200, f"创建用户失败: {resp}"
    return resp["data"]


def _login_user(base_url: str, timeout: int, username: str, password: str):
    """普通用户登录，返回 (token, 全量响应, client实例)"""
    from ..utils.api_client import APIClient
    client = APIClient(base_url, timeout)
    resp = client.request(
        "POST",
        LOGIN_PATH,
        json_data={"username": username, "password": password}
    )
    assert resp.get("_http_status") == 200, f"用户登录失败: {resp}"
    token = resp.get("data", {}).get("token")
    assert token, f"用户登录响应缺少 token: {resp}"
    client.set_token(token)
    return token, resp, client


class TestPasswordChange:
    """修改密码用例集合"""

    def test_change_password_success(self, api_client, config):
        """
        场景：正常修改密码
        验证：
          1. 返回 200
          2. 返回新 token（与旧不同）
          3. （若返回 password_version）应递增
          4. 旧密码无法再登录
          5. 新密码可登录
          6. （可选）旧 token 是否失效（取决于是否启用黑名单 / 版本校验）
        """
        username = _unique_username()
        old_password = "Abcdefg123!"
        _admin_create_user(api_client, username, old_password)

        old_token, login_resp, user_client = _login_user(
            config["base_url"],
            config["timeout"],
            username,
            old_password
        )
        old_version = login_resp["data"].get("password_version")

        new_password = "Abcdefg123!@#X"
        change_resp = user_client.request(
            "POST",
            CHANGE_PASSWORD_PATH,
            json_data={
                "old_password": old_password,
                "new_password": new_password,
                "confirm_password": new_password
            }
        )
        assert change_resp.get("_http_status") == 200, f"修改密码失败: {change_resp}"
        data = change_resp.get("data", {})
        assert "token" in data, "响应应包含新 token"
        assert data["token"] != old_token, "新旧 token 不应相同"
        if old_version is not None:
            assert data.get("password_version") == old_version + 1, "password_version 未递增"

        new_token = data["token"]

        # 旧 token 访问受保护接口（如启用 token 失效策略应失败）
        from ..utils.api_client import APIClient
        old_token_client = APIClient(config["base_url"], config["timeout"])
        old_token_client.set_token(old_token)
        me_old = old_token_client.request("GET", ME_PATH)
        if me_old.get("_http_status") not in (200, 401, 403):
            pytest.fail(f"旧 token 访问响应异常: {me_old}")

        # 旧密码再次登录应失败
        relog_old = user_client.request(
            "POST",
            LOGIN_PATH,
            json_data={"username": username, "password": old_password}
        )
        assert relog_old.get("_http_status") in (400, 401), f"旧密码仍可登录: {relog_old}"

        # 新密码登录应成功
        new_token_login, _, _ = _login_user(
            config["base_url"],
            config["timeout"],
            username,
            new_password
        )
        assert new_token_login != old_token, "新登录 token 仍与旧 token 相同"

    def test_change_password_wrong_old_password(self, api_client, config):
        """
        场景：旧密码错误
        期望：400/401
        """
        username = _unique_username()
        password = "Abcdefg123!@#"
        _admin_create_user(api_client, username, password)
        _, _, user_client = _login_user(config["base_url"], config["timeout"], username, password)

        resp = user_client.request(
            "POST",
            CHANGE_PASSWORD_PATH,
            json_data={
                "old_password": "WrongOld123!@#",
                "new_password": "Abcdefg123!@#Z",
                "confirm_password": "Abcdefg123!@#Z"
            }
        )
        assert resp.get("_http_status") in (400, 401), f"旧密码错误应失败: {resp}"
        msg = resp.get("message", "")
        assert any(k in msg for k in ("旧密码", "不正确", "认证", "错误")), f"提示不明确: {msg}"

    def test_change_password_same_as_old(self, api_client, config):
        """
        场景：新密码与旧密码相同
        期望：400
        """
        username = _unique_username()
        password = "Abcdefg123!@#"
        _admin_create_user(api_client, username, password)
        _, _, user_client = _login_user(config["base_url"], config["timeout"], username, password)

        resp = user_client.request(
            "POST",
            CHANGE_PASSWORD_PATH,
            json_data={
                "old_password": password,
                "new_password": password,
                "confirm_password": password
            }
        )
        assert resp.get("_http_status") == 400, f"相同密码应失败: {resp}"
        assert any(k in resp.get("message", "") for k in ("相同", "不能", "不可", "不同")), "缺少明确提示"

    def test_change_password_policy_fail(self, api_client, config):
        """
        场景：新密码不满足复杂度策略
        期望：400
        """
        username = _unique_username()
        password = "Abcdefg123!@#"
        _admin_create_user(api_client, username, password)
        _, _, user_client = _login_user(config["base_url"], config["timeout"], username, password)

        bad_new = "Ab1!"  # 过短 / 不符合策略
        resp = user_client.request(
            "POST",
            CHANGE_PASSWORD_PATH,
            json_data={
                "old_password": password,
                "new_password": bad_new,
                "confirm_password": bad_new
            }
        )
        assert resp.get("_http_status") == 400, f"策略不满足应失败: {resp}"
        assert any(k in resp.get("message", "") for k in ("长度", "策略", "至少", "复杂", "不满足")), "提示不明确"

    def test_change_password_mismatch_confirm(self, api_client, config):
        """
        场景：确认密码不一致
        期望：400
        """
        username = _unique_username()
        password = "Abcdefg123!@#"
        _admin_create_user(api_client, username, password)
        _, _, user_client = _login_user(config["base_url"], config["timeout"], username, password)

        resp = user_client.request(
            "POST",
            CHANGE_PASSWORD_PATH,
            json_data={
                "old_password": password,
                "new_password": "Abcdefg123!@#X",
                "confirm_password": "Abcdefg123!@#Y"
            }
        )
        assert resp.get("_http_status") == 400, f"确认密码不一致应失败: {resp}"
        assert any(k in resp.get("message", "") for k in ("一致", "不匹配", "相同")), "提示不明确"

    def test_change_password_reuse_history(self, api_client, config):
        """
        场景：历史密码复用限制
        步骤：
          1. 使用 old_password 登录
          2. old -> new 修改成功
          3. （可选）验证旧 token 已失效（如果启用了修改后失效策略）
          4. 使用 new_password 重新登录，拿新 token
          5. 尝试 new -> old，期望：
             - 若启用历史密码限制并且 history_size > 0，则应失败
             - 否则可能成功（宽松处理）
        """
        username = _unique_username()
        old_password = "Abcdefg123!@#"
        new_password = "Abcdefg123!@#Q"

        _admin_create_user(api_client, username, old_password)

        base_url = config["base_url"]
        timeout = config["timeout"]
        history_size = config.get("PASSWORD_HISTORY_SIZE", 0)
        blacklist_on_change = config.get("BLACKLIST_ON_PASSWORD_CHANGE", True)

        # 初次登录，拿旧 token
        _, _, user_client = _login_user(base_url, timeout, username, old_password)

        # 第一次修改：old -> new
        first = user_client.request(
            "POST",
            CHANGE_PASSWORD_PATH,
            json_data={
                "old_password": old_password,
                "new_password": new_password,
                "confirm_password": new_password
            }
        )
        assert first.get("_http_status") == 200, f"第一次修改失败: {first}"

        # （可选）验证旧 token 已失效（如果你的后端策略是立即拉黑）


        # 重新登录（使用新密码），以获取新 token
        _, _, user_client_fresh = _login_user(base_url, timeout, username, new_password)

        # 第二次尝试复用旧密码：new -> old
        second = user_client_fresh.request(
            "POST",
            CHANGE_PASSWORD_PATH,
            json_data={
                "old_password": new_password,
                "new_password": old_password,
                "confirm_password": old_password
            }
        )

        # 断言逻辑：
        # 如果启用了历史密码限制（history_size > 0），那么旧密码应在受保护范围内 => 应失败
        # （假设实现是禁止最近 N 次密码；并且 old_password 仍在记录窗口）
        if history_size and history_size > 0:
            assert second.get("_http_status") == 400, f"历史密码复用应被禁止，但得到: {second}"
            # 信息里包含一些关键提示词，适配中/英文
            msg = second.get("message", "")
            assert any(kw in msg for kw in ("历史", "最近", "重复", "使用过", "history", "reuse")), f"提示不明确: {msg}"
        else:
            # 策略未启用 => 允许成功（或后端仍然禁止也行，取决于你的默认策略）
            if second.get("_http_status") == 200:
                print("历史密码复用未被限制（history_size=0 或未启用策略）")
            else:
                # 如果后端即使未配置也禁止，可接受；给出提示
                print("后端在未配置 history_size 的情况下仍禁止复用，状态:", second.get("_http_status"), second)

# ==== 可根据需要增加：连续错误触发锁定 / 频率限制测试 ====