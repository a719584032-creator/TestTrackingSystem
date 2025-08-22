# repositories/user_repository.py
from __future__ import annotations
from typing import Optional, List
from datetime import datetime

from models.user import User
from models.department import DepartmentMember, Department
from models.user_password_history import UserPasswordHistory  # 若路径不同请调整
from extensions.database import db
from constants.roles import Role, ROLE_LABELS_ZH


class UserRepository:
    """
    用户与用户密码历史的仓储（数据访问）层。
    说明：
    - 不做业务规则判断（如密码策略、历史去重），仅做纯粹的持久化读写。
    - 默认所有写操作不自动 commit，由上层显式调用 commit()，以便在一个事务中组合多个操作。
    """

    # ========== 原有方法 ==========
    @staticmethod
    def find_by_username(username: str) -> Optional[User]:
        return User.query.filter_by(username=username).first()

    @staticmethod
    def find_by_id(user_id: int) -> Optional[User]:
        return User.query.get(user_id)

    # 兼容可能的旧命名
    get_by_id = find_by_id

    @staticmethod
    def add(user: User):
        db.session.add(user)

    @staticmethod
    def list(page: int,
             page_size: int,
             current_user,
             username=None,
             roles=None,
             role_labels=None,
             email=None,
             phone=None,
             active=None,
             department_id=None):
        """
        返回 (items, total, dept_map)：
          dept_map: { user_id: [部门名称, ...] }
        权限：
          - admin: 全量（可选指定 department_id）
          - dept_admin: 仅自己管理的部门成员；若传 department_id 必须在其管理范围
          - 其他: 仅自己（保持结构，便于将来扩展）
        """

        if current_user is None:
            return [], 0, {}

        q = User.query

        # ---- 权限过滤 ----
        managed_dept_ids = []
        if current_user.role == Role.ADMIN.value:
            if department_id:
                # 限定在特定部门
                subq = db.session.query(DepartmentMember.user_id).filter(
                    DepartmentMember.department_id == department_id
                ).subquery()
                q = q.filter(User.id.in_(subq))
        elif current_user.role == Role.DEPT_ADMIN.value:
            # 找出自己“部门管理员”身份的部门
            managed_dept_ids = [
                r[0] for r in db.session.query(DepartmentMember.department_id).filter(
                    DepartmentMember.user_id == current_user.id,
                    DepartmentMember.role == 'dept_admin'
                ).all()
            ]
            if not managed_dept_ids:
                return [], 0, {}
            # department_id 交集验证
            if department_id:
                if department_id not in managed_dept_ids:
                    return [], 0, {}
                target_ids = [department_id]
            else:
                target_ids = managed_dept_ids
            subq = db.session.query(DepartmentMember.user_id).filter(
                DepartmentMember.department_id.in_(target_ids)
            ).subquery()
            q = q.filter(User.id.in_(subq))
        else:
            # 其他角色：只看自己
            q = q.filter(User.id == current_user.id)

        # ---- 条件构建 ----
        conditions = []

        if username:
            conditions.append(User.username.ilike(f"%{username}%"))
        if email:
            conditions.append(User.email.ilike(f"%{email}%"))
        if phone:
            conditions.append(User.phone.ilike(f"%{phone}%"))

        # roles / role_labels 合并成最终 roles_set (逻辑：并集)
        roles_set = set()
        if roles:
            roles_set.update(r for r in roles if r)
        if role_labels:
            for lbl in role_labels:
                r = ROLE_LABELS_ZH.get(lbl)
                if r:
                    roles_set.add(r)
            # 如果 role_labels 全部找不到匹配，直接返回空
            if role_labels and not roles_set and not roles:
                return [], 0, {}

        if roles_set:
            conditions.append(User.role.in_(list(roles_set)))

        if active is not None:
            conditions.append(User.active.is_(bool(active)))

        if conditions:
            q = q.filter(*conditions)

        # 排序
        q = q.order_by(User.id.desc())

        pagination = q.paginate(page=page, per_page=page_size, error_out=False)
        items = pagination.items
        total = pagination.total

        # ---- 组装部门名称 dept_map ----
        dept_map = {}
        if items:
            user_ids = [u.id for u in items]
            dept_q = db.session.query(
                DepartmentMember.user_id,
                Department.name
            ).join(Department, Department.id == DepartmentMember.department_id).filter(
                DepartmentMember.user_id.in_(user_ids)
            )

            # # 对 dept_admin 只保留其管理范围内的部门名称（避免泄露别的部门名字）
            # if current_user.role == Role.DEPT_ADMIN.value and managed_dept_ids:
            #     dept_q = dept_q.filter(DepartmentMember.department_id.in_(managed_dept_ids))

            rows = dept_q.all()
            for uid, dname in rows:
                dept_map.setdefault(uid, []).append(dname)

        return items, total, dept_map

    @staticmethod
    def commit():
        db.session.commit()

    @staticmethod
    def rollback():
        db.session.rollback()

    # ========== 新增：密码历史相关 ==========
    @staticmethod
    def add_password_history(user_id: int, old_password_hash: str):
        """
        记录用户旧密码 hash。
        不提交事务。
        """
        hist = UserPasswordHistory(user_id=user_id, password_hash=old_password_hash)
        db.session.add(hist)
        return hist

    @staticmethod
    def get_recent_password_histories(user_id: int, limit: int) -> List[UserPasswordHistory]:
        """
        按创建顺序（id 倒序）获取最近 limit 条历史。
        limit <= 0 时返回空列表。
        """
        if limit <= 0:
            return []
        return (UserPasswordHistory.query
                .filter_by(user_id=user_id)
                .order_by(UserPasswordHistory.id.desc())
                .limit(limit)
                .all())

    @staticmethod
    def trim_password_histories(user_id: int, keep: int):
        """
        仅保留最近 keep 条历史记录，删除其余。
        keep <= 0 表示清空全部历史。
        单独 commit（因为常在主事务成功后调用，避免影响主流程）。
        """
        if keep <= 0:
            UserPasswordHistory.query.filter_by(user_id=user_id).delete(synchronize_session=False)
            db.session.commit()
            return

        extra_ids = (UserPasswordHistory.query
                     .with_entities(UserPasswordHistory.id)
                     .filter_by(user_id=user_id)
                     .order_by(UserPasswordHistory.id.desc())
                     .offset(keep)
                     .all())
        if extra_ids:
            ids = [i for (i,) in extra_ids]
            UserPasswordHistory.query.filter(UserPasswordHistory.id.in_(ids)).delete(synchronize_session=False)
            db.session.commit()

    # ========== 新增：密码更新 ==========
    @staticmethod
    def update_password(user: User, new_hash: str, commit_on_change: bool = True):
        """
        更新用户密码相关字段（hash / version / 更新时间）。
        默认不自动提交，除非 commit_on_change=True。
        """
        user.password_hash = new_hash
        user.password_version = (user.password_version or 1) + 1
        user.password_updated_at = datetime.utcnow()
        if commit_on_change:
            db.session.commit()
        return user

    @staticmethod
    def reset_password_raw(user: User,
                           new_hash: str,
                           must_change: bool = True,
                           commit: bool = True):
        """
        管理员 / 自助重置使用：
        - 仅替换 password_hash
        - 不修改 password_version
        - 不更新 password_updated_at（保持原值）
        - 可选设置必须修改标记（如果模型支持）

        注意：如果系统依赖 password_version 使旧 token 失效，
             这里不递增意味着旧 token 仍然有效。
        """
        user.password_hash = new_hash
        if must_change and hasattr(user, "must_change_password"):
            user.must_change_password = True
        if commit:
            db.session.commit()
        return user

    # ========== 可能的扩展点（预留） ==========
    @staticmethod
    def lock_for_update(user_id: int) -> Optional[User]:
        """
        可在需要强一致或并发控制时使用，要求底层数据库支持行级锁（如 MySQL/InnoDB）。
        调用后仍需在事务内（不要提前 commit）。
        """
        return (User.query
                .filter_by(id=user_id)
                .with_for_update()
                .first())

    # ======= 新增：统计活跃管理员数量 =======
    @staticmethod
    def count_active_admins() -> int:
        from constants.roles import Role
        return User.query.filter_by(role=Role.ADMIN, active=True).count()

    # ======= 新增：更新 active 状态 =======
    @staticmethod
    def update_active(user: User, active: bool, commit_on_change: bool = True):
        user.active = bool(active)
        if commit_on_change:
            db.session.commit()
        return user

    @staticmethod
    def find_by_phone(phone: str):
        if not phone:
            return None
        return User.query.filter_by(phone=phone).first()

    @staticmethod
    def update_profile(user: User,
                       email: str = None,
                       phone: str = None,
                       role: str = None,
                       commit: bool = True) -> bool:
        """
        更新用户资料，返回是否有实际变更
        注意：此方法不做业务验证，仅负责数据更新
        """
        changed = False

        if email is not None and user.email != email:
            user.email = email
            changed = True

        if phone is not None and user.phone != phone:
            user.phone = phone
            changed = True

        if role is not None and user.role != role:
            user.role = role
            changed = True

        if changed and commit:
            db.session.commit()

        return changed

    @staticmethod
    def find_by_email(email: str) -> Optional[User]:
        """根据邮箱查找用户"""
        if not email:
            return None
        return User.query.filter_by(email=email).first()

    @staticmethod
    def exists_email_except_user(email: str, exclude_user_id: int) -> bool:
        """检查邮箱是否被其他用户占用"""
        if not email:
            return False
        return User.query.filter(
            User.email == email,
            User.id != exclude_user_id
        ).first() is not None

    @staticmethod
    def exists_phone_except_user(phone: str, exclude_user_id: int) -> bool:
        """检查手机号是否被其他用户占用"""
        if not phone:
            return False
        return User.query.filter(
            User.phone == phone,
            User.id != exclude_user_id
        ).first() is not None

    @staticmethod
    def count_users_by_role(role: str) -> int:
        """统计指定角色的用户数量"""
        return User.query.filter_by(role=role).count()

    @staticmethod
    def count_users_by_role_except_user(role: str, exclude_user_id: int) -> int:
        """统计指定角色的用户数量（排除指定用户）"""
        return User.query.filter(
            User.role == role,
            User.id != exclude_user_id
        ).count()
