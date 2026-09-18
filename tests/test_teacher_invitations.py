from datetime import timedelta
import io
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.dependencies import AuthenticatedUser, get_authenticated_user
from app.config import Settings
from app.main import create_app
from app.models import School, Teacher, TeacherRole, utc_now


@pytest.fixture
def invitation_app(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path}/invite.db",
        auth_mode="supabase",
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="sb_publishable_test",
        supabase_secret_key="sb_secret_PRIVATE",
        teacher_invitations_enabled=True,
        teacher_invitation_redirect_url="https://app.example.test/teacher/",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        with app.state.session_factory() as db:
            school = School(name="招待テスト園")
            other_school = School(name="別の園")
            db.add_all([school, other_school])
            db.flush()
            admin = Teacher(
                school_id=school.id,
                name="管理者",
                email="admin@example.com",
                role=TeacherRole.school_admin,
                auth_user_id=str(uuid4()),
            )
            colleague = Teacher(
                school_id=school.id,
                name="先生",
                email="teacher@example.com",
                role=TeacherRole.teacher,
                auth_user_id=str(uuid4()),
            )
            target = Teacher(
                school_id=school.id, name="招待待ち", email="new@example.com"
            )
            foreign = Teacher(
                school_id=other_school.id, name="他園", email="foreign@example.com"
            )
            db.add_all([admin, colleague, target, foreign])
            db.commit()
            ids = {
                "school": school.id,
                "target": target.id,
                "foreign": foreign.id,
                "admin": admin.id,
                "colleague": colleague.id,
            }
            user = AuthenticatedUser(id=admin.auth_user_id, email=admin.email)
        app.dependency_overrides[get_authenticated_user] = lambda: user
        yield app, client, ids


def test_invite_uses_stored_email_and_server_secret_and_resend_cooldown(
    invitation_app, monkeypatch
):
    app, client, ids = invitation_app
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(
            200,
            json={
                "id": "provider-user",
                "email": "private-provider-response",
                "token": "HIDDEN",
            },
        )

    monkeypatch.setattr("app.teacher_invitations.httpx.post", post)
    endpoint = f"/api/v1/teachers/{ids['target']}/invite"
    response = client.post(endpoint)
    assert response.status_code == 200
    assert response.json()["invitation_sent_at"] is not None
    assert response.json()["is_auth_linked"] is False
    assert calls[0][0] == "https://example.supabase.co/auth/v1/invite"
    assert calls[0][1]["headers"]["apikey"] == "sb_secret_PRIVATE"
    assert "Authorization" not in calls[0][1]["headers"]
    assert calls[0][1]["json"] == {"email": "new@example.com"}
    assert calls[0][1]["params"] == {"redirect_to": "https://app.example.test/teacher/"}
    assert calls[0][1]["follow_redirects"] is False
    assert client.post(endpoint).status_code == 429
    assert len(calls) == 1
    config = client.get("/api/v1/auth/config")
    assert config.json()["teacher_invitations_enabled"] is True
    assert "sb_secret_PRIVATE" not in config.text + response.text
    assert "HIDDEN" not in response.text
    assert "supabase_secret_key" not in app.state.settings.model_dump()
    with app.state.session_factory() as db:
        target = db.get(Teacher, ids["target"])
        target.invitation_attempted_at = utc_now() - timedelta(seconds=61)
        db.commit()
    assert client.post(endpoint).status_code == 200
    assert len(calls) == 2


@pytest.mark.parametrize(
    "status,code,expected",
    [(503, None, 503), (429, None, 429), (422, "email_exists", 409), (302, None, 503)],
)
def test_provider_failure_keeps_teacher_and_does_not_expose_payload(
    invitation_app, monkeypatch, status, code, expected
):
    app, client, ids = invitation_app
    monkeypatch.setattr(
        "app.teacher_invitations.httpx.post",
        lambda *a, **k: httpx.Response(
            status, json={"error_code": code, "message": "PRIVATE_PROVIDER_DETAIL"}
        ),
    )
    response = client.post(f"/api/v1/teachers/{ids['target']}/invite")
    assert response.status_code == expected
    assert "PRIVATE_PROVIDER_DETAIL" not in response.text
    with app.state.session_factory() as db:
        teacher = db.get(Teacher, ids["target"])
        assert teacher is not None and teacher.invitation_sent_at is None
        assert teacher.invitation_attempted_at is not None


