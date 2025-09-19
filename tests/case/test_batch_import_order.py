from types import SimpleNamespace

from constants.test_case import TestCasePriority, TestCaseType
from services.test_case_service import TestCaseService


def test_batch_import_creates_cases_in_reverse_order(monkeypatch):
    department_id = 42
    user = SimpleNamespace(id=7)

    cases_data = [
        {"title": "case-1"},
        {"title": "case-2"},
        {"title": "case-3"},
    ]

    created_titles = []

    def fake_create(*, department_id, title, created_by, **kwargs):
        created_titles.append(title)
        return SimpleNamespace(
            id=len(created_titles),
            title=title,
            department_id=department_id,
            group_id=kwargs.get("group_id"),
            priority=kwargs.get("priority") or TestCasePriority.P2.value,
            case_type=kwargs.get("case_type") or TestCaseType.FUNCTIONAL.value,
            status="active",
            version=1,
            created_at=None,
        )

    monkeypatch.setattr(
        TestCaseService,
        "create",
        staticmethod(fake_create),
    )
    monkeypatch.setattr(
        "services.test_case_service.assert_user_in_department",
        lambda dept_id, user: None,
    )

    result = TestCaseService.batch_import(
        department_id=department_id,
        cases_data=cases_data,
        user=user,
    )

    assert created_titles == ["case-3", "case-2", "case-1"]

    returned_titles = [case.title for case in result["created"]]
    assert returned_titles == ["case-1", "case-2", "case-3"]
    assert result["errors"] == []
