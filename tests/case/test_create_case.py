import uuid
import pytest
from typing import Dict, Any, List

# 基础路径常量（按你的实际路由调整）
TEST_CASE_BASE = "/api/test-cases"
USER_CREATE_API = "/api/users/create"

# 固定部门 ID
FIXED_DEPARTMENT_ID = 13


# ---------- 工具函数 ----------
def _rand(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _get_department_id() -> int:
    """
    返回写死的部门ID。
    确保：
      - 该部门在数据库中已存在
      - admin_token 对应用户已属于该部门（否则 create 会被权限拦截）
    """
    return FIXED_DEPARTMENT_ID


def _build_steps() -> List[Dict[str, Any]]:
    return [
        {
            "no": 1,
            "action": "打开登录页面",
            "keyword": "打开",
            "note": "确保页面加载完成",
            "expected": "显示登录表单"
        },
        {
            "no": 2,
            "action": "输入用户名",
            "keyword": "输入",
            "note": "输入正确的用户名",
            "expected": "用户名输入框显示输入内容"
        },
        {
            "no": 3,
            "action": "输入密码",
            "keyword": "输入",
            "note": "输入正确的密码",
            "expected": "密码以掩码形式显示"
        },
        {
            "no": 4,
            "action": "点击登录按钮",
            "keyword": "点击",
            "note": "点击登录按钮提交表单",
            "expected": "跳转到首页"
        }
    ]


def _create_test_case(api_client, department_id: int, expect_success: bool = True, **overrides) -> Dict[str, Any]:
    payload = {
        "department_id": department_id,
        "title": _rand("登录用例"),
        "preconditions": "浏览器已打开",
          # 由于后端会校验 steps 中 action 字段，这里默认填充完整 steps
        "steps": _build_steps(),
        "expected_result": "登录成功后进入首页",
        "keywords": ["登录", "正向"],
        "priority": "P2",
        "case_type": "functional"
    }
    payload.update(overrides)
    resp = api_client.request("POST", TEST_CASE_BASE, json_data=payload)
    if expect_success:
        assert resp.get("_http_status") == 200, f"创建用例失败: {resp}"
        return resp.get("data", {})
    return resp


# ---------- 测试开始 ----------
def test_create_test_case_success(api_client):
    dept_id = _get_department_id()
    data = _create_test_case(api_client, dept_id)
    assert "id" in data
    assert data["department_id"] == dept_id
    assert data["priority"] == "P2"
    assert data["status"] == "active"


def test_create_test_case_missing_title(api_client):
    dept_id = _get_department_id()
    payload = {
        "department_id": dept_id,
        "preconditions": "前置",
        "steps": _build_steps(),
        "expected_result": "OK",
    }
    resp = api_client.request("POST", TEST_CASE_BASE, json_data=payload)
    assert resp.get("_http_status") == 400
    assert "用例标题不能为空" in resp.get("message", "")


def test_create_test_case_invalid_priority(api_client):
    dept_id = _get_department_id()
    payload = {
        "department_id": dept_id,
        "title": _rand("错误优先级"),
        "steps": _build_steps(),
        "priority": "P9"
    }
    resp = api_client.request("POST", TEST_CASE_BASE, json_data=payload)
    assert resp.get("_http_status") == 400
    assert "优先级" in resp.get("message", "")


def test_get_test_case_detail(api_client):
    dept_id = _get_department_id()
    created = _create_test_case(api_client, dept_id)
    case_id = created["id"]
    resp = api_client.request("GET", f"{TEST_CASE_BASE}/{case_id}")
    assert resp.get("_http_status") == 200
    data = resp.get("data")
    assert data["id"] == case_id
    assert data["steps"][0]["action"].startswith("打开登录页面")
    assert data["department_id"] == dept_id


def test_update_test_case(api_client):
    dept_id = _get_department_id()
    created = _create_test_case(api_client, dept_id)
    case_id = created["id"]

    new_title = _rand("更新后的标题")
    new_keywords = ["登录", "回归"]
    update_payload = {
        "title": new_title,
        "keywords": new_keywords,
        "priority": "P1",
        "status": "active",
        "case_type": "functional",
        "steps": _build_steps() + [{
            "no": 5,
            "action": "点击退出按钮",
            "keyword": "点击",
            "note": "退出测试",
            "expected": "返回登录页"
        }]
    }
    resp = api_client.request("PUT", f"{TEST_CASE_BASE}/{case_id}", json_data=update_payload)
    assert resp.get("_http_status") == 200, f"更新失败: {resp}"

    detail = api_client.request("GET", f"{TEST_CASE_BASE}/{case_id}")
    assert detail.get("_http_status") == 200
    data = detail["data"]
    assert data["title"] == new_title
    assert data["priority"] == "P1"
    assert len(data["steps"]) == 5


def test_update_test_case_invalid_priority(api_client):
    dept_id = _get_department_id()
    created = _create_test_case(api_client, dept_id)
    case_id = created["id"]
    resp = api_client.request("PUT", f"{TEST_CASE_BASE}/{case_id}", json_data={"priority": "PX"})
    assert resp.get("_http_status") == 400
    assert "优先级" in resp.get("message", "")


def test_list_test_cases_filter_and_pagination(api_client):
    dept_id = _get_department_id()
    # 创建若干（注意：由于同一个部门可能已有历史数据，断言用 >=）
    for _ in range(3):
        _create_test_case(api_client, dept_id, priority="P2")
    for _ in range(2):
        _create_test_case(api_client, dept_id, priority="P1")

    resp = api_client.request(
        "GET",
        f"{TEST_CASE_BASE}/department/{dept_id}",
        params={
            "priority": "P1",
            "page": 1,
            "page_size": 10,
            "order_by": "created_at",
            "order_desc": "true"
        }
    )
    assert resp.get("_http_status") == 200
    data = resp.get("data", {})
    assert data["total"] >= 2
    for item in data["items"]:
        assert item["priority"] == "P1"


def test_delete_test_case(api_client):
    dept_id = _get_department_id()
    created = _create_test_case(api_client, dept_id)
    case_id = created["id"]

    resp = api_client.request("DELETE", f"{TEST_CASE_BASE}/{case_id}")
    assert resp.get("_http_status") == 200

    detail = api_client.request("GET", f"{TEST_CASE_BASE}/{case_id}")
    assert detail.get("_http_status") in (404, 400, 500), f"预期已删除，但返回: {detail}"


def test_batch_delete_test_cases(api_client):
    dept_id = _get_department_id()
    ids = []
    for _ in range(3):
        created = _create_test_case(api_client, dept_id)
        ids.append(created["id"])

    resp = api_client.request(
        "DELETE",
        f"{TEST_CASE_BASE}/batch",
        json_data={"case_ids": ids, "department_id": dept_id}
    )
    assert resp.get("_http_status") == 200
    msg = resp.get("message", "")
    assert "删除" in msg

    detail = api_client.request("GET", f"{TEST_CASE_BASE}/{ids[0]}")
    assert detail.get("_http_status") in (404, 400, 500)


# ---------- 权限相关 ----------
@pytest.fixture
def normal_user_token(config, api_client):
    """创建一个普通用户并登录，返回其 token"""
    username = _rand("user")
    password = "User123!"
    create_resp = api_client.request(
        "POST",
        USER_CREATE_API,
        json_data={"username": username, "password": password, "role": "user"}
    )
    assert create_resp.get("_http_status") in (200, 201), f"创建用户失败: {create_resp}"

    login_resp = api_client.request(
        "POST",
        "/api/auth/login",
        json_data={"username": username, "password": password}
    )
    assert login_resp.get("_http_status") == 200, f"登录失败: {login_resp}"
    token = login_resp.get("data", {}).get("token")
    assert token, "普通用户未获取 token"
    return token


def test_permission_user_not_in_department(api_client, normal_user_token):
    dept_id = _get_department_id()
    # 使用普通用户 token 尝试创建（假设该用户不在部门 13，会被拒绝）
    from tests.utils.api_client import APIClient
    user_client = APIClient(api_client.base_url, api_client.timeout)
    user_client.set_token(normal_user_token)

    payload = {
        "department_id": dept_id,
        "title": _rand("未授权创建"),
        "steps": _build_steps()
    }
    resp = user_client.request("POST", TEST_CASE_BASE, json_data=payload)
    assert resp.get("_http_status") in (403, 401), f"应拒绝未授权部门访问: {resp}"


# ---------- 步骤格式校验 ----------
def test_create_test_case_step_missing_action(api_client):
    dept_id = _get_department_id()
    bad_steps = _build_steps()
    bad_steps[0].pop("action")
    payload = {
        "department_id": dept_id,
        "title": _rand("步骤缺action"),
        "steps": bad_steps
    }
    resp = api_client.request("POST", TEST_CASE_BASE, json_data=payload)
    assert resp.get("_http_status") == 400
    assert "步骤" in resp.get("message", "")


def test_create_test_case_step_action_empty(api_client):
    dept_id = _get_department_id()
    bad_steps = _build_steps()
    bad_steps[1]["action"] = "   "
    payload = {
        "department_id": dept_id,
        "title": _rand("步骤action空白"),
        "steps": bad_steps
    }
    resp = api_client.request("POST", TEST_CASE_BASE, json_data=payload)
    assert resp.get("_http_status") == 400
    assert "步骤" in resp.get("message", "")


def test_get_test_case_history(api_client):
    dept_id = _get_department_id()
    created = _create_test_case(api_client, dept_id)
    case_id = created["id"]

    new_title = _rand("更新后的标题")
    new_keywords = ["登录", "回归"]
    update_payload = {
        "title": new_title,
        "keywords": new_keywords,
        "priority": "P1",
        "status": "active",
        "case_type": "functional",
        "steps": _build_steps() + [{
            "no": 5,
            "action": "点击退出按钮",
            "keyword": "点击",
            "note": "退出测试",
            "expected": "返回登录页"
        }]
    }
    resp = api_client.request("PUT", f"{TEST_CASE_BASE}/{case_id}", json_data=update_payload)
    assert resp.get("_http_status") == 200, f"更新失败: {resp}"

    detail = api_client.request("GET", f"{TEST_CASE_BASE}/{case_id}")
    assert detail.get("_http_status") == 200
    data = detail["data"]
    assert data["title"] == new_title
    assert data["priority"] == "P1"
    assert len(data["steps"]) == 5

    resp = api_client.request("GET", f"{TEST_CASE_BASE}/{case_id}/history")
    assert resp.get("_http_status") == 200, f"获取变更历史失败: {resp}"


def test_delete_test_case_restore(api_client):
    dept_id = _get_department_id()
    created = _create_test_case(api_client, dept_id)
    case_id = created["id"]

    resp = api_client.request("DELETE", f"{TEST_CASE_BASE}/{case_id}")
    assert resp.get("_http_status") == 200

    detail = api_client.request("GET", f"{TEST_CASE_BASE}/{case_id}")
    assert detail.get("_http_status") in (404, 400, 500), f"预期已删除，但返回: {detail}"

    restore = api_client.request("POST", f"{TEST_CASE_BASE}/{case_id}/restore")
    assert restore.get("message") == "恢复成功", f"预期已恢复，但返回: {restore}"