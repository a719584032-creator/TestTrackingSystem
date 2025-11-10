# 测试计划
> 路径前缀：`/api/test-plans`

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `` | 平台管理员、部门管理员、项目管理员 | 创建测试计划，支持绑定用例/目录/机型/执行人。|
| GET | `` | 登录用户 | 分页查询计划，可按项目、部门、状态、关键字过滤。|
| GET | `/{plan_id}` | 登录用户 | 查看计划概要。|
| GET | `/{plan_id}/cases` | 登录用户 | 查看计划内用例，支持按分组、优先级、状态、机型筛选与分组返回。|
| GET | `/{plan_id}/cases/{plan_case_id}` | 登录用户 | 获取计划用例详情及执行历史、附件下载地址。|
| PUT | `/{plan_id}` | 平台管理员、部门管理员、项目管理员 | 更新计划基本信息、执行人。|
| DELETE | `/{plan_id}` | 平台管理员、部门管理员、项目管理员 | 删除计划。|
| POST | `/{plan_id}/results` | 登录用户 | 记录计划用例的执行结果与附件。|

## `POST /api/test-plans/{plan_id}/results`

- **必填字段**
  - `plan_case_id`: 计划用例 ID。
  - `result`: 执行结果（`pass` / `fail` / `block` / `skip`）。
  - `execution_start_time` 与 `execution_end_time`: 执行起止时间，必须提供且需要使用与前端一致的加密规则（Base64 URL-Safe 编码的 `<timestamp_ms>.<hmac_signature>`）。
- **注意事项**
  - 起止时间缺失或解密失败会返回 400 错误；结束时间早于开始时间同样会被拒绝。
  - 若用例要求逐台执行，还需携带 `device_model_id`。
- **示例请求**
  ```bash
  curl -X POST https://example.com/api/test-plans/77/results \
    -H "Authorization: Bearer <TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{
          "plan_case_id": 901,
          "device_model_id": 61,
          "result": "pass",
          "execution_start_time": "<ENCRYPTED_START>",
          "execution_end_time": "<ENCRYPTED_END>",
          "remark": "本轮测试通过"
        }'
  ```

## `POST /api/test-plans`
- **示例请求**
  ```bash
  curl -X POST https://example.com/api/test-plans \
    -H "Authorization: Bearer <TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "5G 语音专项第 1 轮",
          "project_id": 42,
          "department_id": 3,
          "plan_type": "functional",
          "owner_id": 35,
          "start_date": "2024-05-20",
          "end_date": "2024-05-31",
          "linked_case_ids": [501, 502],
          "linked_group_ids": [105],
          "linked_device_model_ids": [61]
        }'
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "测试计划创建成功",
    "data": {
      "id": 77,
      "name": "5G 语音专项第 1 轮",
      "project_id": 42,
      "department_id": 3,
      "plan_type": "functional",
      "status": "draft",
      "owner": {
        "id": 35,
        "username": "bob"
      },
      "start_date": "2024-05-20",
      "end_date": "2024-05-31",
      "created_at": "2024-05-19T15:08:55+08:00"
    }
  }
  ```

## `GET /api/test-plans/{plan_id}/cases`
- **示例请求**
  ```bash
  curl https://example.com/api/test-plans/77/cases \
    -H "Authorization: Bearer <TOKEN>" \
    -G --data-urlencode "group_id=105" \
    --data-urlencode "status=pending"
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "ok",
    "data": {
      "total": 2,
      "items": [
        {
          "plan_case_id": 901,
          "test_case_id": 501,
          "title": "语音通话-基础拨号",
          "priority": "P1",
          "status": "pending",
          "assigned_to": {
            "id": 47,
            "username": "charlie"
          },
          "last_result": null
        }
      ]
    }
  }
  ```
