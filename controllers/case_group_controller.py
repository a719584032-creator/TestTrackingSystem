from flask import Blueprint, request
from utils.response import json_response
from utils.exceptions import BizError
from controllers.auth_helpers import auth_required
from utils.permissions import get_current_user
from services.case_group_service import CaseGroupService

case_group_bp = Blueprint("case_group", __name__, url_prefix="/api/case-groups")


@case_group_bp.errorhandler(BizError)
def _biz_error(e: BizError):
    return json_response(code=e.code, message=e.message), e.code


@case_group_bp.post("")
@auth_required()
def create_case_group():
    user = get_current_user()
    data = request.get_json() or {}
    department_id = data.get("department_id")
    name = data.get("name")
    parent_id = data.get("parent_id")  # 可能为 null
    order_no = data.get("order_no", 0)

    if not department_id:
        return json_response(code=400, message="部门ID不能为空")
    if not name:
        return json_response(code=400, message="分组名称不能为空")

    group = CaseGroupService.create(
        department_id=department_id,
        name=name,
        user=user,
        parent_id=parent_id,
        order_no=order_no
    )
    return json_response(message="创建成功", data={
        "id": group.id,
        "name": group.name,
        "path": group.path,
        "parent_id": group.parent_id
    })


@case_group_bp.get("/<int:group_id>")
@auth_required()
def get_case_group(group_id: int):
    user = get_current_user()
    group = CaseGroupService.get(group_id, user)
    return json_response(data={
        "id": group.id,
        "name": group.name,
        "path": group.path,
        "parent_id": group.parent_id,
        "department_id": group.department_id,
        "order_no": group.order_no,
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "updated_at": group.updated_at.isoformat() if group.updated_at else None
    })


@case_group_bp.put("/<int:group_id>")
@auth_required()
def update_case_group(group_id: int):
    user = get_current_user()
    data = request.get_json() or {}
    name = data.get("name")
    parent_id = data.get("parent_id")  # 0 => root

    group = CaseGroupService.update(
        group_id=group_id,
        user=user,
        name=name,
        parent_id=parent_id
    )
    return json_response(message="更新成功", data={
        "id": group.id,
        "name": group.name,
        "path": group.path,
        "parent_id": group.parent_id
    })


@case_group_bp.delete("/<int:group_id>")
@auth_required()
def delete_case_group(group_id: int):
    user = get_current_user()
    deleted_case_count = CaseGroupService.delete(group_id, user)
    return json_response(message="删除成功", data={
        "deleted_case_count": deleted_case_count
    })


@case_group_bp.post("/<int:group_id>/copy")
@auth_required()
def copy_case_group(group_id: int):
    user = get_current_user()
    data = request.get_json() or {}
    target_parent_id = data.get("target_parent_id")
    new_name = data.get("new_name")
    result = CaseGroupService.copy(
        group_id=group_id,
        user=user,
        target_parent_id=target_parent_id,
        new_name=new_name
    )
    return json_response(message="复制成功", data=result, code=200)


@case_group_bp.get("/department/<int:department_id>/tree")
@auth_required()
def get_case_group_tree(department_id: int):
    user = get_current_user()
    with_case_count = request.args.get("with_case_count", "false").lower() == "true"
    tree = CaseGroupService.tree(department_id, user, with_case_count=with_case_count)
    return json_response(data=tree)


@case_group_bp.get("/department/<int:department_id>/children")
@auth_required()
def get_case_group_children(department_id: int):
    user = get_current_user()
    parent_id = request.args.get("parent_id", type=int)
    with_case_count = request.args.get("with_case_count", "false").lower() == "true"
    items = CaseGroupService.list_children(department_id, user, parent_id, with_case_count=with_case_count)
    return json_response(data={"items": items})


