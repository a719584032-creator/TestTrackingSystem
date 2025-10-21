# 测试用例
> 路径前缀：`/api/test-cases`

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `` | 登录用户 | 创建用例，需验证所属部门权限。|
| POST | `/batch-import` | 登录用户 | 批量导入，可上传 Excel 或提交 JSON。|
| GET | `/{case_id}` | 登录用户 | 用例详情（含分组、创建者、更新者信息）。|
| PUT | `/{case_id}` | 登录用户 | 更新用例，按字段增量修改。|
| DELETE | `/{case_id}` | 登录用户 | 软删除用例。|
| GET | `/department/{department_id}` | 登录用户 | 部门用例列表，支持多种筛选与分页。|
| DELETE | `/batch` | 登录用户 | 批量删除用例，需要 `department_id` + `case_ids`。|
| GET | `/{case_id}/history` | 登录用户 | 查询用例变更历史，默认返回最近 10 条。|
| POST | `/{case_id}/restore` | 登录用户 | 恢复已删除的用例并写入历史。|
| POST | `/{case_id}/copy` | 登录用户 | 复制用例到指定目录。|

**批量导入提示**：Excel 导入将按工作簿目录自动创建/匹配用例分组，返回成功与失败详情。

## `POST /api/test-cases`
- **示例请求**
  ```bash
  curl -X POST https://example.com/api/test-cases \
    -H "Authorization: Bearer <TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{
          "department_id": 3,
          "group_id": 105,
          "title": "语音通话-基础拨号",
          "priority": "P1",
          "preconditions": "手机开机，插入 SIM 卡",
          "steps": [
            "打开拨号应用",
            "输入号码 10010",
            "点击拨打"
          ],
          "expected_results": [
            "成功发起呼叫",
            "对方响铃"
          ]
        }'
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "用例创建成功",
    "data": {
      "id": 501,
      "department_id": 3,
      "group_id": 105,
      "title": "语音通话-基础拨号",
      "priority": "P1",
      "status": "draft",
      "creator": {
        "id": 12,
        "username": "alice"
      },
      "created_at": "2024-05-19T14:02:18+08:00"
    }
  }
  ```

## `GET /api/test-cases/{case_id}`
- **示例请求**
  ```bash
  curl https://example.com/api/test-cases/501 \
    -H "Authorization: Bearer <TOKEN>"
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "ok",
    "data": {
      "id": 501,
      "department_id": 3,
      "group": {
        "id": 105,
        "name": "基础功能"
      },
      "title": "语音通话-基础拨号",
      "priority": "P1",
      "status": "approved",
      "steps": [
        "打开拨号应用",
        "输入号码 10010",
        "点击拨打"
      ],
      "expected_results": [
        "成功发起呼叫",
        "对方响铃"
      ],
      "attachments": [],
      "creator": {
        "id": 12,
        "username": "alice"
      },
      "updater": {
        "id": 35,
        "username": "bob"
      },
      "created_at": "2024-05-19T14:02:18+08:00",
      "updated_at": "2024-05-20T09:40:11+08:00"
    }
  }
  ```
