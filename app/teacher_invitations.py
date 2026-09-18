"""Server-only Supabase invitation requests; never expose provider payloads."""

import httpx

from app.config import Settings


class TeacherInvitationError(RuntimeError):
    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind


def send_teacher_invitation(settings: Settings, email: str) -> None:
    key = settings.supabase_secret_key.get_secret_value()
    headers = {"apikey": key, "Content-Type": "application/json"}
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {key}"
    try:
        response = httpx.post(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/invite",
            params={"redirect_to": settings.teacher_invitation_redirect_url},
            headers=headers,
            json={"email": email},
            timeout=10.0,
            follow_redirects=False,
        )
    except httpx.HTTPError:
        raise TeacherInvitationError("unavailable") from None
    if response.status_code == 429:
        raise TeacherInvitationError("rate_limited")
    if response.status_code in (400, 422):
        # Only inspect a fixed provider error code, never return its message.
        try:
            code = response.json().get("error_code")
        except (ValueError, AttributeError):
            code = None
        if code in ("email_exists", "user_already_exists"):
            raise TeacherInvitationError("account_exists")
    if not 200 <= response.status_code < 300:
        raise TeacherInvitationError("unavailable")
