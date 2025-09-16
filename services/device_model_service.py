from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError

from models.device_model import DeviceModel
from repositories.department_repository import DepartmentRepository
from repositories.device_model_repository import DeviceModelRepository
from utils.exceptions import BizError
from utils.permissions import assert_user_in_department


class DeviceModelService:

    @staticmethod
    def _ensure_department_exists(department_id: int):
        if not department_id:
            raise BizError("部门ID不能为空")
        dept = DepartmentRepository.get_by_id(department_id)
        if not dept:
            raise BizError("部门不存在", 404)
        return dept

    @staticmethod
    def create(
        *,
        department_id: int,
        name: str,
        user,
        category: Optional[str] = None,
        model_code: Optional[str] = None,
        vendor: Optional[str] = None,
        firmware_version: Optional[str] = None,
        description: Optional[str] = None,
        attributes_json: Optional[dict] = None,
    ) -> DeviceModel:
        DeviceModelService._ensure_department_exists(department_id)
        assert_user_in_department(department_id, user)

        if not name:
            raise BizError("机型名称不能为空")

        existing = DeviceModelRepository.get_by_dept_and_name(department_id, name)
        if existing:
            raise BizError("同部门下已存在同名机型")

        try:
            device_model = DeviceModelRepository.create(
                department_id=department_id,
                name=name.strip(),
                category=category.strip() if category else None,
                model_code=model_code.strip() if model_code else None,
                vendor=vendor.strip() if vendor else None,
                firmware_version=firmware_version.strip() if firmware_version else None,
                description=description,
                attributes_json=attributes_json,
                active=True,
            )
            DeviceModelRepository.commit()
        except IntegrityError:
            raise BizError("创建机型失败：唯一约束冲突")

        return device_model

    @staticmethod
    def get(device_model_id: int, user, *, include_inactive: bool = True) -> DeviceModel:
        device_model = DeviceModelRepository.get_by_id(
            device_model_id, include_inactive=include_inactive
        )
        if not device_model:
            raise BizError("机型不存在", 404)
        assert_user_in_department(device_model.department_id, user)
        return device_model

    @staticmethod
    def list(
        *,
        department_id: int,
        user,
        name: Optional[str] = None,
        model_code: Optional[str] = None,
        category: Optional[str] = None,
        active: Optional[bool] = True,
        page: int = 1,
        page_size: int = 20,
        order_desc: bool = True,
    ) -> Tuple[List[DeviceModel], int]:
        DeviceModelService._ensure_department_exists(department_id)
        assert_user_in_department(department_id, user)

        return DeviceModelRepository.list(
            department_id=department_id,
            name=name,
            model_code=model_code,
            category=category,
            active=active,
            page=page,
            page_size=page_size,
            order_desc=order_desc,
        )

    @staticmethod
    def update(
        device_model_id: int,
        user,
        *,
        name: Optional[str] = None,
        category: Optional[str] = None,
        model_code: Optional[str] = None,
        vendor: Optional[str] = None,
        firmware_version: Optional[str] = None,
        description: Optional[str] = None,
        attributes_json: Optional[dict] = None,
    ) -> DeviceModel:
        device_model = DeviceModelService.get(device_model_id, user, include_inactive=True)

        if name and name.strip() != device_model.name:
            existing = DeviceModelRepository.get_by_dept_and_name(device_model.department_id, name.strip())
            if existing and existing.id != device_model.id:
                raise BizError("同部门下已存在同名机型")

        try:
            DeviceModelRepository.update(
                device_model,
                name=name.strip() if name else None,
                category=category.strip() if category else None,
                model_code=model_code.strip() if model_code else None,
                vendor=vendor.strip() if vendor else None,
                firmware_version=firmware_version.strip() if firmware_version else None,
                description=description,
                attributes_json=attributes_json,
            )
            DeviceModelRepository.commit()
        except IntegrityError:
            raise BizError("更新机型失败：唯一约束冲突")

        return device_model

    @staticmethod
    def set_active(device_model_id: int, user, active: bool) -> DeviceModel:
        device_model = DeviceModelService.get(device_model_id, user, include_inactive=True)

        if device_model.active == active:
            return device_model

        if active:
            existing = DeviceModelRepository.get_by_dept_and_name(
                device_model.department_id, device_model.name
            )
            if existing and existing.id != device_model.id:
                raise BizError("同部门下已存在同名机型")

        DeviceModelRepository.update(device_model, active=active)
        DeviceModelRepository.commit()

        return device_model

