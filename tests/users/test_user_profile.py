import uuid
import pytest
import random


# 辅助函数：创建用户
def _create_user(api_client, username: str, password: str = "Test123!", role: str = "user"):
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


# 辅助函数：登录返回 token
def _login(base_url: str, timeout: int, username: str, password: str):
    from ..utils.api_client import APIClient
    c = APIClient(base_url, timeout)
    resp = c.request("POST", "/api/auth/login", json_data={"username": username, "password": password})
    assert resp.get("_http_status") == 200, f"登录失败: {resp}"
    return resp["data"]["token"]


# 辅助函数：构造带 token 的客户端
def _client_with_token(base_url: str, timeout: int, token: str):
    from ..utils.api_client import APIClient
    c = APIClient(base_url, timeout)
    c.set_token(token)
    return c


# 获取用户详情（通过列表检索）
def _find_user(api_client, username: str):
    resp = api_client.request(
        "GET",
        "/api/users/list",
        params={"keyword": username}  # 如果后端使用 search，请替换为 search
    )
    assert resp.get("_http_status") == 200, f"列表查询失败: {resp}"
    for item in resp["data"]["items"]:
        if item["username"] == username:
            return item
    return None


@pytest.fixture
def normal_user_client(config, api_client):
    """
    创建一个普通用户并返回 (user_id, username, client)
    """
    username = f"u_{uuid.uuid4().hex[:6]}"
    password = "Test123!"
    user_id = _create_user(api_client, username, password, role="user")
    token = _login(config["base_url"], config["timeout"], username, password)
    client = _client_with_token(config["base_url"], config["timeout"], token)
    return user_id, username, client


@pytest.fixture
def dept_admin_client(config, api_client):
    """
    创建一个部门管理员并返回 (user_id, username, client)
    """
    username = f"dept_{uuid.uuid4().hex[:6]}"
    password = "DeptAdm1!"
    user_id = _create_user(api_client, username, password, role="dept_admin")
    token = _login(config["base_url"], config["timeout"], username, password)
    client = _client_with_token(config["base_url"], config["timeout"], token)
    return user_id, username, client


