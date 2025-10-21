# 测试管理系统整体架构

本系统基于 Flask 构建，按照「控制器（Controller）- 服务（Service）- 仓储（Repository）- 模型（Model）」的分层思想实现业务逻辑。下图展示了核心组件与依赖关系：

```mermaid
graph TD
    A[客户端 / 前端] --> B[Flask 蓝图 Controller]
    B --> C[Service 业务层]
    C --> D[Repository 数据访问层]
    D --> E[(主业务数据库\nSQLAlchemy / MySQL)]
    C --> F[LegacyDataService]
    F --> G[(遗留数据库\nlegacy_db)]
    C --> H[扩展组件]
    H --> H1[JWT / 认证]
    H --> H2[Redis 客户端 (可选缓存)]
    B --> I[统一响应 & 异常处理]
    I --> A
```

## 分层职责说明

| 层级 | 主要目录 | 核心职责 |
| --- | --- | --- |
| 应用入口 | `app.py` | 初始化配置、注册蓝图/扩展、全局异常处理。|
| 配置与扩展 | `config/`, `extensions/` | 管理环境配置、数据库连接、日志、JWT、Redis 等。|
| 控制器层 | `controllers/` | 定义蓝图路由，完成参数解析、权限校验、调用服务并包装统一响应。|
| 服务层 | `services/` | 承载业务编排与事务边界，组合多个仓储及第三方服务。|
| 仓储层 | `repositories/` | 封装 SQLAlchemy 查询与持久化操作，屏蔽具体数据源。|
| 数据模型 | `models/` | 定义 ORM 模型、字段、关联、行为方法（如密码加密）。|
| 工具与常量 | `utils/`, `constants/` | 提供响应包装、异常、权限判断、角色常量等。|

## 数据流示例

以「创建测试用例」为例：
1. `POST /api/test-cases` 由 `controllers/test_case_controller.py` 接收请求，解析 JSON 并校验部门权限。 【F:controllers/test_case_controller.py†L18-L75】
2. 控制器调用 `TestCaseService.create` 执行业务逻辑：写入用例基础信息、关联目录、设置默认状态等。 【F:controllers/test_case_controller.py†L44-L75】
3. 服务层使用 `TestCaseRepository` 完成数据库写入，并可能记录操作历史。 【F:controllers/test_case_controller.py†L44-L120】
4. 统一通过 `utils.response.json_response` 返回结果，应用层处理异常或错误码。 【F:utils/response.py†L1-L37】

## 扩展组件
- **数据库**：`extensions/database.py` 初始化主业务库（SQLAlchemy + Flask-Migrate），`extensions/legacy_database.py` 负责遗留库只读连接。 【F:extensions/database.py†L1-L33】【F:extensions/legacy_database.py†L1-L46】
- **认证**：`extensions/jwt.py` 提供 JWT 的创建与吊销能力，并在 `controllers/auth_helpers.py` 中落地为装饰器。 【F:extensions/jwt.py†L1-L86】【F:controllers/auth_helpers.py†L1-L114】
- **日志**：`extensions/logger.py` 统一设置日志格式、级别。 【F:extensions/logger.py†L1-L60】
- **缓存/队列**（可选）：`extensions/redis_client.py` 暴露 `get_redis()`，供需要的服务使用。 【F:extensions/redis_client.py†L1-L13】

## 统一错误处理
- 自定义业务异常通过 `utils.exceptions.BizError` 表达，控制器或全局 handler 将其转换为带业务提示的 JSON。 【F:utils/exceptions.py†L1-L52】【F:app.py†L46-L66】
- 常见 HTTP 错误（404/500）在 `app.py` 内集中处理，确保客户端获得一致格式。 【F:app.py†L46-L66】

## 权限体系概览
- 基于 JWT 的身份认证，成功登录后返回 token。 【F:controllers/auth_controller.py†L13-L55】
- 角色常量定义于 `constants/roles.py`，配合 `auth_required` 装饰器在各控制器上声明接口权限。 【F:constants/roles.py†L1-L27】【F:controllers/auth_helpers.py†L1-L114】
- 部门/项目细粒度权限在 `utils/permissions.py` 中实现，例如 `assert_dept_admin`、`assert_user_in_department`。 【F:utils/permissions.py†L1-L170】

该文档可与《接口文档》配合使用，帮助快速理解请求在系统中的完整流转路径。
