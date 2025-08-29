import os
import json
import requests
from typing import Optional, Dict, Any

# 配置
BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin123!")
NEW_USER_USERNAME = os.environ.get("NEW_USER_USERNAME", "tester1")
NEW_USER_PASSWORD = os.environ.get("NEW_USER_PASSWORD", "Test123!")
NEW_USER_ROLE = os.environ.get("NEW_USER_ROLE", "user")

TIMEOUT = 10


def print_request_response(method: str, url: str, headers: dict = None,
                           json_data: dict = None, response: requests.Response = None):
    """打印请求和响应的详细信息"""
    print(f"\n{'=' * 60}")
    print(f"请求方法: {method}")
    print(f"请求URL: {url}")

    if headers:
        print(f"请求头: {json.dumps(headers, ensure_ascii=False, indent=2)}")

    if json_data:
        print(f"请求参数: {json.dumps(json_data, ensure_ascii=False, indent=2)}")

    if response:
        print(f"响应状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")

        try:
            response_json = response.json()
            print(f"响应内容: {json.dumps(response_json, ensure_ascii=False, indent=2)}")
        except:
            print(f"响应内容: {response.text}")
    print(f"{'=' * 60}")


def api_request(method: str, path: str, token: Optional[str] = None,
                json_data: Optional[Dict] = None) -> Dict[str, Any]:
    """统一的API请求方法"""
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json_data,
            timeout=TIMEOUT
        )

        # 打印请求响应信息
        print_request_response(method, url, headers, json_data, response)

        # 尝试解析JSON响应
        try:
            result = response.json()
            result["_http_status"] = response.status_code
            return result
        except:
            return {
                "_http_status": response.status_code,
                "_raw_text": response.text
            }

    except requests.RequestException as e:
        print_request_response(method, url, headers, json_data)
        print(f"请求异常: {e}")
        raise


def login(username: str, password: str) -> str:
    """用户登录"""
    print(f"\n>>> 开始登录用户: {username}")

    payload = {"username": username, "password": password}
    resp = api_request("POST", "/api/auth/login", json_data=payload)

    if resp.get("_http_status") == 200:
        token = resp.get("data", {}).get("token")
        if token:
            print(f"✓ 登录成功，获取到token")
            return token
        else:
            print("✗ 登录失败：响应中未找到token")
            raise Exception("登录失败：未找到token")
    else:
        print(f"✗ 登录失败：状态码 {resp.get('_http_status')}")
        print(resp)
        # raise Exception("登录失败")


def create_user(token: str, username: str, password: str, role: str):
    """创建用户"""
    print(f"\n>>> 开始创建用户: {username}")

    payload = {"username": username, "password": password, "role": role}
    resp = api_request("POST", "/api/users/create", token=token, json_data=payload)

    status = resp.get("_http_status")
    if status == 201:
        print(f"✓ 用户创建成功")
    elif status == 409:
        print(f"⚠ 用户已存在")
    else:
        print(f"✗ 用户创建失败：状态码 {status}")


def list_users(token: str, page: int = 1, page_size: int = 10):
    """获取用户列表"""
    print(f"\n>>> 开始获取用户列表")

    path = f"/api/users/list?page={page}&page_size={page_size}"
    resp = api_request("GET", path, token=token)

    if resp.get("_http_status") == 200:
        data = resp.get("data", {})
        total = data.get("total", 0)
        items = data.get("items", [])
        print(f"✓ 获取用户列表成功，共 {total} 个用户，当前页 {len(items)} 个")
    else:
        print(f"✗ 获取用户列表失败：状态码 {resp.get('_http_status')}")


def main():
    """主函数"""
    print(f"开始API测试")
    print(f"服务器地址: {BASE_URL}")

    try:
        # 1. 管理员登录
        token = login(ADMIN_USERNAME, ADMIN_PASSWORD)

        # 2. 创建新用户
        create_user(token, NEW_USER_USERNAME, NEW_USER_PASSWORD, NEW_USER_ROLE)

        # 3. 获取用户列表
        list_users(token, page=1, page_size=10)

        print(f"\n>>> 所有测试完成 ✓")

    except Exception as e:
        print(f"\n>>> 测试失败: {e}")
        return False

    return True


if __name__ == "__main__":
    # success = main()
    # exit(0 if success else 1)

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEsInVzZXJuYW1lIjoiYWRtaW4iLCJyb2xlIjoiYWRtaW4iLCJwd2R2IjozLCJleHAiOjE3NTU4NTk4NTUsImlhdCI6MTc1NTgzMTA1NSwianRpIjoiMzYwYTRjNDdkNGFkNGM2OGIxZjZiYzg5YWUwY2YwYzIifQ.W9Va7G3U_nezJbekSVRrmYsbcGMB2j_dJs-YJBi1M6k"
    }
    data = {
        "username": "ut_pwd_b8fcc943",
        "password": "Abcdefg123!@#X"
    }
    # resp = requests.post(url='http://127.0.0.1/api/auth/logout', headers=headers)
    # resp = requests.post(url='http://127.0.0.1/api/auth/login', json=data)
    resp = requests.get(url='http://127.0.0.1/api/departments?page=1&page_size=20', headers=headers)
    print(resp.status_code)
    print(resp.json())
    case = {
        "department_id": 1,
        "title": "用户登录功能测试",
        "preconditions": "1. 用户已注册\n2. 网络连接正常",
        "steps": [
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
        ],
        "expected_result": "用户成功登录系统，跳转到首页",
        "keywords": ["登录", "用户认证", "核心功能"],
        "priority": "P0",
        "case_type": "functional",
        "project_ids": [1, 2],
        "group_mappings": {
            "1": 10,
            "2": 20
        }
    }
