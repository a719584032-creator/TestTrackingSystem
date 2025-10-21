# 认证与密码

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | 公共 | 使用用户名、密码登录并返回 JWT。|
| POST | `/api/auth/logout` | 登录用户 | 使当前 JWT 失效。|
| POST | `/api/auth/change-password` | 登录用户 | 修改当前用户密码，需要旧密码校验。|

## `POST /api/auth/login`
- **请求体**
  ```json
  {
    "username": "alice",
    "password": "secret123"
  }
  ```
- **示例请求**
  ```bash
  curl -X POST https://example.com/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "alice", "password": "secret123"}'
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "登录成功",
    "data": {
      "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "expires_in": 7200,
      "user": {
        "id": 12,
        "username": "alice",
        "real_name": "Alice Zhang",
        "role": "platform_admin",
        "email": "alice@example.com",
        "department_id": 3
      }
    }
  }
  ```

## `POST /api/auth/change-password`
- **请求体字段**：`old_password`、`new_password`、`confirm_password`。
- **示例请求**
  ```bash
  curl -X POST https://example.com/api/auth/change-password \
    -H "Authorization: Bearer <TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{
          "old_password": "secret123",
          "new_password": "secret456",
          "confirm_password": "secret456"
        }'
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "密码已更新，请使用新口令重新登录",
    "data": {
      "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "expires_in": 7200
    }
  }
  ```
- **额外行为**：修改成功后会吊销旧 JWT，需要使用返回的新 token 重新登录。
