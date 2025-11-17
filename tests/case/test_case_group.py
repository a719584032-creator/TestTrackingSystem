import pytest
import uuid


@pytest.mark.order(10)
def test_create_group_root_and_child(api_client, fixed_department_id, make_group):
    dept_id = fixed_department_id
    model_A = f"模块A_Fixed{uuid.uuid4().hex[:6]}"
    g1 = make_group(dept_id, model_A)
    assert g1["path"].startswith("root/模块A_Fixed")
    assert g1["parent_id"] is None

    model_B = f"子模块A1_Fixed{uuid.uuid4().hex[:6]}"
    g1_child = make_group(dept_id, model_B, parent_id=g1["id"])
    assert g1_child["parent_id"] == g1["id"]
    assert g1_child["path"] == f"{g1['path']}/{model_B}"

    resp = api_client.request("GET", f"/api/case-groups/{g1_child['id']}")
    assert resp["_http_status"] == 200
    assert resp["data"]["path"] == g1_child["path"]


@pytest.mark.order(11)
def test_group_rename_and_move_updates_paths(api_client, fixed_department_id, make_group):
    dept_id = fixed_department_id
    parent = make_group(dept_id, f"ParentFX_{uuid.uuid4().hex[:6]}")
    child1 = make_group(dept_id, f"ChildFX1_{uuid.uuid4().hex[:6]}", parent_id=parent["id"])
    child2 = make_group(dept_id, f"ChildFX2_{uuid.uuid4().hex[:6]}", parent_id=child1["id"])

    new_name = f"ChildFX1_New_{uuid.uuid4().hex[:6]}"
    rename_resp = api_client.request(
        "PUT",
        f"/api/case-groups/{child1['id']}",
        json_data={"name": new_name}
    )
    assert rename_resp["_http_status"] == 200
    new_path_child1 = rename_resp["data"]["path"]
    assert new_path_child1.endswith(f"/{new_name}")

    get_child2 = api_client.request("GET", f"/api/case-groups/{child2['id']}")
    assert get_child2["_http_status"] == 200
    assert new_name in get_child2["data"]["path"]

    move_resp = api_client.request(
        "PUT",
        f"/api/case-groups/{child1['id']}",
        json_data={"parent_id": 0}
    )
    assert move_resp["_http_status"] == 200
    moved_path = move_resp["data"]["path"]
    assert moved_path == f"root/{new_name}"

    get_child2_after = api_client.request("GET", f"/api/case-groups/{child2['id']}")
    assert get_child2_after["_http_status"] == 200
    assert get_child2_after["data"]["path"].startswith(moved_path + "/")


@pytest.mark.order(12)
def test_group_name_conflict(api_client, fixed_department_id, make_group):
    dept_id = fixed_department_id
    name = f"模块AlphaFX{uuid.uuid4().hex[:6]}"
    a = make_group(dept_id, name)
    resp_conflict = api_client.request(
        "POST",
        "/api/case-groups",
        json_data={
            "department_id": dept_id,
            "name": name,
            "parent_id": None
        }
    )
    assert resp_conflict["code"] == 400
    assert resp_conflict["message"] == "同级已存在同名分组", f"应拒绝同级重名: {resp_conflict}"
    b = make_group(dept_id, f"父B_FX{uuid.uuid4().hex[:6]}")
    c = make_group(dept_id, f"模块AlphaFX{uuid.uuid4().hex[:6]}", parent_id=b["id"])
    assert c["parent_id"] == b["id"]


@pytest.mark.order(13)
def test_move_group_to_its_descendant_should_fail(api_client, fixed_department_id, make_group):
    dept_id = fixed_department_id
    g_root = make_group(dept_id, f"GRootFX{uuid.uuid4().hex[:6]}")
    g_mid = make_group(dept_id, f"GMidFX{uuid.uuid4().hex[:6]}", parent_id=g_root["id"])
    g_leaf = make_group(dept_id, f"GLeafFX{uuid.uuid4().hex[:6]}", parent_id=g_mid["id"])

    resp = api_client.request(
        "PUT",
        f"/api/case-groups/{g_root['id']}",
        json_data={"parent_id": g_leaf["id"]}
    )
    assert resp["code"] == 400, f"非法移动应失败: {resp}"


@pytest.mark.order(14)
def test_tree_and_children_structure(api_client, fixed_department_id, make_group):
    dept_id = fixed_department_id
    g1 = make_group(dept_id, f"TreeA_FX{uuid.uuid4().hex[:6]}")
    g2 = make_group(dept_id, f"TreeB_FX{uuid.uuid4().hex[:6]}")
    g1c = make_group(dept_id, f"TreeA_Sub1_FX{uuid.uuid4().hex[:6]}", parent_id=g1["id"])

    tree_resp = api_client.request(
        "GET",
        f"/api/case-groups/department/{dept_id}/tree",
        params={"with_case_count": "true"}
    )
    assert tree_resp["_http_status"] == 200
    tree = tree_resp["data"]
    assert tree["name"] == "root"

    def find(node, name):
        if node.get("name") == name:
            return node
        for c in node.get("children", []):
            r = find(c, name)
            if r:
                return r
        return None

    assert find(tree, "TreeA_Sub1_FX") is not None

    children_resp = api_client.request(
        "GET",
        f"/api/case-groups/department/{dept_id}/children",
        params={"with_case_count": "false"}
    )
    assert children_resp["_http_status"] == 200
    names = [i["name"] for i in children_resp["data"]["items"]]
    assert "TreeA_FX" in names and "TreeB_FX" in names


