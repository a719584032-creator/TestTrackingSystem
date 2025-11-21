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
## 初始迁移部署（空库直接一次性生成）

执行：
```
bash
flask db init         # 仅首次
flask db migrate -m "init full schema v1"
flask db upgrade
```


## redis 配置
- 创建文件
```
mkdir -p /data/redis/conf
mkdir -p /data/redis/data

```




