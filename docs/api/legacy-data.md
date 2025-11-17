# 遗留数据只读接口
> 路径前缀：`/api/legacy-data`

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/projects` | 公共 | 查询历史项目（关键字模糊匹配）。|
| GET | `/plans` | 公共 | 按项目名称查询历史计划，需 `project_name`。|
| GET | `/plans/{plan_id}/models` | 公共 | 查询历史计划关联机型。|
| GET | `/plans/{plan_id}/statistics` | 公共 | 获取历史计划统计数据。|
| GET | `/plans/{plan_id}/sheets` | 公共 | 获取计划下的测试表信息。|
| GET | `/sheets/{sheet_id}/cases` | 公共 | 查询指定表在特定机型下的用例状态，需 `model_id`。|
| GET | `/images` | 公共 | 根据执行记录 ID 列表获取截图地址。|

## `GET /api/legacy-data/projects`
- **示例请求**
  ```bash
  curl -G https://example.com/api/legacy-data/projects \
    --data-urlencode "keyword=5G"
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "ok",
    "data": [
      {
        "project_name": "5G 兼容性历史项目",
        "owner": "Legacy Owner",
        "created_at": "2021-03-12T08:00:00+08:00"
      }
    ]
  }
  ```

## `GET /api/legacy-data/plans/{plan_id}/models`
- **示例请求**
  ```bash
  curl https://example.com/api/legacy-data/plans/102/models
  ```
- **示例成功响应**
  ```json
  {
    "code": 200,
    "message": "ok",
    "data": [
      {
        "model_name": "XPhone 12",
        "model_number": "XP12",
        "category": "smartphone"
      }
    ]
  }
  ```