@pytest.mark.order(15)
def test_delete_group_cascades_cases(api_client, fixed_department_id, make_group, make_test_case):
    dept_id = fixed_department_id
    g_main = make_group(dept_id, f"DelMain_MX{uuid.uuid4().hex[:6]}")
    g_child = make_group(dept_id, f"DelChild_MX{uuid.uuid4().hex[:6]}", parent_id=g_main["id"])

    tc1 = make_test_case(dept_id, g_main["id"], "用例DelFX-1")
    tc2 = make_test_case(dept_id, g_child["id"], "用例DelFX-2")

    del_resp = api_client.request("DELETE", f"/api/case-groups/{g_main['id']}")
    assert del_resp["_http_status"] == 200

    get_tc1 = api_client.request("GET", f"/api/test-cases/{tc1['id']}")
    assert get_tc1["_http_status"] in (404, 400)
    get_tc2 = api_client.request("GET", f"/api/test-cases/{tc2['id']}")
    assert get_tc2["_http_status"] in (404, 400)

    children_root = api_client.request(
        "GET",
        f"/api/case-groups/department/{dept_id}/children"
    )
    remaining_names = [i["name"] for i in children_root["data"]["items"]]
    assert "DelMain_MX" not in remaining_names


@pytest.mark.order(16)
def test_copy_group_recursive(api_client, fixed_department_id, make_group, make_test_case):
    dept_id = fixed_department_id
    copy_root_fx = f"CopyRoot_FX{uuid.uuid4().hex[:6]}"
    copy_child1_fx = f"CopyChild1_FX{uuid.uuid4().hex[:6]}"
    copy_child2_fx = f"CopyChild2_FX{uuid.uuid4().hex[:6]}"
    src_root = make_group(dept_id, copy_root_fx)
    child1 = make_group(dept_id, copy_child1_fx, parent_id=src_root["id"])
    child2 = make_group(dept_id, copy_child2_fx, parent_id=child1["id"])

    make_test_case(dept_id, src_root["id"], "用例-RootFX")
    make_test_case(dept_id, child1["id"], "用例-Child1FX")
    make_test_case(dept_id, child2["id"], "用例-Child2FX")

    copy_resp = api_client.request(
        "POST",
        f"/api/case-groups/{src_root['id']}/copy",
        json_data={"new_name": f"{copy_root_fx}_副本"}
    )
    assert copy_resp["_http_status"] == 200
    data = copy_resp["data"]
    new_root_id = data["new_root_group_id"]
    assert data["group_count"] == 3
    assert data["case_count"] == 3

    new_root_detail = api_client.request("GET", f"/api/case-groups/{new_root_id}")
    assert new_root_detail["_http_status"] == 200
    assert new_root_detail["data"]["name"] == f"{copy_root_fx}_副本"

    children_new_root = api_client.request(
        "GET",
        f"/api/case-groups/department/{dept_id}/children",
        params={"parent_id": new_root_id}
    )
    assert children_new_root["_http_status"] == 200
    names_level1 = [i["name"] for i in children_new_root["data"]["items"]]
    assert copy_child1_fx in names_level1

    copy_child1_id = [i for i in children_new_root["data"]["items"] if i["name"] == copy_child1_fx][0]["id"]
    children_child1 = api_client.request(
        "GET",
        f"/api/case-groups/department/{dept_id}/children",
        params={"parent_id": copy_child1_id}
    )
    assert children_child1["_http_status"] == 200
    assert any(i["name"] == copy_child2_fx for i in children_child1["data"]["items"])

    list_cases = api_client.request(
        "GET",
        f"/api/test-cases/department/{dept_id}",
        params={"title": "用例-RootFX"}
    )
    assert list_cases["_http_status"] == 200
    titles = [i["title"] for i in list_cases["data"]["items"]]
    assert titles.count("用例-RootFX") >= 2


@pytest.mark.order(17)
def test_copy_group_to_specific_parent(api_client, fixed_department_id, make_group):
    dept_id = fixed_department_id
    base_group_fx = f"BaseGroup_FX{uuid.uuid4().hex[:6]}"
    copy_target_fx = f"CopyTarget_FX{uuid.uuid4().hex[:6]}"
    base = make_group(dept_id, base_group_fx)
    parent_target = make_group(dept_id, copy_target_fx)

    copy_resp = api_client.request(
        "POST",
        f"/api/case-groups/{base['id']}/copy",
        json_data={
            "target_parent_id": parent_target["id"],
            "new_name": f"{base_group_fx}_Copy"
        }
    )
    assert copy_resp["_http_status"] == 200
    new_root_id = copy_resp["data"]["new_root_group_id"]

    new_detail = api_client.request("GET", f"/api/case-groups/{new_root_id}")
    assert new_detail["_http_status"] == 200
    assert new_detail["data"]["parent_id"] == parent_target["id"]
    assert new_detail["data"]["path"].startswith(f"{parent_target['path']}/")


@pytest.mark.order(18)
def test_copy_group_name_conflict(api_client, fixed_department_id, make_group):
    dept_id = fixed_department_id
    name = f"CopyConflictA_FX{uuid.uuid4().hex[:6]}"
    a = make_group(dept_id, name)
    make_group(dept_id, f"{name}_副本")
    resp = api_client.request(
        "POST",
        f"/api/case-groups/{a['id']}/copy",
        json_data={}
    )
    assert resp["_http_status"] == 400, f"应因同级名称冲突失败: {resp}"
