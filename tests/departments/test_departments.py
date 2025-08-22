import pytest
import uuid


class TestDepartments:
    """部门管理相关测试"""

    def test_create_department_success(self, api_client, test_department_data):
        """测试创建部门成功"""
        resp = api_client.request(
            "POST",
            "/api/departments",
            json_data=test_department_data
        )

        assert resp.get("_http_status") == 200, f"创建部门失败: {resp}"
        assert "data" in resp, "响应中缺少data字段"

        dept_data = resp["data"]
        assert dept_data["name"] == test_department_data["name"]
        assert dept_data["code"] == test_department_data["code"]
        assert "id" in dept_data

    def test_create_department_duplicate_code(self, api_client, test_department_data):
        """测试创建重复编码的部门"""
        # 先创建一个部门
        api_client.request("POST", "/api/departments", json_data=test_department_data)

        # 创建相同编码的部门
        duplicate_data = test_department_data.copy()
        duplicate_data["name"] = f"{duplicate_data['name']}_duplicate"

        resp = api_client.request("POST", "/api/departments", json_data=duplicate_data)

        assert resp.get("_http_status") == 400, "应该返回400冲突状态码"

    def test_list_departments_default(self, api_client):
        """测试获取部门列表 - 默认参数"""
        resp = api_client.request("GET", "/api/departments")

        assert resp.get("_http_status") == 200, f"获取部门列表失败: {resp}"
        assert "data" in resp, "响应中缺少data字段"

        data = resp["data"]['items']
        assert isinstance(data, list), "部门列表应该是数组"

    def test_list_departments_with_search(self, api_client, test_department_data):
        """测试获取部门列表 - 带搜索条件"""
        # 先创建一个测试部门
        create_resp = api_client.request("POST", "/api/departments", json_data=test_department_data)
        assert create_resp.get("_http_status") == 200

        # 搜索该部门
        params = {"keyword": test_department_data["name"][:3], "page": 1, "page_size": 10}
        resp = api_client.request("GET", "/api/departments", params=params)

        assert resp.get("_http_status") == 200, f"搜索部门失败: {resp}"

    def test_get_department_detail(self, api_client, test_department_data):
        """测试获取部门详情"""
        # 先创建一个部门
        create_resp = api_client.request("POST", "/api/departments", json_data=test_department_data)
        assert create_resp.get("_http_status") == 200

        dept_id = create_resp["data"]["id"]

        # 获取部门详情
        resp = api_client.request("GET", f"/api/departments/{dept_id}")

        assert resp.get("_http_status") == 200, f"获取部门详情失败: {resp}"
        assert "data" in resp

        dept_data = resp["data"]
        assert dept_data["id"] == dept_id
        assert dept_data["name"] == test_department_data["name"]

    def test_get_department_detail_with_members(self, api_client, test_department_data):
        """测试获取部门详情 - 包含成员信息"""
        # 先创建一个部门
        create_resp = api_client.request("POST", "/api/departments", json_data=test_department_data)
        assert create_resp.get("_http_status") == 200

        dept_id = create_resp["data"]["id"]

        # 获取部门详情（包含成员）
        params = {"with_members": 1}
        resp = api_client.request("GET", f"/api/departments/{dept_id}", params=params)

        assert resp.get("_http_status") == 200, f"获取部门详情失败: {resp}"

    def test_update_department(self, api_client, test_department_data):
        """测试更新部门信息"""
        # 先创建一个部门
        create_resp = api_client.request("POST", "/api/departments", json_data=test_department_data)
        assert create_resp.get("_http_status") == 200

        dept_id = create_resp["data"]["id"]

        # 更新部门信息
        update_data = {
            "description": "更新后的描述 - pytest测试",
            "status": "active"
        }

        resp = api_client.request("PUT", f"/api/departments/{dept_id}", json_data=update_data)

        assert resp.get("_http_status") == 200, f"更新部门失败: {resp}"

        # 验证更新结果
        detail_resp = api_client.request("GET", f"/api/departments/{dept_id}")
        assert detail_resp.get("_http_status") == 200

        updated_dept = detail_resp["data"]
        assert updated_dept["description"] == update_data["description"]

    def test_delete_department_soft(self, api_client, test_department_data):
        """测试软删除部门"""
        # 先创建一个部门
        create_resp = api_client.request("POST", "/api/departments", json_data=test_department_data)
        assert create_resp.get("_http_status") == 200

        dept_id = create_resp["data"]["id"]

        # 软删除部门
        params = {"hard": 0}
        resp = api_client.request("DELETE", f"/api/departments/{dept_id}", params=params)

        assert resp.get("_http_status") == 200, f"删除部门失败: {resp}"

    def test_get_nonexistent_department(self, api_client):
        """测试获取不存在的部门"""
        resp = api_client.request("GET", "/api/departments/99999999")
        assert resp.get("_http_status") == 404, "应该返回404未找到状态码"