@pytest.mark.integration
class TestUserProfile:

    def test_self_update_email(self, normal_user_client):
        user_id, username, client = normal_user_client
        new_email = f"{username}@example.com"
        resp = client.request(
            "PATCH",
            "/api/users/me/profile",
            json_data={"email": new_email}
        )
        assert resp.get("_http_status") == 200, f"自更新邮箱失败: {resp}"
        assert resp["data"]["email"] == new_email

    def test_self_update_phone_normalization(self, normal_user_client):
        user_id, username, client = normal_user_client

        phone_raw = "1380013" + str(random.randint(1000, 9999))
        resp = client.request(
            "PATCH",
            "/api/users/me/profile",
            json_data={"phone": phone_raw}
        )
        assert resp.get("_http_status") == 200, f"自更新手机号失败: {resp}"
        assert resp["data"]["phone"] == f"+86{phone_raw}", f"规范化失败: {resp['data']['phone']}"

    def test_self_update_invalid_email(self, normal_user_client):
        user_id, username, client = normal_user_client
        resp = client.request(
            "PATCH",
            "/api/users/me/profile",
            json_data={"email": "bad-email-format"}
        )
        assert resp.get("_http_status") == 400, f"应返回 400: {resp}"
        assert "邮箱" in resp.get("message", "")

    def test_self_update_invalid_phone(self, normal_user_client):
        user_id, username, client = normal_user_client
        resp = client.request(
            "PATCH",
            "/api/users/me/profile",
            json_data={"phone": "12345"}
        )
        assert resp.get("_http_status") == 400, f"应返回 400: {resp}"
        assert "手机号" in resp.get("message", "")

    def test_admin_updates_user_profile(self, api_client):
        """
        管理员更新普通用户的邮箱和手机号
        """
        target_username = f"target_{uuid.uuid4().hex[:6]}"
        target_id = _create_user(api_client, target_username, "Test123!", role="user")
        new_email = f"{target_username}@corp.com"
        new_phone = "1390013" + str(random.randint(1000, 9999))
        resp = api_client.request(
            "PATCH",
            f"/api/users/{target_id}/profile",
            json_data={"email": new_email, "phone": new_phone}
        )
        assert resp.get("_http_status") == 200, f"管理员更新失败: {resp}"
        assert resp["data"]["email"] == new_email
        assert resp["data"]["phone"] == f"+86{new_phone}"

    def test_dept_admin_cannot_update_admin_profile(self, dept_admin_client, config, api_client):
        """
        部门管理员更新系统管理员资料应 403
        """
        # 找到系统管理员 ID
        admin_info = _find_user(api_client, config["admin_username"])
        assert admin_info, "未找到系统管理员"
        admin_id = admin_info["id"]

        _, dept_username, dept_client = dept_admin_client
        resp = dept_client.request(
            "PATCH",
            f"/api/users/{admin_id}/profile",
            json_data={"email": f"{dept_username}@try.com"}
        )
        assert resp.get("_http_status") == 403, f"应拒绝部门管理员修改系统管理员资料: {resp}"

    def test_email_conflict(self, api_client):
        """
        两个用户，第二个更新成第一个的邮箱 -> 409
        """
        u1 = f"c1_{uuid.uuid4().hex[:6]}"
        u2 = f"c2_{uuid.uuid4().hex[:6]}"
        id1 = _create_user(api_client, u1, "Test123!")
        id2 = _create_user(api_client, u2, "Test123!")

        email1 = f"{u1}@ex.com"
        # 先给第一个设置邮箱
        r1 = api_client.request(
            "PATCH", f"/api/users/{id1}/profile",
            json_data={"email": email1}
        )
        assert r1.get("_http_status") == 200, f"预设邮箱失败: {r1}"

        # 第二个用户设置同邮箱
        r2 = api_client.request(
            "PATCH", f"/api/users/{id2}/profile",
            json_data={"email": email1}
        )
        # 后端定义 409 或 400，此处按 409
        assert r2.get("_http_status") in (409,), f"邮箱冲突未返回 409: {r2}"

    def test_phone_conflict(self, api_client):
        """
        两个用户，第二个更新成第一个的手机号 -> 409
        """
        u1 = f"p1_{uuid.uuid4().hex[:6]}"
        u2 = f"p2_{uuid.uuid4().hex[:6]}"
        id1 = _create_user(api_client, u1, "Test123!")
        id2 = _create_user(api_client, u2, "Test123!")

        phone = "1370013" + str(random.randint(1000, 9999))
        r1 = api_client.request(
            "PATCH", f"/api/users/{id1}/profile",
            json_data={"phone": phone}
        )
        assert r1.get("_http_status") == 200, f"预设手机号失败: {r1}"

        r2 = api_client.request(
            "PATCH", f"/api/users/{id2}/profile",
            json_data={"phone": phone}
        )
        assert r2.get("_http_status") in (409,), f"手机号冲突未返回 409: {r2}"

    def test_missing_fields(self, normal_user_client):
        user_id, username, client = normal_user_client
        resp = client.request(
            "PATCH",
            "/api/users/me/profile",
            json_data={}
        )
        assert resp.get("_http_status") == 400, f"缺少字段应 400: {resp}"

    def test_idempotent_update(self, normal_user_client):
        user_id, username, client = normal_user_client
        email = f"{username}@example.com"
        phone = "1381234" + str(random.randint(1000, 9999))
        first = client.request(
            "PATCH",
            "/api/users/me/profile",
            json_data={"email": email, "phone": phone}
        )
        assert first.get("_http_status") == 200, f"首次更新失败: {first}"
        second = client.request(
            "PATCH",
            "/api/users/me/profile",
            json_data={"email": email, "phone": phone}
        )
        assert second.get("_http_status") == 200, f"幂等更新失败: {second}"
        # 保持不变
        assert second["data"]["email"] == email
        assert second["data"]["phone"] == f"+86{phone}"

    def test_user_cannot_update_other_user(self, normal_user_client, config, api_client):
        """
        普通用户尝试修改他人资料 -> 403
        """
        # 创建第二个普通用户
        user2_name = f"other_{uuid.uuid4().hex[:6]}"
        user2_id = _create_user(api_client, user2_name, "Test123!", role="user")

        user1_id, user1_name, user1_client = normal_user_client
        resp = user1_client.request(
            "PATCH",
            f"/api/users/{user2_id}/profile",
            json_data={"email": f"{user2_name}@new.com"}
        )
        assert resp.get("_http_status") == 403, f"普通用户不应能改他人资料: {resp}"
