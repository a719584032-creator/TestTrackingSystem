from typing import List, Optional, Tuple

from sqlalchemy import asc, desc, func, select
from sqlalchemy.exc import IntegrityError

from extensions.database import db
from models.device_model import DeviceModel


class DeviceModelRepository:

    @staticmethod
    def create(**kwargs) -> DeviceModel:
        device_model = DeviceModel(**kwargs)
        db.session.add(device_model)
        db.session.flush()
        return device_model

    @staticmethod
    def get_by_id(device_model_id: int, include_inactive: bool = False) -> Optional[DeviceModel]:
        stmt = select(DeviceModel).where(DeviceModel.id == device_model_id)
        if not include_inactive:
            stmt = stmt.where(DeviceModel.active == True)  # noqa: E712
        return db.session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_dept_and_name(department_id: int, name: str) -> Optional[DeviceModel]:
        stmt = select(DeviceModel).where(
            DeviceModel.department_id == department_id,
            DeviceModel.name == name,
            DeviceModel.active == True,  # noqa: E712
        )
        return db.session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list(
        department_id: int,
        name: Optional[str] = None,
        model_code: Optional[str] = None,
        category: Optional[str] = None,
        active: Optional[bool] = True,
        page: int = 1,
        page_size: int = 20,
        order_desc: bool = True,
    ) -> Tuple[List[DeviceModel], int]:
        conditions = [DeviceModel.department_id == department_id]
        if active is not None:
            conditions.append(DeviceModel.active == active)
        if name:
            conditions.append(DeviceModel.name.ilike(f"%{name.strip()}%"))
        if model_code:
            conditions.append(DeviceModel.model_code.ilike(f"%{model_code.strip()}%"))
        if category:
            conditions.append(DeviceModel.category == category)

        stmt = select(DeviceModel).where(*conditions)
        count_stmt = select(func.count(DeviceModel.id)).where(*conditions)

        if order_desc:
            stmt = stmt.order_by(desc(DeviceModel.created_at))
        else:
            stmt = stmt.order_by(asc(DeviceModel.created_at))

        total = db.session.execute(count_stmt).scalar() or 0
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = db.session.execute(stmt).scalars().all()
        return items, total

    @staticmethod
    def update(device_model: DeviceModel, **kwargs) -> DeviceModel:
        for field, value in kwargs.items():
            if value is not None:
                setattr(device_model, field, value)
        db.session.flush()
        return device_model

    @staticmethod
    def commit():
        try:
            db.session.commit()
        except IntegrityError as exc:  # pragma: no cover - pass through for service handling
            db.session.rollback()
            raise exc

    @staticmethod
    def rollback():
        db.session.rollback()
