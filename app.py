# app.py
from flask import Flask
from config.settings import get_config
from extensions.database import db, migrate
from extensions.legacy_database import legacy_db
from extensions.logger import init_logger
from controllers.auth_controller import auth_bp
from utils.response import json_response
from utils.exceptions import BizError
from controllers.user_controller import user_bp
from services.user_service import UserService
from controllers.department_controller import department_bp
from controllers.test_case_controller import test_case_bp
from controllers.case_group_controller import case_group_bp
from controllers.project_controller import project_bp
from controllers.device_model_controller import device_model_bp
from controllers.test_plan_controller import test_plan_bp
from controllers.legacy_data_controller import legacy_data_bp
from controllers.attachment_controller import attachment_bp
from controllers.ota_controller import ota_bp




def create_app(config_name="development"):
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    # 初始化扩展
    db.init_app(app)
    migrate.init_app(app, db)
    legacy_db.init_app(app)
    init_logger(app)
    print("当前数据库 URI:", app.config["SQLALCHEMY_DATABASE_URI"])
    try:
        # 首次init时表还没创建，需要重复upgrade
        with app.app_context():
            # 确保默认管理员
            UserService.ensure_default_admin(app)
    except BaseException as e:
        print(f"首次init需要等待表结构创建完成后才能添加默认管理员: {e}")

    # 登录
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    # 新增用户管理
    app.register_blueprint(user_bp, url_prefix="/api/users")
    # 部门增删改查
    app.register_blueprint(department_bp)
    # 项目增删改查
    app.register_blueprint(project_bp)
    # 用例增删改查
    app.register_blueprint(test_case_bp)
    app.register_blueprint(case_group_bp)
    # 机型管理
    app.register_blueprint(device_model_bp)
    # 测试计划
    app.register_blueprint(test_plan_bp)
    # 旧数据查询
    app.register_blueprint(legacy_data_bp)
    # 附件访问
    app.register_blueprint(attachment_bp)
    # OTA 升级
    app.register_blueprint(ota_bp)



    # 错误处理
    @app.errorhandler(404)
    def not_found(e):
        return json_response(message="接口不存在", code=404)

    @app.errorhandler(500)
    def server_error(e):
        return json_response(message="服务器内部错误", code=500)

    @app.errorhandler(BizError)
    def _biz_err(e: BizError):
        return json_response(code=e.code, message=e.message, data=e.data)

    return app




if __name__ == "__main__":
    app = create_app()
    app.run(host="10.184.37.17", port=8888, debug=True)
