from flask import Blueprint, request
from utils.response import json_response
from utils.exceptions import BizError
from services.project_service import ProjectService
from controllers.auth_helpers import auth_required, require_department_role
from constants.department_roles import DepartmentRole
from utils.permissions import get_current_user, get_permission_scope


project_bp = Blueprint("project", __name__, url_prefix="/api/projects")


@project_bp.errorhandler(BizError)
def _biz_error(e: BizError):
    return json_response(code=e.code, message=e.message), e.code


@project_bp.post("")
@auth_required()
@require_department_role(
    lambda *_args, **_kwargs: (request.get_json(silent=True) or {}).get("department_id"),
    role=DepartmentRole.ADMIN,
)
def create_project():
    data = request.get_json(silent=True) or {}
    project = ProjectService.create(
        department_id=data.get("department_id"),
        name=data.get("name"),
        code=data.get("code"),
        description=data.get("description"),
        owner_user_id=data.get("owner_user_id"),
        permission_scope=get_permission_scope(),
    )
    return json_response(message="创建成功", data=project.to_dict())


@project_bp.get("")
@auth_required()
def list_projects():
    scope = get_permission_scope()
    args = request.args
    department_id = args.get("department_id", type=int)
    name = args.get("name")
    code = args.get("code")
    status = args.get("status")
    page = args.get("page", default=1, type=int)
    page_size = args.get("page_size", default=20, type=int)
    order_desc = args.get("order", "desc").lower() != "asc"
    items, total = ProjectService.list(
        department_id=department_id,
        name=name,
        code=code,
        status=status,
        page=page,
        page_size=page_size,
        order_desc=order_desc,
        permission_scope=scope,
    )
    return json_response(
        data={
            "items": [i.to_dict() for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@project_bp.get("/<int:project_id>")
@auth_required()
def get_project(project_id: int):
    project = ProjectService.get(project_id, permission_scope=get_permission_scope())
    return json_response(data=project.to_dict())


@project_bp.put("/<int:project_id>")
@auth_required()
def update_project(project_id: int):
    scope = get_permission_scope()
    data = request.get_json(silent=True) or {}
    project = ProjectService.update(
        project_id,
        name=data.get("name"),
        code=data.get("code"),
        description=data.get("description"),
        status=data.get("status"),
        owner_user_id=data.get("owner_user_id"),
        permission_scope=scope,
    )
    return json_response(message="更新成功", data=project.to_dict())


@project_bp.delete("/<int:project_id>")
@auth_required()
def delete_project(project_id: int):
    user = get_current_user()
    ProjectService.delete(
        project_id,
        user_id=user.id if user else None,
        permission_scope=get_permission_scope(),
    )
    return json_response(message="删除成功")
