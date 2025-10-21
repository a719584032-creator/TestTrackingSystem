# 测试管理系统接口索引

> **统一说明**：所有接口均返回 JSON：`{"code": <int>, "message": <str>, "data": <any>}`。除显式说明外，`code=200` 表示成功；需要登录的接口必须携带 `Authorization: Bearer <JWT>` 头。

## 模块文档
- [认证与密码](auth.md)
- [用户管理](users.md)
- [部门管理](departments.md)
- [项目管理](projects.md)
- [设备/机型管理](devices.md)
- [用例分组](case-groups.md)
- [测试用例](test-cases.md)
- [测试计划](test-plans.md)
- [遗留数据只读接口](legacy-data.md)

## 错误码约定
- `400`：参数错误或业务校验失败（`BizError`）。
- `401`：未认证或 token 失效。
- `403`：无访问权限。
- `404`：资源不存在。
- `500`：服务器内部错误。

## 统一字段说明
- 分页参数：`page` 从 1 开始；`page_size` 默认 20，最大 100。
- 布尔查询参数支持：`true/false`、`1/0`、`yes/no`。
- 日期时间字段遵循 ISO8601 字符串。
