"""Minimal LINE Messaging API integration helpers.

This module deliberately uses the standard library for signature verification.
The webhook route must validate the raw request body before JSON parsing.
"""

import base64
import hashlib
import hmac
import secrets

import httpx

LINE_PUSH_MESSAGE_URL = "https://api.line.me/v2/bot/message/push"
LINE_TEXT_MAX_UTF16_CODE_UNITS = 5000
LINE_LINK_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LINE_LINK_CODE_LENGTH = 8


class LineMessagingError(RuntimeError):
    """Raised when LINE rejects a push-message request."""


def generate_link_code() -> str:
    """Create a guardian-friendly, one-time code without ambiguous characters."""

    suffix = "".join(secrets.choice(LINE_LINK_CODE_ALPHABET) for _ in range(LINE_LINK_CODE_LENGTH))
    return f"SS-{suffix}"


def hash_link_code(*, code: str, channel_secret: str) -> str:
    """Hash an invite code so the database never stores the usable code itself."""

    return hmac.new(
        channel_secret.encode("utf-8"),
        code.strip().upper().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def parse_link_code(message_text: str) -> str | None:
    """Accept a code sent by itself, for example: ``SS-ABCD2345``."""

    code = message_text.strip().upper()
    if len(code) != len("SS-") + LINE_LINK_CODE_LENGTH or not code.startswith("SS-"):
        return None
    if all(character in LINE_LINK_CODE_ALPHABET for character in code.removeprefix("SS-")):
        return code
    return None


def verify_webhook_signature(*, body: bytes, signature: str | None, channel_secret: str) -> bool:
    """Return whether a raw LINE webhook request has a valid HMAC signature."""

    if not signature or not channel_secret:
        return False
    expected = base64.b64encode(
        hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode("ascii")
    return hmac.compare_digest(signature, expected)


def utf16_code_unit_length(value: str) -> int:
    """LINE counts text-message length as UTF-16 code units, not Python characters."""

    return len(value.encode("utf-16-le")) // 2


def truncate_line_text(value: str) -> str:
    """Keep a text message within LINE's 5,000 UTF-16-code-unit limit."""

    if utf16_code_unit_length(value) <= LINE_TEXT_MAX_UTF16_CODE_UNITS:
        return value

    suffix = "..."
    prefix_limit = LINE_TEXT_MAX_UTF16_CODE_UNITS - utf16_code_unit_length(suffix)
    encoded_prefix = value.encode("utf-16-le")[: prefix_limit * 2]
    return encoded_prefix.decode("utf-16-le", errors="ignore") + suffix


def build_notification_text(*, summary: str, conversation_prompt: str | None) -> str:
    """Format only the teacher-approved text intended for a guardian."""

    parts = ["【園からのお知らせ】", summary]
    if conversation_prompt:
        parts.extend(["", conversation_prompt])
    return truncate_line_text("\n".join(parts))


def push_text_message(
    *,
    channel_access_token: str,
    recipient_line_user_id: str,
    text: str,
    retry_key: str,
    timeout_seconds: float,
) -> str | None:
    """Send one text message and return LINE's request ID when available."""

    if not channel_access_token:
        raise LineMessagingError("LINE_CHANNEL_ACCESS_TOKEN is not configured")

    response = httpx.post(
        LINE_PUSH_MESSAGE_URL,
        headers={
            "Authorization": f"Bearer {channel_access_token}",
            "Content-Type": "application/json",
            "X-Line-Retry-Key": retry_key,
        },
        json={
            "to": recipient_line_user_id,
            "messages": [{"type": "text", "text": truncate_line_text(text)}],
        },
        timeout=timeout_seconds,
    )
    if not response.is_success:
        detail = response.text.strip().replace("\n", " ")[:500]
        raise LineMessagingError(f"LINE push failed with HTTP {response.status_code}: {detail}")
    return response.headers.get("x-line-request-id")
