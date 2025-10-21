# 部门管理
> 路径前缀：`/api/departments`

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `` | 平台管理员 | 创建部门，包含 `name`、`code`、`description`。|
| GET | `` | 登录用户 | 分页查询部门，可通过名称、编码、状态筛选。|
| GET | `/{dept_id}` | 登录用户 | 获取部门详情及统计字段。|
| PUT | `/{dept_id}` | 平台管理员、部门管理员 | 更新名称、编码、描述、状态。|
| PATCH | `/{dept_id}/status` | 平台管理员 | 启用/禁用部门。|
| POST | `/{dept_id}/members` | 平台管理员、部门管理员 | 添加或更新成员角色，支持 `upsert`。|
| GET | `/{dept_id}/members` | 登录用户 | 分页查询成员（复用用户列表逻辑）。|
| PATCH | `/role/{member_id}` | 部门管理员 | 修改成员的部门内角色。|
| DELETE | `/{department_id}/members/{user_id}` | 部门管理员 | 将成员移出部门。|

## `POST /api/departments`
- **示例请求**
  ```bash
  curl -X POST https://example.com/api/departments \
    -H "Authorization: Bearer <TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{
          "name": "终端研发部",
          "code": "RD-001",
          "description": "终端与固件测试团队"
        }'
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "部门创建成功",
    "data": {
      "id": 3,
      "name": "终端研发部",
      "code": "RD-001",
      "description": "终端与固件测试团队",
      "status": "enabled",
      "created_at": "2024-05-16T10:20:33+08:00"
    }
  }
  ```

## `GET /api/departments/{dept_id}`
- **示例请求**
  ```bash
  curl https://example.com/api/departments/3 \
    -H "Authorization: Bearer <TOKEN>"
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "ok",
    "data": {
      "id": 3,
      "name": "终端研发部",
      "code": "RD-001",
      "status": "enabled",
      "description": "终端与固件测试团队",
      "member_count": 18,
      "project_count": 6,
      "created_at": "2024-05-16T10:20:33+08:00",
      "updated_at": "2024-05-19T08:12:00+08:00"
    }
  }
  ```
