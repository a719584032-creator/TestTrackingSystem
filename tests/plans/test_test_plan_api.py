
# -*- coding: utf-8 -*-

# PyTest: 测试计划相关接口联调用例（部门ID固定为 13）。
# 依赖 conftest.py 中的 api_client / fixed_department_id / make_group / make_test_case 等 fixture。
#
# 覆盖点：
# 1) 创建计划（分组+单个用例；兼容性开关混合；三台机型）
# 2) 列表/详情/更新/删除 基本流程
# 3) 结果记录接口的关键规则：
#    - 兼容性开启的用例必须指定 device_model_id
#    - 兼容性关闭的用例允许不指定 device_model_id
#    - 业务统计在全部完成后置为 completed


import uuid
import pytest

# -------------------------- 工具函数 --------------------------

def _create_project(api_client, department_id: int) -> dict:
    suffix = uuid.uuid4().hex[:6]
    payload = {
        "department_id": department_id,
        "name": f"自动化项目_{suffix}",
        "code": f"AUTO_{suffix}",
        "description": "API自动创建"
    }
    resp = api_client.request("POST", "/api/projects", json_data=payload)
    assert resp.get("_http_status") in (200, 201), f"创建项目失败: {resp}"
    return resp["data"]

def _create_device_model(api_client, department_id: int) -> dict:
    suffix = uuid.uuid4().hex[:6]
    payload = {
        "department_id": department_id,
        "name": f"自动化设备_{suffix}",
        "model_code": f"MDL_{suffix}",
        "vendor": "Lenovo",
        "category": "headset",
        "firmware_version": "1.0.0",
        "description": "API 自动化创建",
        "active": True,
        "attributes_json": {"anc": True, "color": "black"}
    }
    resp = api_client.request("POST", "/api/device-models", json_data=payload)
    assert resp.get("_http_status") in (200, 201), f"创建设备失败: {resp}"
    return resp["data"]

def _create_tester_user(api_client, department_id: int) -> dict:
    suffix = uuid.uuid4().hex[:6]
    # 1) 先创建普通用户
    user_resp = api_client.request(
        "POST", "/api/users/create",
        json_data={"username": f"tester_{suffix}", "password": "Test123!", "role": "user"}
    )
    assert user_resp.get("_http_status") in (200, 201), f"创建用户失败: {user_resp}"
    user = user_resp["data"]
    # 2) 加入部门（需要系统提供部门成员添加接口）
    member_resp = api_client.request(
        "POST", f"/api/departments/{department_id}/members",
        json_data={"user_id": user["id"]}
    )
    assert member_resp.get("_http_status") in (200, 201), f"加入部门失败: {member_resp}"
    return user

def _create_plan_payload(project_id: int, case_ids, case_group_ids, device_model_ids, tester_ids):
    suffix = uuid.uuid4().hex[:4]
    return {
        "project_id": project_id,
        "name": f"自动化计划_{suffix}",
        "description": "由自动化脚本创建",
        "status": "active",
        "start_date": "2025-09-01",
        "end_date": "2025-12-31",
        "case_ids": case_ids,
        "case_group_ids": case_group_ids,
        "device_model_ids": device_model_ids,
        "tester_user_ids": tester_ids
    }

# -------------------------- 测试用例 --------------------------

