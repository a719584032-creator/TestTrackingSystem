import requests
import json
import os
from pathlib import Path


class CaseBatchImportTester:
    def __init__(self, base_url, headers):
        self.base_url = base_url.rstrip('/')
        self.headers = headers
        self.department_id = 13

    def test_file_upload(self, file_path, group_id=None, sheet_index=0):
        """测试文件上传接口"""
        url = f"{self.base_url}/api/test-cases/batch-import"

        # 准备表单数据
        data = {
            'department_id': str(self.department_id),
            'sheet_index': str(sheet_index)
        }

        if group_id is not None:
            data['group_id'] = str(group_id)

        # 准备文件
        if not os.path.exists(file_path):
            print(f"❌ 文件不存在: {file_path}")
            return None

        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f,
                              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}

            try:
                response = requests.post(url, headers=self.headers, data=data, files=files)
                return self._handle_response(response, f"上传文件: {os.path.basename(file_path)}")
            except Exception as e:
                print(f"❌ 请求异常: {e}")
                return None

    def test_invalid_file_scenarios(self):
        """测试无效文件场景"""
        url = f"{self.base_url}/api/test-cases/batch-import"

        # 测试1: 空文件名
        print("\n=== 测试空文件名 ===")
        data = {'department_id': str(self.department_id)}
        files = {'file': ('', b'', 'application/octet-stream')}
        response = requests.post(url, headers=self.headers, data=data, files=files)
        self._handle_response(response, "空文件名测试")

        # 测试2: 空文件内容
        print("\n=== 测试空文件内容 ===")
        files = {'file': ('test.xlsx', b'', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        response = requests.post(url, headers=self.headers, data=data, files=files)
        self._handle_response(response, "空文件内容测试")

        # 测试3: 无效的sheet_index
        print("\n=== 测试无效sheet_index ===")
        data = {'department_id': str(self.department_id), 'sheet_index': 'invalid'}
        # 创建一个临时的测试文件
        test_content = b'test content'
        files = {
            'file': ('test.xlsx', test_content, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        response = requests.post(url, headers=self.headers, data=data, files=files)
        self._handle_response(response, "无效sheet_index测试")

        # 测试4: 无效的group_id
        print("\n=== 测试无效group_id ===")
        data = {'department_id': str(self.department_id), 'group_id': 'invalid'}
        response = requests.post(url, headers=self.headers, data=data, files=files)
        self._handle_response(response, "无效group_id测试")

    def _handle_response(self, response, test_name):
        """处理响应结果"""
        print(f"\n--- {test_name} ---")
        print(f"状态码: {response.status_code}")

        try:
            result = response.json()
            print(f"响应内容: {json.dumps(result, ensure_ascii=False, indent=2)}")

            if response.status_code == 200:
                print("✅ 测试通过")
            else:
                print("⚠️  测试失败或返回错误")

            return result
        except json.JSONDecodeError:
            print(f"响应内容 (非JSON): {response.text}")
            return None

    def run_all_tests(self, test_files):
        """运行所有测试"""
        print("🚀 开始批量导入测试用例接口测试")
        print(f"测试地址: {self.base_url}/api/test-cases/batch-import")
        print(f"部门ID: {self.department_id}")

        # 测试有效文件上传
        for file_info in test_files:
            file_path = file_info['path']
            group_id = file_info.get('group_id')
            sheet_index = file_info.get('sheet_index', 0)

            print(f"\n{'=' * 50}")
            print(f"测试文件: {file_path}")
            print(f"分组ID: {group_id if group_id else '无'}")
            print(f"Sheet索引: {sheet_index}")

            self.test_file_upload(file_path, group_id, sheet_index)

        # 测试异常场景
        print(f"\n{'=' * 50}")
        print("开始测试异常场景")
        self.test_invalid_file_scenarios()

        print(f"\n{'=' * 50}")
        print("🎉 所有测试完成")


def main():
    # 配置信息 - 请根据实际情况修改
    BASE_URL = "http://10.184.37.17:8888"  # 您的API地址

    # 请填写您的认证headers
    HEADERS = {
        'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEsInVzZXJuYW1lIjoiYWRtaW4iLCJyb2xlIjoiYWRtaW4iLCJwd2R2IjoxLCJleHAiOjE3NTgyMTk3MzYsImlhdCI6MTc1ODE5MDkzNiwianRpIjoiOWEzNTc4ZjEyNDMxNGVmZTk2ODk3YjY2OWZmZjVkMjMifQ.QYa0CwRro-Cv-Px7jR6U83NZaXth5qmLZ8q2ze7_7NY',  # 请替换为实际的token
        # 'Cookie': 'session=your_session_here',  # 或者使用Cookie认证
        # 其他需要的headers
    }

    # 测试文件配置 - 请根据实际情况修改
    TEST_FILES = [
        {
            'path': r"C:\Users\71958\Downloads\01 Mouse Test information.xlsx",  # 请替换为实际的测试文件路径
            'group_id': None,  # 不指定分组，会根据Excel中的文件夹名创建
            'sheet_index': 0
        },
        {
            'path': r"C:\Users\71958\Downloads\01 Mouse Test information.xlsx",
            'group_id': 1,  # 请替换为实际的分组ID
            'sheet_index': 0
        }
    ]

    # 创建测试器并运行测试
    tester = CaseBatchImportTester(BASE_URL, HEADERS)
    tester.run_all_tests(TEST_FILES)


if __name__ == "__main__":
    main()
