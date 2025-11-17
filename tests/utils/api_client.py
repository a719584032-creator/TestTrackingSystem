import json
import requests
from typing import Optional, Dict, Any
from datetime import datetime


class APIClient:
    """统一的API客户端"""

    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token: Optional[str] = None
        self.session = requests.Session()

    def set_token(self, token: str):
        """设置认证token"""
        self.token = token

    def request(self, method: str, path: str,
                params: Optional[Dict] = None,
                json_data: Optional[Dict] = None,
                headers: Optional[Dict] = None,
                attach_token: bool = True) -> Dict[str, Any]:
        """统一的API请求方法"""
        url = f"{self.base_url}{path}"

        # 构建请求头
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)
        if attach_token and self.token:
            request_headers["Authorization"] = f"Bearer {self.token}"

        response = None
        error = None
        result = None

        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                headers=request_headers,
                params=params,
                json=json_data,
                timeout=self.timeout
            )

            # 解析响应
            try:
                result = response.json()
                result["_http_status"] = response.status_code
            except:
                result = {
                    "_http_status": response.status_code,
                    "_raw_text": response.text
                }

        except requests.RequestException as e:
            error = e
            result = {
                "_error": str(e),
                "_http_status": 0
            }

        # 无论成功还是失败，都打印请求响应信息
        self._print_request_response(
            method=method,
            url=url,
            headers=request_headers,
            params=params,
            json_data=json_data,
            response=response,
            result=result,
            error=error
        )

        # 如果有异常，重新抛出
        if error:
            raise error

        return result

    def _print_request_response(self, method: str, url: str,
                                headers: dict = None,
                                params: dict = None,
                                json_data: dict = None,
                                response: requests.Response = None,
                                result: dict = None,
                                error: Exception = None):
        """打印请求和响应的详细信息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"\n{'=' * 80}")
        print(f"[{timestamp}] {method.upper()} {url}")

        # 打印请求信息
        if params:
            print(f"查询参数: {json.dumps(params, ensure_ascii=False, indent=2)}")

        if headers:
            # 隐藏敏感信息
            safe_headers = dict(headers)
            # if "Authorization" in safe_headers:
            #     safe_headers["Authorization"] = "Bearer ***"
            print(f"请求头: {json.dumps(safe_headers, ensure_ascii=False, indent=2)}")

        if json_data:
            print(f"请求体: {json.dumps(json_data, ensure_ascii=False, indent=2)}")

        # 打印响应信息
        if error:
            print(f"❌ 请求异常: {error}")
            if result:
                print(f"错误详情: {json.dumps(result, ensure_ascii=False, indent=2)}")
        elif response:
            status_code = response.status_code
            status_emoji = "✅" if 200 <= status_code < 300 else "⚠️" if 300 <= status_code < 400 else "❌"
            print(f"{status_emoji} 响应状态码: {status_code}")

            # 打印响应头（简化版）
            response_headers = {
                "Content-Type": response.headers.get("Content-Type", ""),
                "Content-Length": response.headers.get("Content-Length", "")
            }
            print(f"响应头: {json.dumps(response_headers, ensure_ascii=False, indent=2)}")

            # 打印响应内容
            if result:
                # 移除内部字段，只显示API返回的内容
                display_result = {k: v for k, v in result.items() if not k.startswith('_')}
                if display_result:
                    print(f"响应内容: {json.dumps(display_result, ensure_ascii=False, indent=2)}")

                # 如果有原始文本且没有JSON内容，显示原始文本
                if '_raw_text' in result and not display_result:
                    print(f"响应内容(原始): {result['_raw_text']}")
        else:
            print("❌ 无响应对象")
            if result:
                print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")

        print(f"{'=' * 80}")