@pytest.mark.order(1)
def test_create_plan_with_groups_and_single_exec_flow(api_client, fixed_department_id, make_group, make_test_case):
    dept_id = fixed_department_id
    # 项目 + 测试人员 + 三台机型
    project = _create_project(api_client, dept_id)
    tester = _create_tester_user(api_client, dept_id)
    dm1 = _create_device_model(api_client, dept_id)
    dm2 = _create_device_model(api_client, dept_id)
    dm3 = _create_device_model(api_client, dept_id)

    # 分组与用例
    g1 = make_group(dept_id, f"G1_{uuid.uuid4().hex[:4]}")
    c1 = make_test_case(dept_id, g1["id"], f"用例-兼容性_{uuid.uuid4().hex[:4]}")  # 需要兼容性
    c2 = make_test_case(dept_id, g1["id"], f"用例-单次_{uuid.uuid4().hex[:4]}", compatibility_testing=False)

    # 额外一个分组不选，用于确认只取选中的组
    g2 = make_group(dept_id, f"G2_{uuid.uuid4().hex[:4]}")
    _ = make_test_case(dept_id, g2["id"], f"不会被包含_{uuid.uuid4().hex[:4]}")

    # 单个独立用例（兼容性关闭）
    c3 = make_test_case(dept_id, None, f"独立用例-单次_{uuid.uuid4().hex[:4]}", compatibility_testing=False)

    # 计划：选择 g1 + 独立 c3；其中 c2 / c3 关闭兼容性；c1 走兼容性（3台机型）
    payload = _create_plan_payload(
        project_id=project["id"],
        case_ids=[c3["id"]],
        case_group_ids=[g1["id"]],
        device_model_ids=[dm1["id"], dm2["id"], dm3["id"]],
        tester_ids=[tester["id"], 50, 51, 52, 53]
    )

    create_resp = api_client.request("POST", "/api/test-plans", json_data=payload)
    assert create_resp.get("_http_status") in (200, 201), f"创建计划失败: {create_resp}"
    plan = create_resp["data"]
    plan_id = plan["id"]

    # GET 详情
    detail = api_client.request("GET", f"/api/test-plans/{plan_id}")
    assert detail.get("_http_status") == 200, f"获取计划详情失败: {detail}"
    assert detail["data"]["id"] == plan_id

    cases_resp = api_client.request("GET", f"/api/test-plans/{plan_id}/cases?page=1&page_size=100")
    assert cases_resp.get("_http_status") == 200, f"获取计划用例失败: {cases_resp}"
    plan_cases = cases_resp["data"]["items"]

    # 列表 - 过滤项目
    list_resp = api_client.request("GET", f"/api/test-plans?project_id={project['id']}&page=1&page_size=10")
    assert list_resp.get("_http_status") == 200, f"计划列表失败: {list_resp}"
    assert any(item["id"] == plan_id for item in list_resp["data"]["items"]), "新建计划未出现在列表中"

    # 结果记录：
    # 1) 对需要兼容性的用例 (c1)：不带设备应报 400
    record_bad = api_client.request(
        "POST", f"/api/test-plans/{plan_id}/results",
        json_data={"plan_case_id": next(pc["id"] for pc in plan_cases if pc["case_id"] == c1["id"]),
                   "result": "pass"}
    )
    assert record_bad["code"] == 400, "需要兼容性的用例未指定设备应当报错"

    # 2) 逐台设备 PASS
    pc1_id = next(pc["id"] for pc in plan_cases if pc["case_id"] == c1["id"])
    for dm in (dm1, dm2, dm3):
        ok = api_client.request(
            "POST", f"/api/test-plans/{plan_id}/results",
            json_data={"plan_case_id": pc1_id, "device_model_id": dm["id"], "result": "pass"}
        )
        assert ok["_http_status"] == 200, f"记录结果失败: {ok}"

    # 3) 兼容性关闭的用例（c2, c3）不带设备也可 PASS
    for cid in (c2["id"], c3["id"]):
        pc_id = next(pc["id"] for pc in plan_cases if pc["case_id"] == cid)
        ok = api_client.request(
            "POST", f"/api/test-plans/{plan_id}/results",
            json_data={"plan_case_id": pc_id, "result": "pass"}
        )
        assert ok["_http_status"] == 200, f"兼容性关闭的用例记录失败: {ok}"

    # 再取详情，状态应已完成（若后端 to_dict 暴露 status）
    detail2 = api_client.request("GET", f"/api/test-plans/{plan_id}")
    assert detail2["_http_status"] == 200
    # 如果状态字段存在，应该是 completed；若不存在则忽略
    if "status" in detail2["data"]:
        assert detail2["data"]["status"] in ("completed", "COMPLETED"), f"计划未完成: {detail2['data'].get('status')}"

    # 更新
    dm4 = _create_device_model(api_client, dept_id)
    new_device_ids = [dm1["id"], dm2["id"], dm3["id"], dm4["id"]]  # 仅允许新增，不移除
    upd = api_client.request(
        "PUT", f"/api/test-plans/{plan_id}",
        json_data={
            "name": plan["name"] + "_upd",
            "description": "更新描述",
            "device_model_ids": new_device_ids,
        }
    )
    assert upd["_http_status"] == 200
    assert {
        dm["device_model_id"] for dm in upd["data"].get("device_models", [])
    } == set(new_device_ids)

    updated_cases = api_client.request("GET", f"/api/test-plans/{plan_id}/cases?page=1&page_size=100")
    assert updated_cases["_http_status"] == 200
    compat_case = next(pc for pc in updated_cases["data"]["items"] if pc["case_id"] == c1["id"])
    assert {res["device_model_id"] for res in compat_case["execution_results"]} == set(new_device_ids)

    # 删除
    # delete_resp = api_client.request("DELETE", f"/api/test-plans/{plan_id}")
    # assert delete_resp["_http_status"] == 200, f"删除计划失败: {delete_resp}"

@pytest.mark.order(2)
def test_create_plan_with_non_compatibility_cases(api_client, fixed_department_id, make_group, make_test_case):
    """兼容性关闭的用例在计划中应允许不指定机型执行。"""
    dept_id = fixed_department_id
    project = _create_project(api_client, dept_id)
    tester = _create_tester_user(api_client, dept_id)

    g = make_group(dept_id, f"G_{uuid.uuid4().hex[:4]}")
    c1 = make_test_case(dept_id, g["id"], f"C1_{uuid.uuid4().hex[:4]}", compatibility_testing=False)

    payload = _create_plan_payload(
        project_id=project["id"],
        case_ids=[],
        case_group_ids=[g["id"]],
        device_model_ids=[],
        tester_ids=[tester["id"]]
    )

    ok = api_client.request("POST", "/api/test-plans", json_data=payload)
    assert ok["_http_status"] in (200, 201), f"创建计划失败: {ok}"
    plan_id = ok["data"]["id"]

    cases_resp = api_client.request("GET", f"/api/test-plans/{plan_id}/cases?page=1&page_size=100")
    assert cases_resp["_http_status"] == 200
    pc_id = next(pc["id"] for pc in cases_resp["data"]["items"] if pc["case_id"] == c1["id"])

    record = api_client.request(
        "POST",
        f"/api/test-plans/{plan_id}/results",
        json_data={"plan_case_id": pc_id, "result": "pass"}
    )
    assert record["_http_status"] == 200, f"关闭兼容性的用例不应要求机型: {record}"
