import random

import pytest
import uuid


class TestUsers:
    """用户管理相关测试"""

    def test_create_user_success(self, api_client, test_user_data):
        """测试创建用户成功"""
        resp = api_client.request(
            "POST",
            "/api/users/create",
            json_data=test_user_data
        )

        assert resp.get("_http_status") == 200, f"创建用户失败: {resp}"
        assert "data" in resp, "响应中缺少data字段"

        # 验证返回的用户信息
        user_data = resp["data"]
        assert user_data["username"] == test_user_data["username"]
        assert user_data["role"] == test_user_data["role"]
        assert "id" in user_data

    def test_create_user_duplicate(self, api_client, test_user_data):
        """测试创建重复用户"""
        # 先创建一个用户
        api_client.request("POST", "/api/users/create", json_data=test_user_data)

        # 再次创建相同用户名的用户
        resp = api_client.request(
            "POST",
            "/api/users/create",
            json_data=test_user_data
        )

        assert resp.get("_http_status") == 409, "应该返回409冲突状态码"

    def test_create_email_duplicate(self, api_client):
        """测试创建重复邮箱用户"""
        suffix = uuid.uuid4().hex[:8]
        email = f"asdfg{random.randint(1000,9999)}@qq.com"
        test_user_data = {
            "username": f"testuser_{suffix}",
            "password": "Test123!",
            "email": email,
            "role": "user"
        }
        # 先创建一个用户
        api_client.request("POST", "/api/users/create", json_data=test_user_data)

        duplicate_email_data = test_user_data.copy()
        duplicate_email_data["username"] = f"testuser_{uuid.uuid4().hex[:8]}"
        # 再次创建相同邮箱的用户
        resp = api_client.request(
            "POST",
            "/api/users/create",
            json_data=duplicate_email_data
        )

        assert resp.get("_http_status") == 409, "应该返回409冲突状态码"


    def test_create_phone_duplicate(self, api_client):
        """测试创建重复手机用户"""
        suffix = uuid.uuid4().hex[:8]
        phone = f"1325555{random.randint(1000, 9999)}"
        test_user_data = {
            "username": f"testuser_{suffix}",
            "password": "Test123!",
            "phone": phone,
            "role": "user"
        }
        # 先创建一个用户
        api_client.request("POST", "/api/users/create", json_data=test_user_data)

        duplicate_email_data = test_user_data.copy()
        duplicate_email_data["username"] = f"testuser_{uuid.uuid4().hex[:8]}"
        # 再次创建相同手机的用户
        resp = api_client.request(
            "POST",
            "/api/users/create",
            json_data=duplicate_email_data
        )

        assert resp.get("_http_status") == 409, "应该返回409冲突状态码"

    def test_create_user_invalid_data(self, api_client):
        """测试创建用户时传入无效数据"""
        invalid_data = {
            "username": "",  # 空用户名
            "password": "123",  # 密码太短
            "role": "invalid_role"  # 无效角色
        }

        resp = api_client.request(
            "POST",
            "/api/users/create",
            json_data=invalid_data
        )

        assert resp.get("_http_status") == 400, "应该返回400错误请求状态码"

    def test_list_users_default(self, api_client):
        """测试获取用户列表 - 默认参数"""
        resp = api_client.request("GET", "/api/users/list")

        assert resp.get("_http_status") == 200, f"获取用户列表失败: {resp}"
        assert "data" in resp, "响应中缺少data字段"

        data = resp["data"]
        assert "total" in data, "缺少total字段"
        assert "items" in data, "缺少items字段"
        assert isinstance(data["items"], list), "items应该是列表"

    def test_list_users_with_pagination(self, api_client):
        """测试获取用户列表 - 带分页参数"""
        params = {"page": 1, "page_size": 5}
        resp = api_client.request("GET", "/api/users/list", params=params)

        assert resp.get("_http_status") == 200, f"获取用户列表失败: {resp}"

        data = resp["data"]
        assert len(data["items"]) <= 5, "返回的用户数量应该不超过page_size"

    def test_list_users_with_search(self, api_client, test_user_data):
        """测试获取用户列表 - 带搜索条件"""
        # 先创建一个测试用户
        api_client.request("POST", "/api/users/create", json_data=test_user_data)

        # 搜索该用户
        params = {"search": test_user_data["username"][:5]}
        resp = api_client.request("GET", "/api/users/list", params=params)

        assert resp.get("_http_status") == 200, f"搜索用户失败: {resp}"

        # 验证搜索结果
        items = resp["data"]["items"]
        found = any(item["username"] == test_user_data["username"] for item in items)
        assert found, f"未找到创建的用户: {test_user_data['username']}"

    def test_list_users_unauthorized(self, config):
        """测试未授权访问用户列表"""
        from ..utils.api_client import APIClient

        # 创建没有token的客户端
        client = APIClient(config["base_url"], config["timeout"])
        resp = client.request("GET", "/api/users/list", attach_token=False)

        assert resp.get("_http_status") == 401, "应该返回401未授权状态码"


@pytest.mark.integration
class TestUserIntegration:
    """用户相关集成测试"""

    def test_user_lifecycle(self, api_client):
        """测试用户完整生命周期"""
        # 生成唯一用户数据
        suffix = uuid.uuid4().hex[:8]
        user_data = {
            "username": f"lifecycle_user_{suffix}",
            "password": "Test123!",
            "role": "user"
        }

        # 1. 创建用户
        create_resp = api_client.request(
            "POST",
            "/api/users/create",
            json_data=user_data
        )
        assert create_resp.get("_http_status") == 200
        user_id = create_resp["data"]["id"]

        # 2. 验证用户出现在列表中
        list_resp = api_client.request(
            "GET",
            "/api/users/list",
            params={"search": user_data["username"]}
        )
        assert list_resp.get("_http_status") == 200

        found_user = None
        for item in list_resp["data"]["items"]:
            if item["id"] == user_id:
                found_user = item
                break

        assert found_user is not None, "新创建的用户未出现在列表中"
        assert found_user["username"] == user_data["username"]
        assert found_user["role"] == user_data["role"]