class TestDepartmentMembers:
    """部门成员相关测试"""

    @pytest.fixture
    def department_with_user(self, api_client, test_department_data, test_user_data):
        """创建部门和用户的夹具"""
        # 创建部门
        dept_resp = api_client.request("POST", "/api/departments", json_data=test_department_data)
        assert dept_resp.get("_http_status") == 200
        dept_id = dept_resp["data"]["id"]

        # 创建用户
        user_resp = api_client.request("POST", "/api/users/create", json_data=test_user_data)
        assert user_resp.get("_http_status") == 200
        user_id = user_resp["data"]["id"]

        return {"dept_id": dept_id, "user_id": user_id}

    def test_add_department_member(self, api_client, department_with_user):
        """测试添加部门成员"""
        dept_id = department_with_user["dept_id"]
        user_id = department_with_user["user_id"]

        member_data = {
            "user_id": user_id,
            "role": "dept_admin",
            "upsert": True
        }

        resp = api_client.request(
            "POST",
            f"/api/departments/{dept_id}/members",
            json_data=member_data
        )

        assert resp.get("_http_status") == 200, f"添加部门成员失败: {resp}"
        assert "data" in resp

        member_info = resp["data"]
        assert "id" in member_info
        return member_info["id"]  # 返回成员ID供其他测试使用

    def test_list_department_members(self, api_client, department_with_user):
        """测试获取部门成员列表"""
        dept_id = department_with_user["dept_id"]

        # 先添加一个成员
        self.test_add_department_member(api_client, department_with_user)

        # 获取成员列表
        params = {"role": "dept_admin"}
        resp = api_client.request("GET", f"/api/departments/{dept_id}/members", params=params)

        assert resp.get("_http_status") == 200, f"获取部门成员列表失败: {resp}"

    def test_update_member_role(self, api_client, department_with_user):
        """测试修改成员角色"""
        dept_id = department_with_user["dept_id"]

        # 先添加成员
        member_id = self.test_add_department_member(api_client, department_with_user)

        if member_id:
            # 修改成员角色
            update_data = {"role": "dept_viewer"}
            resp = api_client.request("PATCH", f"/api/departments/{member_id}", json_data=update_data)

            assert resp.get("_http_status") == 200, f"修改成员角色失败: {resp}"

    def test_remove_department_member(self, api_client, department_with_user):
        """测试移除部门成员"""
        # 先添加成员
        member_id = self.test_add_department_member(api_client, department_with_user)

        if member_id:
            # 移除成员
            resp = api_client.request("DELETE", f"/api/departments/{member_id}")

            assert resp.get("_http_status") == 200, f"移除部门成员失败: {resp}"


@pytest.mark.integration
class TestDepartmentIntegration:
    """部门相关集成测试"""

    def test_department_full_lifecycle(self, api_client):
        """测试部门完整生命周期"""
        # 生成唯一数据
        suffix = uuid.uuid4().hex[:8]
        dept_data = {
            "name": f"集成测试部门_{suffix}",
            "code": f"INT_{suffix}",
            "description": "集成测试部门"
        }

        # 1. 创建部门
        create_resp = api_client.request("POST", "/api/departments", json_data=dept_data)
        assert create_resp.get("_http_status") == 200
        dept_id = create_resp["data"]["id"]

        # 2. 获取部门详情
        detail_resp = api_client.request("GET", f"/api/departments/{dept_id}")
        assert detail_resp.get("_http_status") == 200
        assert detail_resp["data"]["name"] == dept_data["name"]

        # 3. 更新部门
        update_data = {"description": "更新后的集成测试部门"}
        update_resp = api_client.request("PUT", f"/api/departments/{dept_id}", json_data=update_data)
        assert update_resp.get("_http_status") == 200

        # 4. 验证更新
        updated_detail = api_client.request("GET", f"/api/departments/{dept_id}")
        assert updated_detail["data"]["description"] == update_data["description"]

        # 5. 软删除部门
        delete_resp = api_client.request("DELETE", f"/api/departments/{dept_id}", params={"hard": 0})
        assert delete_resp.get("_http_status") == 200
