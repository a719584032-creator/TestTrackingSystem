import os
import json
import requests
from typing import Optional, Dict, Any

# 配置
BASE_URL = os.environ.get("API_BASE_URL", "http://10.184.37.17:8888")
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

#     headers = {
#   "Content-Type": "application/json",
#   "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEsInVzZXJuYW1lIjoiYWRtaW4iLCJyb2xlIjoiYWRtaW4iLCJwd2R2IjoxLCJleHAiOjE3NTc1MjEzOTMsImlhdCI6MTc1NzQ5MjU5MywianRpIjoiZDgyMWY1YWMzOTk1NDU3OGFiMmY0MTUxZDVjN2Y4NTkifQ.cwuqStA7iou3ExsHSqNVL-GsI7xZUZJ4yA-O63O2RZY"
# }
#     data = {
#         "name": "new_mulu"
#     }
#     # resp = requests.post(url='http://127.0.0.1/api/auth/logout', headers=headers)
#     # resp = requests.post(url='http://127.0.0.1/api/auth/login', json=data)
#     resp = requests.delete(url='http://10.184.37.17:8888/api/case-groups/108', headers=headers)
#     print(resp.status_code)
#     print(resp.json())

    import os
    import boto3
    from botocore.config import Config

    ENDPOINT = "https://oss4.xcloud.lenovo.com:10443"

    session = boto3.session.Session(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID") or "A003863_Testing",
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY") or "b2BktcdB6BnMaJueO/ZNJ0QrpUPWcffgY4engwXT",
        region_name=os.getenv("AWS_REGION_NAME", "us-east-1"),
    )

    cfg = Config(
        signature_version=os.getenv("AWS_SIGNATURE_VERSION", "s3v4"),
        s3={"addressing_style": "path"}  # 自定义 endpoint 常用 path-style
    )

    s3 = session.client("s3", endpoint_url=ENDPOINT, config=cfg)
    bucket = 'tts'

    # 1) 上传对象
    file_path = r"C:\Users\71958\Pictures\2.png"
    size = os.path.getsize(file_path)

    with open(file_path, "rb") as f:
        s3.put_object(
            Bucket=bucket,
            Key="uploads/images",
            Body=f,
            ContentType="application/octet-stream",
            ContentLength=size,  # 关键
        )

    # 2) 下载对象
    obj = s3.get_object(Bucket=bucket, Key="uploads/images")
    content = obj["Body"].read()

    # 3) 生成预签名上传 URL（给前端直传）
    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": "your-bucket", "Key": "uploads/image.png", "ContentType": "image/png"},
        ExpiresIn=900,  # 15分钟
    )
    print("Presigned PUT:", url)

    # 4) 列前缀（当作“文件夹”）
    resp = s3.list_objects_v2(Bucket="your-bucket", Prefix="demo/", Delimiter="/")
    for item in resp.get("Contents", []):
        print(item["Key"], item["Size"])
