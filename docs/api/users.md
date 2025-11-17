# 用户管理
> 路径前缀：`/api/users`

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/create` | 平台管理员 | 创建用户（支持指定角色、邮箱、手机号）。|
| GET | `/list` | 平台管理员、部门管理员 | 支持分页及多条件组合筛选的用户列表。|
| PATCH | `/{user_id}/status` | 平台管理员、部门管理员 | 启用/停用用户帐号，`{"active": true/false}`。|
| PATCH | `/{user_id}/profile` | 平台管理员、部门管理员 | 更新指定用户的邮箱、手机号、角色。|
| PATCH | `/me/profile` | 登录用户 | 更新自己的邮箱或手机号。|
| POST | `/{user_id}/password/reset` | 登录用户 | 管理员可重置任意用户，普通用户仅可重置自身。返回一次性新密码。|

## `POST /api/users/create`
- **示例请求**
  ```bash
  curl -X POST https://example.com/api/users/create \
    -H "Authorization: Bearer <TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{
          "username": "bob",
          "real_name": "Bob Lee",
          "email": "bob@example.com",
          "phone": "13800138000",
          "role": "department_admin",
          "department_id": 3,
          "password": "Temp@123"
        }'
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "用户创建成功",
    "data": {
      "id": 35,
      "username": "bob",
      "real_name": "Bob Lee",
      "role": "department_admin",
      "email": "bob@example.com",
      "phone": "13800138000",
      "department_id": 3,
      "active": true,
      "created_at": "2024-05-19T09:32:41+08:00"
    }
  }
  ```

## `GET /api/users/list`
- **常用查询参数**：`page=1&page_size=20&department_id=3&role=tester&keyword=alice`
- **示例请求**
  ```bash
  curl -G https://example.com/api/users/list \
    -H "Authorization: Bearer <TOKEN>" \
    --data-urlencode "page=1" \
    --data-urlencode "page_size=20" \
    --data-urlencode "department_id=3"
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "ok",
    "data": {
      "page": 1,
      "page_size": 20,
      "total": 56,
      "items": [
        {
          "id": 12,
          "username": "alice",
          "real_name": "Alice Zhang",
          "role": "platform_admin",
          "email": "alice@example.com",
          "phone": "13800138001",
          "department": {
            "id": 3,
            "name": "终端研发部"
          },
          "active": true,
          "last_login_at": "2024-05-18T17:20:04+08:00"
        }
      ]
    }
  }
  ```

**列表查询参数摘要**：`page`、`page_size`、`username`、`email`、`phone`、`role`、`role_label`、`active`、`department_id`。
