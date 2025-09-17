# 最终版测试管理系统数据模型（MySQL）

目录建议：
```
├── app.py                    # Flask 应用入口
├── config/                   # 配置相关
│   ├── __init__.py
│   ├── settings.py           # 基础配置类（开发、测试、生产环境、AWS、redis）
├── constants/                # 项目常量
│   ├── __init__.py
│   ├── roles.py
│   ├── department_reles.py
├── extensions/               # 第三方扩展初始化（db, jwt, cache 等）
│   ├── __init__.py
│   ├── database.py           # SQLAlchemy 初始化
│   ├── jwt.py                # JWT 初始化
│   ├── logger.py             # 日志初始化
├── models/                   # ORM 模型
│   ├── __init__.py
│   ├── mixins.py
│   ├── user.py
│   ├── department.py
│   ├── project.py
│   ├── device_model.py
│   ├── test_plan.py
│   ├── plan_case.py
│   ├── plan_device_model.py
│   ├── case_group.py
│   ├── test_case.py
│   ├── execution.py
│   ├── comment.py
│   ├── attachment.py
│   ├── tag.py
├── schemas/                  # 数据序列化与验证
│   ├── __init__.py
├── repositories/             # 数据访问层（DAO）
│   ├── __init__.py
├── services/                 # 业务逻辑层
│   ├── __init__.py
├── controllers/              # 控制器（蓝图路由）
│   ├── __init__.py
├── utils/                    # 工具模块
│   ├── __init__.py
│   ├── response.py           # 统一 API 响应格式
│   ├── exceptions.py         # 自定义异常
│   ├── password.py           # 密码加密/校验
│   ├── datetime_util.py
├── migrations/               # 数据库迁移文件（Flask-Migrate）
├── tests/                    # 单元测试
│   ├── __init__.py
│   ├── test_auth.py
│   ├── test_testplan.py
├── requirements.txt          # Python 依赖
├── .env                      # 环境变量（数据库、JWT 密钥等）
├── README.md
```
## 11. 初始迁移（空库直接一次性生成）

执行：
```
bash
flask db init         # 仅首次
flask db migrate -m "init full schema v1"
flask db upgrade
```

Alembic 自动生成会列出所有 create_table。  
可根据需要手工添加 engine / charset（通常 Alembic 生成时会自动携带）及索引顺序。

但生产仍建议使用 Alembic 管理版本。

## 12. 常见查询索引建议（可按需再补）

| 场景 | 建议索引 |
|------|---------|
| 计划执行结果统计 | execution_result (run_id, result) 已有 |
| 按计划过滤设备 | plan_device_model(plan_id, device_model_id) 唯一约束可用 |
| 用例层次检索 | case_group(project_id, path) 已有 |
| 用例筛选 | test_case(project_id, status), test_case(group_id) |
| 评论拉取 | comment(target_type, target_id) |
| 标签过滤 | tag_map(target_type, target_id) + tag_id（如需反查 tag → objects 已有） |

## 13. 一些可选改进

- 使用 Enum：MySQL 原生 Enum 修改不便，推荐 varchar + CheckConstraint（MySQL 8.0+ 生效）或应用层校验。
- 大表分区：execution_result 可按 run_id HASH 或 executed_at RANGE（后期量大再考虑）。
- 软删除：对 TestCase / TestPlan 引入 SoftDeleteMixin 替代物理删除。


## 15. 前后端字段映射提示

| 概念 | 关键主表 | 说明 |
|------|----------|------|
| 用例原始数据 | test_case | 编辑时更新；PlanCase 不随之自动变更（快照） |
| 计划快照 | plan_case | 创建计划或刷新选择时生成 |
| 执行批次 | execution_run | 每次测试执行 session |
| 执行结果 | execution_result | run 内每 (plan_case, device_model) 一行 |
| 评论/附件 | comment / attachment | 通过 target_type + target_id 聚合 |
| 标签 | tag + tag_map | 通用关联 |


- 新建文件
```yaml
mkdir -p /data/mysql/conf
```
- 添加配置
```
cat >/data/mysql/conf/my.cnf <<'EOF'
[mysqld]
bind-address=0.0.0.0
# 典型附加优化示例：
character-set-server = utf8mb4
collation-server = utf8mb4_general_ci
max_connections = 300
# 避免某些客户端时区问题
default-time-zone = '+08:00'

[client]
default-character-set = utf8mb4
EOF

```


## redis 配置
- 创建文件
```
mkdir -p /data/redis/conf
mkdir -p /data/redis/data

```

- 添加配置
```
cat > /data/redis/conf/redis.conf <<'EOF'
bind 0.0.0.0
protected-mode no
port 6379
daemonize no
tcp-backlog 511
timeout 0
tcp-keepalive 300
databases 16

# 开启 AOF（更高数据安全，稍牺牲性能）
appendonly yes
appendfsync everysec

# RDB 策略（默认即可，可按需调整）
save 900 1
save 300 10
save 60 10000

# 设置密码（示例，实际请替换）
requirepass StrongRedis@123

# 避免复制/集群下明文主从认证时泄露（如需主从配置还需 masterauth）
# masterauth StrongRedis@123

# 限制客户端最大连接数（按需要）
# maxclients 10000

# 内存策略：达到 maxmemory 后的淘汰策略（示例）
# maxmemory 2gb
# maxmemory-policy allkeys-lru

EOF

```



