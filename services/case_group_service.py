import copy
from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, Any, List
from extensions.database import db
from utils.exceptions import BizError
from utils.permissions import assert_user_in_department
from repositories.case_group_repository import CaseGroupRepository
from models.case_group import CaseGroup
from models.test_case import TestCase
from models.test_case_history import TestCaseHistory
from constants.test_case import TestCaseStatus
import logging

logger = logging.getLogger(__name__)


class CaseGroupService:

    @staticmethod
    def _build_path(parent: Optional[CaseGroup], name: str) -> str:
        if parent:
            return f"{parent.path}/{name}"
        return f"root/{name}"

    @staticmethod
    def get(group_id: int, user) -> CaseGroup:
        group = CaseGroupRepository.get_by_id(group_id)
        if not group:
            raise BizError("分组不存在", 404)
        assert_user_in_department(group.department_id, user)
        return group

    @staticmethod
    def get_or_create_by_name(
        department_id: int,
        name: str,
        user,
        parent_id: Optional[int] = None,
        order_no: int = 0
    ) -> CaseGroup:
        """根据名称获取或创建分组"""
        assert_user_in_department(department_id, user)
        existing = CaseGroupRepository.get_by_name_under_parent(department_id, parent_id, name)
        if existing:
            return existing
        return CaseGroupService.create(
            department_id=department_id,
            name=name,
            user=user,
            parent_id=parent_id,
            order_no=order_no
        )

    @staticmethod
    def create(department_id: int, name: str, user, parent_id: Optional[int] = None, order_no: int = 0) -> CaseGroup:
        assert_user_in_department(department_id, user)

        parent = None
        if parent_id:
            parent = CaseGroupRepository.get_by_id(parent_id)
            if not parent:
                raise BizError("父分组不存在", 404)
            if parent.department_id != department_id:
                raise BizError("父分组不在该部门下", 400)

        # 同级重名校验
        if CaseGroupRepository.exists_name_under_parent(department_id, parent_id, name):
            raise BizError("同级已存在同名分组", 400)

        path = CaseGroupService._build_path(parent, name)

        group = CaseGroupRepository.create(
            department_id=department_id,
            parent_id=parent.id if parent else None,
            name=name,
            path=path,
            order_no=order_no,
            created_by=user.id,
            updated_by=user.id
        )
        db.session.commit()
        return group

    @staticmethod
    def update(group_id: int, user, name: Optional[str] = None, parent_id: Optional[int] = None):
        group = CaseGroupService.get(group_id, user)

        # 如果两者都未传且没有变化
        if name is None and parent_id is None:
            return group

        new_parent = None
        if parent_id is not None:
            logger.debug(f'parent_id is {parent_id}')
            if parent_id == 0:
                new_parent = None
            else:
                new_parent = CaseGroupRepository.get_by_id(parent_id)
                if not new_parent:
                    raise BizError("新的父分组不存在", 404)
                if new_parent.department_id != group.department_id:
                    raise BizError("新的父分组不在同一部门", 400)
                # 循环检测：不能移动到自身或后代
                descendant_ids = CaseGroupRepository.get_descendant_ids_inclusive(group)
                if new_parent.id in descendant_ids:
                    raise BizError("不能将分组移动到其自身或子分组下", 400)
        else:
            # 如果没传 parent_id，就保留现有父节点
            new_parent = group.parent

        # 校验同级重名
        target_parent_id = new_parent.id if new_parent else None
        target_name = name if name is not None else group.name
        if CaseGroupRepository.exists_name_under_parent(group.department_id, target_parent_id, target_name,
                                                        exclude_id=group.id):
            raise BizError("同级已存在同名分组", 400)

        old_path = group.path
        update_parent = parent_id is not None  # 只有传了才更新
        logger.debug(f'update_parent is {update_parent}')
        changed = CaseGroupRepository.update_group_parent_and_name(group, new_parent, name, update_parent)
        if changed:
            # 先计算新路径
            new_path = CaseGroupService._build_path(new_parent, group.name)
            group.path = new_path
            group.updated_by = user.id

            # ✅ 用旧 path 查询子孙
            descendants = CaseGroupRepository.get_descendants_by_path_prefix(group.department_id, old_path)

            if descendants:
                updates = []
                for d in descendants:
                    # old_path/xxx => new_path/xxx
                    suffix = d.path[len(old_path) + 1:]  # 去掉 old_path + '/'
                    new_child_path = f"{group.path}/{suffix}"
                    updates.append((d.id, new_child_path))
                CaseGroupRepository.bulk_update_paths(updates)

            db.session.commit()

        return group

    @staticmethod
    def delete(group_id: int, user) -> int:
        group = CaseGroupService.get(group_id, user)

        # 收集所有后代（含自身）
        group_ids = CaseGroupRepository.get_descendant_ids_inclusive(group)

        logger.debug(f'group_ids is {group_ids}')

        # 收集所有测试用例 id
        case_ids = CaseGroupRepository.collect_test_case_ids_by_group_ids(group_ids)

        from services.test_case_service import TestCaseService  # 避免循环导入
        deleted_case_count = 0

        # 删除测试用例
        if case_ids:
            deleted_case_count = TestCaseService.batch_delete(
                case_ids=case_ids,
                department_id=group.department_id,
                user=user
            )

        # 删除分组（软删除）
        CaseGroupRepository.delete_groups_soft(group_ids, department_id=group.department_id, user_id=user.id)

        return deleted_case_count

    @staticmethod
    def copy(group_id: int, user, target_parent_id: Optional[int] = None, new_name: Optional[str] = None) -> Dict[str, Any]:
        source_group = CaseGroupService.get(group_id, user)

        target_parent = None
        if target_parent_id:
            target_parent = CaseGroupRepository.get_by_id(target_parent_id)
            if not target_parent:
                raise BizError("目标父分组不存在", 404)
            if target_parent.department_id != source_group.department_id:
                raise BizError("目标父分组不在同一部门", 400)

            forbidden = CaseGroupRepository.get_descendant_ids_inclusive(source_group)
            if target_parent.id in forbidden:
                raise BizError("不能复制到原分组或其子分组下", 400)

        root_new_name = new_name or f"{source_group.name}_副本"

        parent_id_for_check = target_parent.id if target_parent else None
        if CaseGroupRepository.exists_name_under_parent(
            source_group.department_id, parent_id_for_check, root_new_name
        ):
            raise BizError("目标父分组下已存在同名分组", 400)

        # 准备所有原树分组
        descendants = CaseGroupRepository.get_descendants(source_group)
        all_groups = [source_group] + descendants
        all_groups.sort(key=lambda g: g.path.count("/"))

        old_id_to_new: Dict[int, int] = {}
        new_groups_by_old_id: Dict[int, CaseGroup] = {}
        created_groups: List[CaseGroup] = []
        created_cases: List[TestCase] = []

        # === 1. 先复制根节点 ===
        new_root = CaseGroupRepository.create(
            department_id=source_group.department_id,
            parent_id=target_parent.id if target_parent else None,
            name=root_new_name,
            path=CaseGroupService._build_path(target_parent, root_new_name),
            order_no=source_group.order_no,
            created_by=user.id,
            updated_by=user.id
        )

        old_id_to_new[int(source_group.id)] = int(new_root.id)
        new_groups_by_old_id[int(source_group.id)] = new_root
        created_groups.append(new_root)

        # === 2. 复制其余子分组 ===
        for g in all_groups:
            if g.id == source_group.id:
                continue

            old_parent_id = int(g.parent_id) if g.parent_id is not None else None
            if old_parent_id is not None and old_parent_id not in old_id_to_new:
                logger.error(
                    f"复制异常: g.id={g.id}, g.name={g.name}, old_parent_id={old_parent_id}, 已映射={list(old_id_to_new.keys())}"
                )
                raise BizError("复制结构异常：父分组未找到映射", 500)

            new_parent = new_groups_by_old_id.get(old_parent_id)

            clone = CaseGroupRepository.create(
                department_id=g.department_id,
                parent_id=new_parent.id if new_parent else None,
                name=g.name,
                path=CaseGroupService._build_path(new_parent, g.name),
                order_no=g.order_no,
                created_by=user.id,
                updated_by=user.id
            )

            old_id_to_new[int(g.id)] = int(clone.id)
            new_groups_by_old_id[int(g.id)] = clone
            created_groups.append(clone)

        # === 3. 复制测试用例 ===
        group_ids = [int(g.id) for g in all_groups]
        test_cases_by_group: Dict[int, List[TestCase]] = defaultdict(list)
        if group_ids:
            tc_query = TestCase.query.filter(
                TestCase.department_id == source_group.department_id,
                TestCase.group_id.in_(group_ids)
            )
            if hasattr(TestCase, "is_deleted"):
                tc_query = tc_query.filter(TestCase.is_deleted.is_(False))

            for tc in tc_query:
                test_cases_by_group[int(tc.group_id)].append(tc)

        new_test_cases: List[TestCase] = []
        histories: List[TestCaseHistory] = []

        for g in all_groups:
            original_group_id = int(g.id)
            tc_list = test_cases_by_group.get(original_group_id)
            if not tc_list:
                continue

            new_group = new_groups_by_old_id.get(original_group_id)
            if not new_group:
                logger.error(
                    f"复制异常: 未找到原分组 {original_group_id} 的新分组映射"
                )
                raise BizError("复制结构异常：未找到目标分组", 500)

            for tc in tc_list:
                new_tc = TestCase(
                    department_id=tc.department_id,
                    group_id=new_group.id,
                    title=tc.title,
                    preconditions=tc.preconditions,
                    steps=copy.deepcopy(tc.steps) if tc.steps else [],
                    expected_result=tc.expected_result,
                    keywords=copy.deepcopy(tc.keywords) if tc.keywords else [],
                    priority=tc.priority,
                    status=TestCaseStatus.ACTIVE.value,
                    case_type=tc.case_type,
                    workload_minutes=tc.workload_minutes,
                    created_by=user.id,
                    updated_by=user.id
                )
                db.session.add(new_tc)
                new_test_cases.append(new_tc)

        if new_test_cases:
            db.session.flush()  # 获取 ID 和版本信息
            operated_at = datetime.utcnow()
            for new_tc in new_test_cases:
                histories.append(
                    TestCaseHistory(
                        test_case_id=new_tc.id,
                        version=new_tc.get_version() if hasattr(new_tc, "get_version") else (new_tc.version or 1),
                        title=new_tc.title,
                        preconditions=new_tc.preconditions,
                        steps=new_tc.steps,
                        expected_result=new_tc.expected_result,
                        keywords=new_tc.keywords,
                        priority=new_tc.priority,
                        status=new_tc.status,
                        case_type=new_tc.case_type,
                        workload_minutes=new_tc.workload_minutes,
                        change_type="CREATE",
                        change_summary="创建测试用例",
                        operated_by=user.id,
                        operated_at=operated_at
                    )
                )

            if histories:
                db.session.add_all(histories)

        created_cases.extend(new_test_cases)

        # ⭐确保写入数据库
        db.session.commit()
        return {
            "new_root_group_id": old_id_to_new[int(source_group.id)],
            "group_count": len(created_groups),
            "case_count": len(created_cases)
        }


    @staticmethod
    def tree(department_id: int, user, with_case_count: bool = False) -> Dict[str, Any]:
        assert_user_in_department(department_id, user)

        groups = CaseGroupRepository.list_by_department(department_id)
        id_to_node = {}
        for g in groups:
            id_to_node[g.id] = {
                "id": g.id,
                "name": g.name,
                "path": g.path,
                "parent_id": g.parent_id,
                "order_no": g.order_no,
                "children": []
            }

        # 组装层次
        roots = []
        for g in groups:
            node = id_to_node[g.id]
            if g.parent_id:
                parent_node = id_to_node.get(g.parent_id)
                if parent_node:
                    parent_node["children"].append(node)
            else:
                roots.append(node)

        # 排序
        def sort_children(n):
            n["children"].sort(key=lambda x: (x["order_no"], x["id"]))
            for c in n["children"]:
                sort_children(c)

        for r in roots:
            sort_children(r)

        # 统计用例数量（可选）
        if with_case_count:
            group_ids = [g.id for g in groups]
            counts = CaseGroupRepository.count_cases_grouped(group_ids)
            for gid, node in id_to_node.items():
                node["case_count"] = counts.get(gid, 0)

        # 拼接 root 虚拟节点
        root_node = {
            "id": 0,
            "name": "root",
            "path": "root",
            "parent_id": None,
            "order_no": 0,
            "children": roots
        }
        if with_case_count:
            root_node["case_count"] = sum(n.get("case_count", 0) for n in id_to_node.values())

        return root_node

    @staticmethod
    def list_children(department_id: int, user, parent_id: Optional[int], with_case_count: bool = False):
        assert_user_in_department(department_id, user)

        if parent_id:
            parent = CaseGroupRepository.get_by_id(parent_id)
            if not parent:
                raise BizError("父分组不存在", 404)
            if parent.department_id != department_id:
                raise BizError("父分组不在该部门", 400)
        groups = CaseGroupRepository.list_children(department_id, parent_id)

        result = []
        if with_case_count:
            counts = CaseGroupRepository.count_cases_grouped([g.id for g in groups])
        else:
            counts = {}
        for g in groups:
            item = {
                "id": g.id,
                "name": g.name,
                "path": g.path,
                "parent_id": g.parent_id,
                "order_no": g.order_no
            }
            if with_case_count:
                item["case_count"] = counts.get(g.id, 0)
            result.append(item)
        return result
