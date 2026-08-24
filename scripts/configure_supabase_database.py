"""Configure the local backend to use a Supabase Postgres connection.

The script keeps the database password off the screen: it is entered through
the terminal's hidden password prompt and written only to the local .env file.
"""

from __future__ import annotations

import getpass
from pathlib import Path
from urllib.parse import quote, urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
PLACEHOLDER = "[YOUR-PASSWORD]"


def replace_env_value(contents: str, key: str, value: str) -> str:
    """Replace one dotenv value while leaving every other setting untouched."""
    lines = contents.splitlines()
    replacement = f"{key}={value}"
    for index, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[index] = replacement
            break
    else:
        lines.append(replacement)
    return "\n".join(lines) + "\n"


def main() -> None:
    if not ENV_FILE.exists():
        raise SystemExit(".env がありません。先に `cp .env.example .env` を実行してください。")

    print("Supabase の Connect > Direct > Session pooler を開いてください。")
    print("URIをそのまま貼るか、Enterだけを押して Host / User を個別に入力できます。")
    connection_string = input("Connection string（またはEnter）: ").strip()
    if not connection_string:
        print("画面の Connection parameters にある Host と User の右側のコピーアイコンを使います。")
        host = input("Host: ").strip()
        user = input("User: ").strip()
        connection_string = f"postgresql://{user}:{PLACEHOLDER}@{host}:5432/postgres?sslmode=require"
    elif PLACEHOLDER not in connection_string:
        raise SystemExit(
            "URIには [YOUR-PASSWORD] を残してください。個別入力なら、ここでEnterだけを押します。"
        )

    # `[YOUR-PASSWORD]` is convenient for people but its brackets are not
    # valid in a URI password. Use a harmless temporary value only while
    # validating the host and port.
    parsed = urlsplit(connection_string.replace(PLACEHOLDER, "password-placeholder", 1))
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        raise SystemExit("PostgreSQL の接続文字列ではありません。Session pooler の URI を使ってください。")
    if not parsed.hostname.endswith(".pooler.supabase.com") or parsed.port != 5432:
        raise SystemExit("Free プランでは Session pooler（pooler.supabase.com、port 5432）を使ってください。")

    password = getpass.getpass("Database password（画面には表示されません）: ")
    if not password:
        raise SystemExit("Database password は空にできません。")
    if password != getpass.getpass("Database password（確認）: "):
        raise SystemExit("2回のパスワードが一致しません。変更していません。")

    # SQLAlchemy needs the driver name in the URI. quote() safely handles any
    # special characters in a Supabase database password.
    sqlalchemy_url = connection_string.replace(PLACEHOLDER, quote(password, safe=""), 1)
    sqlalchemy_url = sqlalchemy_url.replace("postgresql://", "postgresql+psycopg://", 1)
    sqlalchemy_url = sqlalchemy_url.replace("postgres://", "postgresql+psycopg://", 1)

    current_contents = ENV_FILE.read_text(encoding="utf-8")
    ENV_FILE.write_text(
        replace_env_value(current_contents, "DATABASE_URL", sqlalchemy_url),
        encoding="utf-8",
    )
    print(".env に Supabase PostgreSQL の接続設定を保存しました。接続文字列は表示していません。")


if __name__ == "__main__":
    main()
