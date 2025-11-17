# 用例分组
> 路径前缀：`/api/case-groups`

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `` | 登录用户 | 创建目录，需提供 `department_id`、`name`。|
| GET | `/{group_id}` | 登录用户 | 查看分组详情。|
| PUT | `/{group_id}` | 登录用户 | 更新名称或调整父级。|
| DELETE | `/{group_id}` | 登录用户 | 删除分组，返回被删除用例数量。|
| POST | `/{group_id}/copy` | 登录用户 | 复制分组至新的父级，可重命名。|
| GET | `/department/{department_id}/tree` | 登录用户 | 获取部门目录树，`with_case_count=true` 可附带用例数量。|
| GET | `/department/{department_id}/children` | 登录用户 | 平铺查询某父级的直接子节点。|

## `POST /api/case-groups`
- **示例请求**
  ```bash
  curl -X POST https://example.com/api/case-groups \
    -H "Authorization: Bearer <TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{
          "department_id": 3,
          "name": "基础功能",
          "parent_id": null
        }'
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "分组创建成功",
    "data": {
      "id": 105,
      "department_id": 3,
      "name": "基础功能",
      "parent_id": null,
      "path": "105",
      "case_count": 0,
      "created_at": "2024-05-19T13:40:52+08:00"
    }
  }
  ```

## `GET /api/case-groups/department/{department_id}/tree`
- **示例请求**
  ```bash
  curl https://example.com/api/case-groups/department/3/tree \
    -H "Authorization: Bearer <TOKEN>" \
    -G --data-urlencode "with_case_count=true"
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "ok",
    "data": [
      {
        "id": 105,
        "name": "基础功能",
        "case_count": 24,
        "children": [
          {
            "id": 106,
            "name": "语音通话",
            "case_count": 10,
            "children": []
          }
        ]
      }
    ]
  }
  ```
