"""Create the first school and link the signed-in Supabase user as its administrator."""

from getpass import getpass

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def prompt(label: str) -> str:
    value = input(f"{label}: ").strip()
    if not value:
        raise SystemExit(f"{label} is required")
    return value


def main() -> None:
    settings = Settings()
    if settings.auth_mode != "supabase":
        raise SystemExit("Set AUTH_MODE=supabase in .env before running this script")
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY are required in .env")

    email = prompt("Supabase login email").lower()
    password = getpass("Supabase login password: ")
    school_name = prompt("School name")
    admin_name = prompt("Administrator display name")

    try:
        sign_in = httpx.post(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
            headers={"apikey": settings.supabase_publishable_key},
            json={"email": email, "password": password},
            timeout=10.0,
        )
        sign_in.raise_for_status()
    except httpx.HTTPError as error:
        raise SystemExit(f"Supabase sign-in failed: {error}") from error

    access_token = sign_in.json().get("access_token")
    if not isinstance(access_token, str):
        raise SystemExit("Supabase did not return an access token")

    app = create_app(settings)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/schools",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"name": school_name, "initial_admin_name": admin_name},
        )

    if response.status_code != 201:
        raise SystemExit(f"Initial setup failed ({response.status_code}): {response.json().get('detail')}")
    print("Initial setup complete. The signed-in user is now this school's administrator.")


if __name__ == "__main__":
    main()
