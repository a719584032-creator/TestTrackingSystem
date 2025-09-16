from flask import Blueprint, request

from constants.roles import Role
from controllers.auth_helpers import auth_required
from services.device_model_service import DeviceModelService
from utils.exceptions import BizError
from utils.permissions import get_current_user
from utils.response import json_response


device_model_bp = Blueprint("device_model", __name__, url_prefix="/api/device-models")


@device_model_bp.errorhandler(BizError)
def _biz_error(e: BizError):
    return json_response(code=e.code, message=e.message, data=e.data), e.code


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


@device_model_bp.post("")
@auth_required(roles=[Role.ADMIN, Role.DEPT_ADMIN])
def create_device_model():
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    attributes_json = data.get("attributes_json")
    if attributes_json is not None and not isinstance(attributes_json, dict):
        return json_response(code=400, message="attributes_json 必须为对象")

    device_model = DeviceModelService.create(
        department_id=data.get("department_id"),
        name=data.get("name"),
        user=user,
        category=data.get("category"),
        model_code=data.get("model_code"),
        vendor=data.get("vendor"),
        firmware_version=data.get("firmware_version"),
        description=data.get("description"),
        attributes_json=attributes_json,
    )
    return json_response(message="创建成功", data=device_model.to_dict())


@device_model_bp.get("")
@auth_required()
def list_device_models():
    user = get_current_user()
    args = request.args

    department_id = args.get("department_id", type=int)
    if not department_id:
        return json_response(code=400, message="department_id 不能为空")

    active_param = args.get("active")
    active = _parse_bool(active_param) if active_param is not None else True

    page = args.get("page", default=1, type=int)
    page_size = args.get("page_size", default=20, type=int)
    order_desc = args.get("order", "desc").lower() != "asc"

    items, total = DeviceModelService.list(
        department_id=department_id,
        user=user,
        name=args.get("name"),
        model_code=args.get("model_code"),
        category=args.get("category"),
        active=active,
        page=page,
        page_size=page_size,
        order_desc=order_desc,
    )

    return json_response(
        data={
            "items": [item.to_dict() for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@device_model_bp.get("/<int:device_model_id>")
@auth_required()
def get_device_model(device_model_id: int):
    user = get_current_user()
    device_model = DeviceModelService.get(device_model_id, user)
    return json_response(data=device_model.to_dict())


@device_model_bp.put("/<int:device_model_id>")
@auth_required(roles=[Role.ADMIN, Role.DEPT_ADMIN])
def update_device_model(device_model_id: int):
    user = get_current_user()
    data = request.get_json(silent=True) or {}

    attributes_json = data.get("attributes_json")
    if attributes_json is not None and not isinstance(attributes_json, dict):
        return json_response(code=400, message="attributes_json 必须为对象")

    if "active" in data:
        return json_response(code=400, message="active 字段请通过启用/停用接口修改")

    device_model = DeviceModelService.update(
        device_model_id,
        user,
        name=data.get("name"),
        category=data.get("category"),
        model_code=data.get("model_code"),
        vendor=data.get("vendor"),
        firmware_version=data.get("firmware_version"),
        description=data.get("description"),
        attributes_json=attributes_json,
    )
    return json_response(message="更新成功", data=device_model.to_dict())


@device_model_bp.post("/<int:device_model_id>/enable")
@auth_required(roles=[Role.ADMIN, Role.DEPT_ADMIN])
def enable_device_model(device_model_id: int):
    user = get_current_user()
    device_model = DeviceModelService.set_active(device_model_id, user, True)
    return json_response(message="启用成功", data=device_model.to_dict())


@device_model_bp.post("/<int:device_model_id>/disable")
@auth_required(roles=[Role.ADMIN, Role.DEPT_ADMIN])
def disable_device_model(device_model_id: int):
    user = get_current_user()
    device_model = DeviceModelService.set_active(device_model_id, user, False)
    return json_response(message="停用成功", data=device_model.to_dict())
