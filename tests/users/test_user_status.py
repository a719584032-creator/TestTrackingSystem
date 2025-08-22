# 在你的测试文件（例如 test_users.py 或原 TestUserIntegration 所在文件）中追加如下代码。
# 如果你希望保持分离，可新建 test_user_status.py 并复用 conftest 提供的 fixture。

import uuid
import pytest


# ---------- 可选帮助函数 ----------
def _create_user(api_client, username: str, password: str, role: str = "user"):
    resp = api_client.request(
        "POST",
        "/api/users/create",
        json_data={
            "username": username,
            "password": password,
            "role": role
        }
    )
    assert resp.get("_http_status") in (200, 201), f"创建用户失败: {resp}"
    return resp["data"]["id"]


def _login(base_url: str, timeout: int, username: str, password: str):
    from ..utils.api_client import APIClient
    client = APIClient(base_url, timeout)
    resp = client.request("POST", "/api/auth/login", json_data={
        "username": username,
        "password": password
    })
    assert resp.get("_http_status") == 200, f"登录失败: {resp}"
    return resp["data"]["token"]


# ---------- 新增 fixture：部门管理员 token ----------
@pytest.fixture
def dept_admin_token(config, api_client):
    # 1. 由管理员创建一个部门管理员账号
    suffix = uuid.uuid4().hex[:6]
    username = f"dept_admin_{suffix}"
    password = "DeptAdm1!"
    create_resp = api_client.request(
        "POST",
        "/api/users/create",
        json_data={
            "username": username,
            "password": password,
            "role": "dept_admin"
        }
    )
    assert create_resp.get("_http_status") in (200, 201), f"创建部门管理员失败: {create_resp}"

    # 2. 登录获取 token
    token = _login(config["base_url"], config["timeout"], username, password)
    return token


@pytest.mark.integration
class TestUserStatus:

    def test_user_enable_disable_flow(self, api_client):
        """
        场景：
          1. 创建普通用户
          2. 禁用
          3. 再次禁用（幂等）
          4. 启用
          5. 再次启用（幂等）
        """
        username = f"status_user_{uuid.uuid4().hex[:6]}"
        password = "Test123!"
        user_id = _create_user(api_client, username, password, "user")

        # 禁用
        disable_resp = api_client.request(
            "PATCH",
            f"/api/users/{user_id}/status",
            json_data={"active": False}
        )
        assert disable_resp.get("_http_status") == 200, f"禁用失败: {disable_resp}"
        assert disable_resp["data"]["active"] is False

        # 再次禁用（幂等）
        disable_again = api_client.request(
            "PATCH",
            f"/api/users/{user_id}/status",
            json_data={"active": False}
        )
        assert disable_again.get("_http_status") == 200, f"第二次禁用失败: {disable_again}"
        assert disable_again["data"]["active"] is False

        # 启用
        enable_resp = api_client.request(
            "PATCH",
            f"/api/users/{user_id}/status",
            json_data={"active": True}
        )
        assert enable_resp.get("_http_status") == 200, f"启用失败: {enable_resp}"
        assert enable_resp["data"]["active"] is True

        # 再次启用（幂等）
        enable_again = api_client.request(
            "PATCH",
            f"/api/users/{user_id}/status",
            json_data={"active": True}
        )
        assert enable_again.get("_http_status") == 200
        assert enable_again["data"]["active"] is True

    def test_self_disable_forbidden(self, api_client, config):
        """
        管理员尝试禁用自己：应失败（Service 中先触发“不能禁用自己”）。
        """
        # 获取当前默认管理员信息（需要列表接口中能搜索/过滤）
        # 如果 list 接口使用 keyword 参数，这里需保持一致。
        list_resp = api_client.request(
            "GET",
            "/api/users/list",
            params={"keyword": config["admin_username"]}
        )
        assert list_resp.get("_http_status") == 200
        target = None
        for item in list_resp["data"]["items"]:
            if item["username"] == config["admin_username"]:
                target = item
                break
        assert target, "未找到默认管理员"
        admin_id = target["id"]

        # 尝试禁用
        disable_resp = api_client.request(
            "PATCH",
            f"/api/users/{admin_id}/status",
            json_data={"active": False}
        )
        assert disable_resp.get("_http_status") == 400, f"应禁止自我禁用: {disable_resp}"
        assert "不能禁用自己" in disable_resp.get("message", "")

    def test_dept_admin_cannot_disable_admin(self, api_client, dept_admin_token, config):
        """
        部门管理员尝试禁用系统管理员：403
        """
        # 用部门管理员 token 构造一个独立 client
        from ..utils.api_client import APIClient
        dept_client = APIClient(config["base_url"], config["timeout"])
        dept_client.set_token(dept_admin_token)

        # 找到系统管理员
        list_resp = dept_client.request(
            "GET",
            "/api/users/list",
            params={"keyword": config["admin_username"]}
        )
        assert list_resp.get("_http_status") == 200
        admin_id = None
        for item in list_resp["data"]["items"]:
            if item["username"] == config["admin_username"]:
                admin_id = item["id"]
                break
        assert admin_id, "部门管理员视角未找到系统管理员"

        # 尝试禁用
        resp = dept_client.request(
            "PATCH",
            f"/api/users/{admin_id}/status",
            json_data={"active": False}
        )
        assert resp.get("_http_status") == 403, f"部门管理员不应能禁用管理员: {resp}"
        assert "无权操作" in resp.get("message", "")

    def test_invalid_active_param(self, api_client):
        """
        active 不是布尔值时应 400
        """
        username = f"invalid_active_{uuid.uuid4().hex[:6]}"
        user_id = _create_user(api_client, username, "Test123!", "user")

        resp = api_client.request(
            "PATCH",
            f"/api/users/{user_id}/status",
            json_data={"active": "false"}   # 错误：字符串而非布尔
        )
        assert resp.get("_http_status") == 400, f"应返回 400: {resp}"
        assert "布尔" in resp.get("message", "")

