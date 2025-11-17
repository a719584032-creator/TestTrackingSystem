# 项目管理
> 路径前缀：`/api/projects`

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `` | 平台管理员、部门管理员 | 创建项目，需指定所属部门。|
| GET | `` | 登录用户 | 分页查询项目，支持部门、名称、编码、状态筛选。|
| GET | `/{project_id}` | 登录用户 | 项目详情。|
| PUT | `/{project_id}` | 平台管理员、部门管理员 | 更新项目信息及负责人。|
| DELETE | `/{project_id}` | 平台管理员、部门管理员 | 删除项目，记录操作者。|

## `POST /api/projects`
- **示例请求**
  ```bash
  curl -X POST https://example.com/api/projects \
    -H "Authorization: Bearer <TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "5G 终端适配",
          "code": "PRJ-5G-01",
          "department_id": 3,
          "manager_id": 12,
          "description": "5G 终端兼容性测试"
        }'
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "项目创建成功",
    "data": {
      "id": 42,
      "name": "5G 终端适配",
      "code": "PRJ-5G-01",
      "department_id": 3,
      "manager": {
        "id": 12,
        "username": "alice"
      },
      "status": "active",
      "description": "5G 终端兼容性测试",
      "created_at": "2024-05-18T15:11:28+08:00"
    }
  }
  ```

## `GET /api/projects/{project_id}`
- **示例请求**
  ```bash
  curl https://example.com/api/projects/42 \
    -H "Authorization: Bearer <TOKEN>"
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "ok",
    "data": {
      "id": 42,
      "name": "5G 终端适配",
      "code": "PRJ-5G-01",
      "department": {
        "id": 3,
        "name": "终端研发部"
      },
      "manager": {
        "id": 12,
        "username": "alice"
      },
      "status": "active",
      "description": "5G 终端兼容性测试",
      "member_count": 14,
      "plan_count": 7,
      "created_at": "2024-05-18T15:11:28+08:00",
      "updated_at": "2024-05-20T09:02:17+08:00"
    }
  }
  ```