def test_timeout_keeps_reservation_without_exception_text(invitation_app, monkeypatch):
    app, client, ids = invitation_app

    def timeout(*a, **k):
        raise httpx.ConnectError("PRIVATE_URL_AND_KEY")

    monkeypatch.setattr("app.teacher_invitations.httpx.post", timeout)
    endpoint = f"/api/v1/teachers/{ids['target']}/invite"
    response = client.post(endpoint)
    assert response.status_code == 503 and "PRIVATE_URL_AND_KEY" not in response.text
    assert client.post(endpoint).status_code == 429


def test_invite_rejects_other_school_teacher_and_disabled_or_linked_targets(
    invitation_app, monkeypatch
):
    app, client, ids = invitation_app
    post = lambda *a, **k: pytest.fail("Denied requests must not contact Supabase")
    monkeypatch.setattr("app.teacher_invitations.httpx.post", post)
    assert client.post(f"/api/v1/teachers/{ids['foreign']}/invite").status_code == 403
    assert client.post(f"/api/v1/teachers/{ids['admin']}/invite").status_code == 409
    with app.state.session_factory() as db:
        target = db.get(Teacher, ids["target"])
        target.is_active = False
        db.commit()
        colleague = db.get(Teacher, ids["colleague"])
        user = AuthenticatedUser(id=colleague.auth_user_id, email=colleague.email)
    assert client.post(f"/api/v1/teachers/{ids['target']}/invite").status_code == 409
    app.dependency_overrides[get_authenticated_user] = lambda: user
    assert client.post(f"/api/v1/teachers/{ids['target']}/invite").status_code == 403


def test_disabled_feature_rejects_send(invitation_app, monkeypatch):
    app, client, ids = invitation_app
    app.state.settings.teacher_invitations_enabled = False
    monkeypatch.setattr(
        "app.teacher_invitations.httpx.post", lambda *a, **k: pytest.fail("disabled")
    )
    assert client.post(f"/api/v1/teachers/{ids['target']}/invite").status_code == 503


def test_unsafe_configuration_is_rejected_without_printing_key():
    with pytest.raises(ValueError) as error:
        Settings(
            _env_file=None,
            teacher_invitations_enabled=True,
            auth_mode="supabase",
            supabase_secret_key="sb_secret_PRIVATE",
            supabase_url="http://unsafe.test",
            teacher_invitation_redirect_url="https://app.test/teacher/",
        )
    assert "sb_secret_PRIVATE" not in str(error.value)


def test_invitation_migration_preserves_existing_teacher(tmp_path):
    from alembic import command
    from app.database import create_database_engine
    from app.database_migrations import build_alembic_config

    url = f"sqlite:///{tmp_path}/migration.db"
    config = build_alembic_config(url)
    command.upgrade(config, "0027_school_trial_mode")
    engine = create_database_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO teachers (id, school_id, name, role, is_active, email, created_at) VALUES ('old', 'school', 'Existing', 'teacher', 1, 'old@example.com', CURRENT_TIMESTAMP)"
            )
        )
    command.upgrade(config, "head")
    with engine.connect() as conn:
        assert conn.execute(
            text(
                "SELECT name, invitation_attempted_at, invitation_sent_at FROM teachers WHERE id='old'"
            )
        ).one() == ("Existing", None, None)
    engine.dispose()


def test_invitation_migration_preserves_postgresql_permissions():
    from alembic import command
    from app.database_migrations import build_alembic_config

    output = io.StringIO()
    config = build_alembic_config("postgresql://example:unused@localhost/example")
    config.output_buffer = output
    command.upgrade(config, "0027_school_trial_mode:0028_teacher_invitations", sql=True)
    sql = output.getvalue()
    assert (
        "ALTER TABLE teachers ADD COLUMN invitation_attempted_at TIMESTAMP WITH TIME ZONE"
        in sql
    )
    assert (
        "ALTER TABLE teachers ADD COLUMN invitation_sent_at TIMESTAMP WITH TIME ZONE"
        in sql
    )
    assert "GRANT" not in sql and "ROW LEVEL SECURITY" not in sql and "DROP" not in sql
