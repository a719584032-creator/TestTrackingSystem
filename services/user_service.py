# services/user_service.py
from models.user import User
from repositories.user_repository import UserRepository
from utils.password import hash_password, verify_password
from utils.exceptions import BizError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from extensions.database import db
from constants.roles import SystemRole, normalize_system_role
from flask import current_app


SYSTEM_WRITE_ROLES = {SystemRole.ADMIN.value}


class UserService:

    @staticmethod
    def _check_update_permission(actor: User, target: User):
        """检查更新权限"""
        if actor.id != target.id:
            if actor.role not in SYSTEM_WRITE_ROLES:
                raise BizError("无权限修改他人信息", code=403)

    @staticmethod
    def _validate_and_normalize_profile_data(email: str, phone: str, role_raw: str) -> dict:
        """验证和规范化资料数据"""
        result = {}

        # Email 验证
        if email is not None:
            new_email = email.strip() if isinstance(email, str) else email
            if new_email:
                from utils.validators import validate_email
                if not validate_email(new_email):
                    raise BizError("邮箱格式不正确", code=400)
            result['new_email'] = new_email

        # Phone 验证
        if phone is not None:
            from utils.validators import normalize_phone
            norm_phone = normalize_phone(phone)
            if norm_phone is None:
                raise BizError("手机号格式不正确", code=400)
            result['new_phone'] = norm_phone

        # System role 验证
        if role_raw is not None:
            if isinstance(role_raw, str) and role_raw.strip() == "":
                raise BizError("非法角色值", code=400)
            try:
                normalized = normalize_system_role(role_raw, default=SystemRole.VIEWER)
                result['new_role'] = normalized
                result['role_changing'] = True
            except ValueError:
                raise BizError("非法角色值", code=400)

        return result

    @staticmethod
    def _check_uniqueness_constraints(target_user_id: int, validated_data: dict):
        """检查唯一性约束"""
        new_email = validated_data.get('new_email')
        new_phone = validated_data.get('new_phone')

        if new_email and UserRepository.exists_email_except_user(new_email, target_user_id):
            raise BizError("邮箱已被占用", code=409)

        if new_phone and UserRepository.exists_phone_except_user(new_phone, target_user_id):
            raise BizError("手机号已被占用", code=409)

    @staticmethod
    def _check_role_change_constraints(actor: User, target: User, new_role: str):
        """检查角色变更约束"""
        if actor.role != SystemRole.ADMIN.value:
            raise BizError("只有系统管理员可以修改角色", code=403)
        if actor.id == target.id:
            raise BizError("禁止修改自己的角色", code=403)

        # 防止移除最后一个管理员
        current_role_value = target.role
        if (current_role_value == SystemRole.ADMIN.value and
                new_role != SystemRole.ADMIN.value and
                UserRepository.count_users_by_role_except_user(SystemRole.ADMIN.value, target.id) == 0):
            raise BizError("不能移除最后一个管理员", code=400)

    @staticmethod
    def _has_actual_changes(target: User, validated_data: dict) -> bool:
        """检查是否有实际变更"""
        new_email = validated_data.get('new_email')
        new_phone = validated_data.get('new_phone')
        new_role = validated_data.get('new_role')
        role_changing = validated_data.get('role_changing', False)

        no_email_change = (new_email is None or new_email == target.email)
        no_phone_change = (new_phone is None or new_phone == target.phone)
        no_role_change = (not role_changing)

        return not (no_email_change and no_phone_change and no_role_change)

    @staticmethod
    def create_user(username: str, password: str, role: str, email: str | None, phone: str | None):
        # 1. 基础校验
        if not username or not password:
            raise BizError("用户名和密码必填", code=400)
        username = username.strip()
        if len(username) < 5:
            raise BizError("用户名长度至少 5 位", code=400)

        # 2. 数据验证和规范化
        validated_data = UserService._validate_and_normalize_profile_data(email, phone, role)

        # 3. 构造实体
        user = User(
            username=username,
            password_hash=hash_password(password),
            email=validated_data.get('new_email'),
            phone=validated_data.get('new_phone'),
            role=validated_data.get('new_role')
        )

        # 5. 持久化
        UserRepository.add(user)
        try:
            UserRepository.commit()
        except IntegrityError as e:
            UserRepository.rollback()
            msg = str(e.orig)
            if "username" in msg:
                raise BizError("用户名已存在", code=409)
            if "email" in msg:
                raise BizError("邮箱已存在", code=409)
            if "phone" in msg:
                raise BizError("手机已存在", code=409)
            raise BizError("唯一性冲突", code=409)
        except SQLAlchemyError:
            UserRepository.rollback()
            raise BizError("数据库错误", code=500)

        return user

    @staticmethod
    def authenticate(username: str, password: str):
        user = UserRepository.find_by_username(username)
        if not user or not user.active:
            return None
        if not verify_password(user.password_hash, password):
            return None
        return user

    @staticmethod
    def list_users(page=1, page_size=20, current_user=None,
                   username=None, roles=None, role_labels=None,
                   email=None, phone=None, active=None,
                   department_id=None):
        return UserRepository.list(
            page=page,
            page_size=page_size,
            current_user=current_user,
            username=username,
            roles=roles,
            role_labels=role_labels,
            email=email,
            phone=phone,
            active=active,
            department_id=department_id
        )

    @staticmethod
    def ensure_default_admin(app):
        uname = app.config["ADMIN_INIT_USERNAME"]
        if not UserRepository.find_by_username(uname):
            user = User(
                username=uname,
                password_hash=hash_password(app.config["ADMIN_INIT_PASSWORD"]),
                email=app.config["ADMIN_INIT_EMAIL"],
                role=SystemRole.ADMIN.value,
                active=True
            )
            db.session.add(user)
            db.session.commit()
            app.logger.info("默认管理员已创建: %s", uname)

    # ======= 新增：更新用户启用 / 禁用状态 =======
    @staticmethod
    def update_user_status(actor: User, target_user_id: int, active: bool) -> User:
        """
        更新指定用户 active 状态（启用/禁用）。
        业务校验：
          - 目标用户存在
          - 仅系统管理员可以修改他人状态
          - 禁止禁用最后一个管理员
          - 禁止用户自禁
          - 幂等：若状态未变化直接返回
        """
        target = UserRepository.find_by_id(target_user_id)
        if not target:
            raise BizError("用户不存在", code=404)

        # 自我禁用保护（可根据需求调整）
        if actor.id == target.id and active is False:
            raise BizError("不能禁用自己", code=400)

        # 角色权限限制：仅系统管理员可操作他人
        if actor.role != SystemRole.ADMIN.value and actor.id != target.id:
            raise BizError("无权操作该用户", code=403)

        # 如果是禁用操作，需要检查是否为最后一个活跃管理员
        if target.role == SystemRole.ADMIN.value and active is False:
            active_admins = UserRepository.count_active_admins()
            # active_admins 包含当前 target（仍是 active True 状态）
            if active_admins <= 1:
                raise BizError("不能禁用最后一个管理员账号", code=400)

        # 幂等处理
        if bool(target.active) == bool(active):
            return target  # 不做写操作

        try:
            UserRepository.update_active(target, active, commit_on_change=True)
        except SQLAlchemyError:
            UserRepository.rollback()
            raise BizError("数据库错误", code=500)

        return target

    @staticmethod
    def update_user_profile(actor: User,
                            target_user_id: int,
                            email: str = None,
                            phone: str = None,
                            role_raw: str = None) -> User:
        """
        更新用户资料（邮箱 / 手机号 / 角色）

        权限：
          - 系统管理员：可改任意用户的邮箱/手机，并可调整他人角色（禁止修改自身角色）
          - 系统操作员：可改除自身外其它用户的邮箱/手机，但无权改角色
          - 其它登录用户：仅可改自己的邮箱/手机

        角色更新附加约束：
          - 仅系统管理员允许
          - 禁止修改自身角色（可按需放开）
          - 防止移除最后一个系统管理员

        幂等：无任何字段实际变更直接返回
        """
        # 1. 获取目标用户
        target = UserRepository.find_by_id(target_user_id)
        if not target:
            raise BizError("用户不存在", code=404)

        # 2. 权限检查
        UserService._check_update_permission(actor, target)

        # 3. 数据验证和规范化
        validated_data = UserService._validate_and_normalize_profile_data(email, phone, role_raw)

        # 4. 角色变更特殊检查
        if validated_data.get('role_changing'):
            UserService._check_role_change_constraints(actor, target, validated_data['new_role'])

        # 5. 唯一性检查
        UserService._check_uniqueness_constraints(target.id, validated_data)

        # 6. 检查是否有实际变更
        if not UserService._has_actual_changes(target, validated_data):
            return target

        # 7. 执行更新
        try:
            UserRepository.update_profile(
                target,
                email=validated_data.get('new_email'),
                phone=validated_data.get('new_phone'),
                role=validated_data.get('new_role'),
                commit=True
            )
        except SQLAlchemyError:
            UserRepository.rollback()
            raise BizError("数据库错误", code=500)

        return target

    @staticmethod
    def reset_password(actor: User, target_user_id: int) -> User:
        """
        重置用户密码为默认值，并返回该明文密码（仅此一次返回）。

        权限：
          - ADMIN 可重置任意用户
          - 其它角色 仅可重置自己的密码

        返回：
          {
            "user_id": int,
            "new_password": "password123",
            "message": "密码已重置，请尽快修改"
          }
        """
        cfg = current_app.config
        default_reset_password = cfg.get("DEFAULT_RESET_PASSWORD")
        target = UserRepository.find_by_id(target_user_id)
        if not target:
            raise BizError("用户不存在", code=404)

        # 权限判断
        if actor.role != SystemRole.ADMIN.value and actor.id != target.id:
            raise BizError("无权限重置该用户密码", code=403)

        new_hash = hash_password(default_reset_password)

        try:
            UserRepository.reset_password_raw(target, new_hash=new_hash, must_change=True, commit=True)
        except SQLAlchemyError:
            UserRepository.rollback()
            raise BizError("数据库错误", code=500)
        # 关键：挂载一次性明文密码
        setattr(target, "_plain_reset_password", default_reset_password)
        return target
