from collections.abc import Generator
from dataclasses import dataclass

import httpx
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.edge_keys import hash_edge_api_key
from app.models import EdgeDevice, Teacher, TeacherRole


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str


@dataclass(frozen=True)
class CurrentTeacher:
    """Authenticated teacher context used for school-scoped authorization."""

    user: AuthenticatedUser
    teacher: Teacher | None
    is_development: bool

    @property
    def school_id(self) -> str | None:
        return self.teacher.school_id if self.teacher else None

    @property
    def is_school_admin(self) -> bool:
        return self.is_development or (
            self.teacher is not None and self.teacher.role == TeacherRole.school_admin
        )


@dataclass(frozen=True)
class CurrentEdgeDevice:
    """An active on-premise device authenticated with its own API key."""

    device: EdgeDevice


def get_db(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_authenticated_user(
    request: Request, authorization: str | None = Header(default=None)
) -> AuthenticatedUser:
    """Validate a Supabase access token with the Auth service in production.

    Calling `/auth/v1/user` supports both legacy shared-secret and modern
    asymmetric Supabase JWT signing keys, which keeps first deployment simple.
    """

    settings = request.app.state.settings
    if settings.auth_mode == "development":
        return AuthenticatedUser(id="development-user", email="developer@local.test")

    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase Auth is enabled but SUPABASE_URL or SUPABASE_PUBLISHABLE_KEY is missing",
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token is required")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token is required")

    try:
        response = httpx.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": settings.supabase_publishable_key,
                "Authorization": f"Bearer {token}",
            },
            timeout=5.0,
        )
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase Auth could not be reached",
        ) from error

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token")

    payload = response.json()
    user_id = payload.get("id")
    email = payload.get("email")
    if not isinstance(user_id, str) or not isinstance(email, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Supabase user is incomplete")
    return AuthenticatedUser(id=user_id, email=email.lower())


def get_current_teacher(
    request: Request,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_authenticated_user),
) -> CurrentTeacher:
    if request.app.state.settings.auth_mode == "development":
        return CurrentTeacher(user=user, teacher=None, is_development=True)

    teacher = db.scalar(select(Teacher).where(Teacher.auth_user_id == user.id))
    if teacher is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This Supabase account is not linked to a teacher account",
        )
    return CurrentTeacher(user=user, teacher=teacher, is_development=False)


def get_current_edge_device(
    db: Session = Depends(get_db),
    x_edge_api_key: str | None = Header(default=None, alias="X-Edge-Api-Key"),
) -> CurrentEdgeDevice:
    if not x_edge_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Edge device API key is required")
    device = db.scalar(
        select(EdgeDevice).where(EdgeDevice.api_key_hash == hash_edge_api_key(x_edge_api_key))
    )
    if device is None or not device.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or disabled edge device API key")
    return CurrentEdgeDevice(device=device)


def assert_school_access(current_teacher: CurrentTeacher, school_id: str) -> None:
    if not current_teacher.is_development and current_teacher.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this school is denied")


def assert_school_admin(current_teacher: CurrentTeacher) -> None:
    if not current_teacher.is_school_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="School administrator access is required")


def is_bootstrap_admin(request: Request, user: AuthenticatedUser) -> bool:
    allowed = {
        email.strip().lower()
        for email in request.app.state.settings.supabase_bootstrap_admin_emails.split(",")
        if email.strip()
    }
    return user.email in allowed
