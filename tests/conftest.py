import os
import json
import pytest
import uuid
import requests
from typing import Dict, Any, Optional


@pytest.fixture(scope="session")
def config():
    """全局配置"""
    return {
        "base_url": os.environ.get("API_BASE_URL", "http://127.0.0.1"),
        "admin_username": os.environ.get("ADMIN_USERNAME", "admin"),
        "admin_password": os.environ.get("ADMIN_PASSWORD", "admin123"),
        "timeout": 10
    }


@pytest.fixture(scope="session")
def admin_token(config):
    """管理员登录获取token - 会话级别，只执行一次"""
    from .utils.api_client import APIClient

    client = APIClient(config["base_url"], config["timeout"])

    print(f"\n>>> 管理员登录: {config['admin_username']}")
    payload = {
        "username": config["admin_username"],
        "password": config["admin_password"]
    }

    resp = client.request("POST", "/api/auth/login", json_data=payload)

    assert resp.get("_http_status") == 200, f"登录失败: {resp}"

    token = resp.get("data", {}).get("token")
    assert token, "登录响应中未找到token"

    print(f"✓ 管理员登录成功")
    return token


@pytest.fixture
def api_client(config, admin_token):
    """API客户端实例 - 每个测试函数都会创建新实例"""
    from .utils.api_client import APIClient

    client = APIClient(config["base_url"], config["timeout"])
    client.set_token(admin_token)
    return client


@pytest.fixture
def test_user_data():
    """测试用户数据"""
    import uuid
    suffix = uuid.uuid4().hex[:8]
    return {
        "username": f"testuser_{suffix}",
        "password": "Test123!",
        "role": "user"
    }


@pytest.fixture
def test_department_data():
    """测试部门数据"""
    import uuid
    suffix = uuid.uuid4().hex[:8]
    return {
        "name": f"研发中心_{suffix}",
        "code": f"RND_{suffix}",
        "description": "自动化测试部门"
    }


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