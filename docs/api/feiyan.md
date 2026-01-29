# 飞雁数据导入导出
> 路径前缀：`/api/feiyan`  
> 说明：仅用于飞雁系统数据导入、执行结果更新与导出回写；数据不关联现有业务，仅复用登录与用户名。

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/departments` | 登录用户 | 分页查询飞雁部门（去重）。|
| GET | `/projects` | 登录用户 | 分页查询飞雁项目（去重），支持按部门/名称过滤。|
| GET | `/test-plans` | 登录用户 | 分页查询飞雁计划，支持按部门/项目过滤。|
| GET | `/test-plans/{plan_id}` | 登录用户 | 获取单个飞雁测试计划详情。|
| GET | `/test-plans/{plan_id}/cases` | 登录用户 | 分页查询计划用例与执行结果。|
| POST | `/test-plans/{plan_id}/attachments/presign` | 登录用户 | 生成附件上传预签名URL（对象存储直传）。|
| POST | `/test-plans/{plan_id}/results` | 登录用户 | 更新单条用例执行结果（run_result 为空则不更新）。|
| POST | `/test-plans/import` | 登录用户 | 导入 Excel（模板：导入导出数据模板2.xlsx）。|
| GET | `/test-plans/{plan_id}/export` | 登录用户 | 导出计划数据到Excel。|

## `GET /api/feiyan/departments`
- **查询参数**
  - `page`：页码，默认 1。
  - `page_size`：每页数量，默认 1000。
- **示例请求**
  ```bash
  curl -H "Authorization: Bearer <TOKEN>" \
    "https://example.com/api/feiyan/departments?page=1&page_size=1000"
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "items": [
        {
          "department_id": "1",
          "department_name": "部门1"
        }
      ],
      "total": 1,
      "page": 1,
      "page_size": 1000
    }
  }
  ```


## `GET /api/feiyan/projects`
- **查询参数**
  - `department_id` / `dept_id`：部门ID（外部）。
  - `name` / `keyword` / `project_name`：项目名称模糊匹配。
  - `page`：页码，默认 1。
  - `page_size`：每页数量，默认 20。
- **示例请求**
  ```bash
  curl -H "Authorization: Bearer <TOKEN>" \
    "https://example.com/api/feiyan/projects?department_id=1&name=project&page=1&page_size=20"
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "items": [
        {
          "project_id": "10",
          "project_name": "项目A",
          "department_id": "1",
          "department_name": "部门1"
        }
      ],
      "total": 1,
      "page": 1,
      "page_size": 20
    }
  }
  ```


## `GET /api/feiyan/test-plans/{plan_id}`
- **路径参数**
  - `plan_id`：计划ID（外部）。
- **示例请求**
  ```bash
  curl -H "Authorization: Bearer <TOKEN>" \\
    "https://example.com/api/feiyan/test-plans/10001"
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "plan_id": "10001",
      "department_id": "1",
      "department_name": "部门1",
      "project_id": "10",
      "project_name": "项目A",
      "name": "飞雁计划A",
      "start_time": "2025-01-01 10:00:00",
      "end_time": "2025-01-31 18:00:00",
      "total": 100,
      "passed": 30,
      "failed": 10,
      "blocked": 5,
      "not_run": 55,
      "tester_ids": [{"1": "张三"}, {"2": "李四"}],
      "tester_names": "张三,李四",
      "created_by_user_id": 88,
      "created_at": "2025-01-02T12:00:00",
      "updated_at": "2025-01-03T09:30:00",
      "devices": [
        {"device_id": "D01", "device_name": "设备A"},
        {"device_id": "D02", "device_name": "设备B"}
      ]
    }
  }
  ```

## `GET /api/feiyan/test-plans`
- **查询参数**
  - `department_id`：部门 ID（外部）。
  - `project_id`：项目 ID（外部）。
  - `page`：页码，默认 1。
  - `page_size`：每页数量，默认 100。
- **示例请求**
  ```bash
  curl -H "Authorization: Bearer <TOKEN>" \
    "https://example.com/api/feiyan/test-plans?department_id=1&project_id=10&page=1&page_size=100"
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "items": [
        {
          "plan_id": "10001",
          "department_id": "1",
          "department_name": "部门1",
          "project_id": "10",
          "project_name": "项目A",
          "name": "飞雁计划A",
          "start_time": "2025-01-01 10:00:00",
          "end_time": "2025-01-31 18:00:00",
          "total": 100,
          "passed": 30,
          "failed": 10,
          "blocked": 5,
          "not_run": 55,
          "tester_ids": [{"1": "张三"}, {"2": "李四"}],
          "tester_names": "张三,李四",
          "created_by_user_id": 88,
          "created_at": "2025-01-02T12:00:00",
          "updated_at": "2025-01-03T09:30:00"
        }
      ],
      "total": 1,
      "page": 1,
      "page_size": 100
    }
  }
  ```

## `GET /api/feiyan/test-plans/{plan_id}/cases`
- **查询参数**
  - `page`：页码，默认 1。
  - `page_size`：每页数量，默认 100。
  - `title` / `keyword`：标题关键字。
  - `group_path` / `group`：分组路径过滤。
  - `priority`：优先级过滤。
  - `run_result`：结果过滤（`pass`/`fail`/`block`/`pending`/`skip`）。
- **示例请求**
  ```bash
  curl -H "Authorization: Bearer <TOKEN>" \
    "https://example.com/api/feiyan/test-plans/10001/cases?page=1&page_size=20&run_result=pending"
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "items": [
        {
          "id": 1,
          "plan_id": "10001",
          "case_id": "50001",
          "title": "开机流程检查",
          "priority": "P1",
          "group_path": "root/启动",
          "target": "验证开机流程",
          "preconditions": "设备已断电",
          "steps": [{"no": 1, "action": "按下电源键"}],
          "expected_result": "设备成功启动",
          "keywords": ["boot", "smoke"],
          "workload_minutes": 5,
        {"device_id": "D01", "device_name": "设备A"},
          "device_name": "设备A",
          "executed_by_id": "11",
          "executed_by_name": "张三",
          "execution_start_time": "2025-01-05 10:00:00",
          "execution_end_time": "2025-01-05 10:10:00",
          "run_result": "pending",
          "remark": null,
          "failure_reason": null,
          "bug_ref": null,
          "attachments": [
            {"file_name": "a.png", "url": "https://oss.example/a.png"}
          ],
          "created_at": "2025-01-05T10:00:00",
          "updated_at": "2025-01-05T10:00:00"
        }
      ],
      "total": 1,
      "page": 1,
      "page_size": 20,
      "group_tree": {
        "name": "root",
        "path": "root",
        "children": [
          {"name": "启动", "path": "root/启动", "children": []}
        ]
      }
    }
  }
  ```

## `POST /api/feiyan/test-plans/{plan_id}/attachments/presign`
- **说明**
  - 生成对象存储上传预签名 URL，前端用返回的 `upload_url` 直传文件。
  - `case_id` 或 `case_id_ext` 必填。
- **示例请求**
  ```bash
  curl -X POST https://example.com/api/feiyan/test-plans/10001/attachments/presign \
    -H "Authorization: Bearer <TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{
          "case_id": "50001",
          "file_name": "a.png",
          "mime_type": "image/png",
          "size": 12345
        }'
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "success",
    "data": {
      "method": "PUT",
      "upload_url": "https://oss.example/tts-test/feiyan/20250105/50001/a.png?...",
      "headers": {
        "Content-Type": "image/png"
      },
      "file_key": "feiyan/20250105/50001/a.png",
      "file_name": "a.png",
      "mime_type": "image/png",
      "size": 12345,
      "expires_in": 3600
    }
  }
  ```

## `POST /api/feiyan/test-plans/{plan_id}/results`
- **说明**
  - 仅当 `run_result` 有值时才会更新结果字段。
  - `case_id` 或 `case_id_ext` 必填。
  - 结果枚举：`pass` / `fail` / `block` / `pending` / `skip`。
  - 附件需先调用预签名接口上传，再提交 `file_key`。
- **示例请求**
  ```bash
  curl -X POST https://example.com/api/feiyan/test-plans/10001/results \
    -H "Authorization: Bearer <TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{
          "case_id": "50001",
          "run_result": "pass",
          "execution_start_time": "2025-01-05 10:00:00",
          "execution_end_time": "2025-01-05 10:10:00",
          "remark": "执行通过",
          "bug_ref": "BUG-123",
          "attachments": [
            {
              "file_name": "a.png",
              "file_key": "feiyan/20250105/50001/a.png",
              "mime_type": "image/png",
              "size": 12345
            }
          ]
        }'
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "结果已记录",
    "data": {
      "id": 1,
      "plan_id": "10001",
      "case_id": "50001",
      "run_result": "pass",
      "executed_by_id": "88",
      "executed_by_name": "admin",
      "execution_start_time": "2025-01-05 10:00:00",
      "execution_end_time": "2025-01-05 10:10:00",
      "remark": "执行通过",
      "attachments": [
        {
          "file_name": "a.png",
          "file_key": "feiyan/20250105/50001/a.png",
          "url": "https://oss.example/tts-test/feiyan/20250105/50001/a.png?..."
        }
      ]
    }
  }
  ```

## `POST /api/feiyan/test-plans/import`
- **说明**
  - `multipart/form-data` 上传，字段名：`file`（或 `files`）。
  - 模板：`导入导出数据模版2.xlsx`。
  - 必填字段：部门ID、部门名称、项目ID、项目名称、设备ID、测试计划ID、测试计划名称、计划测试人员、用例ID、用例标题、用例关键字。
  - ID字段允许数字或字符串（包含 UUID）。
  - 缺列或必填为空将返回对应行的错误信息。
- **示例请求**
  ```bash
  curl -X POST https://example.com/api/feiyan/test-plans/import \
    -H "Authorization: Bearer <TOKEN>" \
    -F "file=@导入导出数据模版2.xlsx"
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "导入完成",
    "data": {
      "success_count": 120,
      "failure_count": 2,
      "errors": [
        {"row": 12, "message": "第12行缺少计划ID"}
      ]
    }
  }
  ```

## `GET /api/feiyan/test-plans/{plan_id}/export`
- **说明**
  - 返回 Excel 文件（模板格式）。
- **示例请求**
  ```bash
  curl -H "Authorization: Bearer <TOKEN>" \
    -o feiyan_test_plan_10001.xlsx \
    "https://example.com/api/feiyan/test-plans/10001/export"
  ```
