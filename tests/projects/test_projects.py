import uuid
import pytest


@pytest.fixture
def test_project_data(fixed_department_id):
    suffix = uuid.uuid4().hex[:8]
    return {
        "department_id": fixed_department_id,
        "name": f"测试项目_{suffix}",
        "code": f"PRJ_{suffix}",
        "description": "示例项目",
    }


def test_create_project(api_client, test_project_data):
    resp = api_client.request("POST", "/api/projects", json_data=test_project_data)
    assert resp.get("_http_status") in (200, 201)
    data = resp.get("data")
    assert data and data["name"] == test_project_data["name"]


def test_list_projects(api_client, test_project_data):
    api_client.request("POST", "/api/projects", json_data=test_project_data)
    resp = api_client.request(
        "GET", "/api/projects", params={"department_id": test_project_data["department_id"]}
    )
    assert resp.get("_http_status") == 200
    assert "items" in resp.get("data", {})


def test_project_lifecycle(api_client, test_project_data):
    create_resp = api_client.request("POST", "/api/projects", json_data=test_project_data)
    project_id = create_resp.get("data", {}).get("id")
    assert project_id
    detail_resp = api_client.request("GET", f"/api/projects/{project_id}")
    assert detail_resp.get("data", {}).get("id") == project_id
    update_data = {"name": test_project_data["name"] + "_upd"}
    update_resp = api_client.request(
        "PUT", f"/api/projects/{project_id}", json_data=update_data
    )
    assert update_resp.get("data", {}).get("name") == update_data["name"]
    delete_resp = api_client.request("DELETE", f"/api/projects/{project_id}")
    assert delete_resp.get("_http_status") in (200, 204)
    # ensure project is soft deleted
    get_resp = api_client.request("GET", f"/api/projects/{project_id}")
    assert get_resp.get("_http_status") == 404
