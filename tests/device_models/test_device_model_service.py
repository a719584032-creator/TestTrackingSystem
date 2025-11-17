# -*- coding: utf-8 -*-
import uuid
import pytest

# 说明：
# - 所有修改/管理接口使用 admin 鉴权（沿用 conftest.py 的 api_client fixture）
# - 部门 ID 使用 fixed_department_id fixture（固定返回 13）
# - 针对接口约束：attributes_json 必须为对象；active 不能通过 PUT 修改；list 必须携带 department_id

def _rand_suffix(n=6):
    return uuid.uuid4().hex[:n]


@pytest.fixture
def make_device_model(api_client, fixed_department_id):
    """
    工具：创建一个设备模型，返回 data
    """
    def _create(**overrides):
        sfx = _rand_suffix()
        payload = {
            "department_id": fixed_department_id,  # 固定 13
            "name": f"自动化设备_{sfx}",
            "category": "headset",
            "model_code": f"MDL_{sfx}",
            "vendor": "Lenovo",
            "firmware_version": "1.0.0",
            "description": "API 自动化创建",
            "attributes_json": {"color": "black", "anc": True}
        }
        payload.update(overrides)

        resp = api_client.request("POST", "/api/device-models", json_data=payload)
        assert resp.get("_http_status") in (200, 201), f"创建失败: {resp}"
        data = resp.get("data") or {}
        assert data.get("id"), f"响应缺少 id: {resp}"
        assert data.get("department_id") == fixed_department_id, f"department_id 不匹配: {resp}"
        return data
    return _create


# ----------------------- 创建 -----------------------

def test_create_device_model_success(api_client, make_device_model):
    dm = make_device_model()
    assert dm.get("name", "").startswith("自动化设备_")


def test_create_device_model_attributes_json_must_be_object(api_client, fixed_department_id):
    sfx = _rand_suffix()
    resp = api_client.request(
        "POST",
        "/api/device-models",
        json_data={
            "department_id": fixed_department_id,
            "name": f"坏的属性_{sfx}",
            "attributes_json": "NOT_A_DICT"  # 这里应当被拒绝
        }
    )
    assert resp.get("_http_status") == 400, resp
    # 控制器里明确的报错文案
    assert "attributes_json 必须为对象" in (resp.get("message") or ""), resp


# ----------------------- 列表 -----------------------

def test_list_requires_department_id(api_client):
    # 未传 department_id 必须 400
    resp = api_client.request("GET", "/api/device-models", params={})
    assert resp.get("_http_status") == 400, resp
    assert "department_id 不能为空" in (resp.get("message") or ""), resp


def test_list_default_active_true_and_filtering(api_client, make_device_model, fixed_department_id):
    # 创建两个设备模型，其中一个置为 inactive
    active_dm = make_device_model()
    inactive_dm = make_device_model()

    # disable 一个
    dis = api_client.request("POST", f"/api/device-models/{inactive_dm['id']}/disable")
    assert dis.get("_http_status") == 200, dis

    # 1) 不带 active 参数，默认 active=True，应只返回激活的
    lst1 = api_client.request("GET", "/api/device-models", params={"department_id": fixed_department_id})
    assert lst1.get("_http_status") == 200, lst1
    ids1 = [it["id"] for it in lst1.get("data", {}).get("items", [])]
    assert active_dm["id"] in ids1
    assert inactive_dm["id"] not in ids1

    # 2) active=false（兼容字符串 false）
    lst2 = api_client.request(
        "GET",
        "/api/device-models",
        params={"department_id": fixed_department_id, "active": "false"}
    )
    assert lst2.get("_http_status") == 200, lst2
    ids2 = [it["id"] for it in lst2.get("data", {}).get("items", [])]
    assert inactive_dm["id"] in ids2
    assert active_dm["id"] not in ids2

    # 3) active=0 也应识别为 False（控制器使用自定义 _parse_bool）
    lst3 = api_client.request(
        "GET",
        "/api/device-models",
        params={"department_id": fixed_department_id, "active": "0"}
    )
    assert lst3.get("_http_status") == 200, lst3
    ids3 = [it["id"] for it in lst3.get("data", {}).get("items", [])]
    assert inactive_dm["id"] in ids3


# ----------------------- 详情 -----------------------

def test_get_device_model(api_client, make_device_model):
    dm = make_device_model()
    resp = api_client.request("GET", f"/api/device-models/{dm['id']}")
    assert resp.get("_http_status") == 200, resp
    assert resp.get("data", {}).get("id") == dm["id"], resp


# ----------------------- 更新 -----------------------

def test_update_device_model_success(api_client, make_device_model):
    dm = make_device_model()
    new_name = f"{dm['name']}_upd"
    resp = api_client.request(
        "PUT",
        f"/api/device-models/{dm['id']}",
        json_data={
            "name": new_name,
            "vendor": "Lenovo Pro",
            "attributes_json": {"updated": True, "anc": False}
        }
    )
    assert resp.get("_http_status") == 200, resp
    assert resp.get("data", {}).get("name") == new_name, resp
    # attributes_json 返回结构依业务而定，这里不强耦合


def test_update_device_model_cannot_change_active(api_client, make_device_model):
    dm = make_device_model()
    # PUT 不允许修改 active
    resp = api_client.request(
        "PUT",
        f"/api/device-models/{dm['id']}",
        json_data={"active": False}
    )
    assert resp.get("_http_status") == 400, resp
    assert "active 字段请通过启用/停用接口修改" in (resp.get("message") or ""), resp


# ----------------------- 启用 / 停用 -----------------------

def test_enable_disable_toggle_and_verify_by_list(api_client, make_device_model, fixed_department_id):
    dm = make_device_model()

    # 停用
    dis = api_client.request("POST", f"/api/device-models/{dm['id']}/disable")
    assert dis.get("_http_status") == 200, dis

    lst_inactive = api_client.request(
        "GET", "/api/device-models",
        params={"department_id": fixed_department_id, "active": "false"}
    )
    assert lst_inactive.get("_http_status") == 200, lst_inactive
    ids_inactive = [it["id"] for it in lst_inactive.get("data", {}).get("items", [])]
    assert dm["id"] in ids_inactive

    # 启用
    ena = api_client.request("POST", f"/api/device-models/{dm['id']}/enable")
    assert ena.get("_http_status") == 200, ena

    lst_active = api_client.request(
        "GET", "/api/device-models",
        params={"department_id": fixed_department_id}
    )
    assert lst_active.get("_http_status") == 200, lst_active
    ids_active = [it["id"] for it in lst_active.get("data", {}).get("items", [])]
    assert dm["id"] in ids_active


# ----------------------- 鉴权（只做基础 401 校验） -----------------------

def test_auth_required_for_list_and_create(api_client, fixed_department_id):
    # list 未带 token -> 401
    resp_list = api_client.request(
        "GET", "/api/device-models",
        params={"department_id": fixed_department_id},
        attach_token=False
    )
    assert resp_list.get("_http_status") == 401, resp_list

    # create 未带 token -> 401
    sfx = _rand_suffix()
    resp_create = api_client.request(
        "POST", "/api/device-models",
        json_data={
            "department_id": fixed_department_id,
            "name": f"未鉴权_{sfx}"
        },
        attach_token=False
    )
    assert resp_create.get("_http_status") == 401, resp_create
