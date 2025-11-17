# 设备/机型管理
> 路径前缀：`/api/device-models`

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `` | 平台管理员、部门管理员 | 创建机型，支持扩展属性 `attributes_json`。|
| GET | `` | 登录用户 | 列表查询，必须提供 `department_id`，支持名称、型号、分类、启用状态筛选。|
| GET | `/{device_model_id}` | 登录用户 | 查看机型详情。|
| PUT | `/{device_model_id}` | 平台管理员、部门管理员 | 更新机型基本信息与扩展属性。|
| POST | `/{device_model_id}/enable` | 平台管理员、部门管理员 | 启用机型。|
| POST | `/{device_model_id}/disable` | 平台管理员、部门管理员 | 停用机型。|

## `POST /api/device-models`
- **示例请求**
  ```bash
  curl -X POST https://example.com/api/device-models \
    -H "Authorization: Bearer <TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{
          "department_id": 3,
          "name": "XPhone 13",
          "model_number": "XP13",
          "category": "smartphone",
          "attributes_json": {
            "os_version": "Android 14",
            "chipset": "Snapdragon 8 Gen 3"
          }
        }'
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "机型创建成功",
    "data": {
      "id": 61,
      "department_id": 3,
      "name": "XPhone 13",
      "model_number": "XP13",
      "category": "smartphone",
      "attributes_json": {
        "os_version": "Android 14",
        "chipset": "Snapdragon 8 Gen 3"
      },
      "status": "enabled",
      "created_at": "2024-05-19T11:25:10+08:00"
    }
  }
  ```

## `GET /api/device-models/{device_model_id}`
- **示例请求**
  ```bash
  curl https://example.com/api/device-models/61 \
    -H "Authorization: Bearer <TOKEN>"
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "ok",
    "data": {
      "id": 61,
      "department_id": 3,
      "name": "XPhone 13",
      "model_number": "XP13",
      "category": "smartphone",
      "status": "enabled",
      "attributes_json": {
        "os_version": "Android 14",
        "chipset": "Snapdragon 8 Gen 3"
      },
      "plan_usage_count": 4,
      "created_at": "2024-05-19T11:25:10+08:00",
      "updated_at": "2024-05-19T11:26:34+08:00"
    }
  }
  ```
