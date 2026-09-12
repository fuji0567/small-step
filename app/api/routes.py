import csv
import io
import json
from datetime import datetime, time, timedelta, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo
import httpx

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    AuthenticatedUser,
    CurrentEdgeDevice,
    CurrentTeacher,
    assert_school_access,
    assert_school_admin,
    get_authenticated_user,
    get_current_edge_device,
    get_current_teacher,
    get_db,
    is_bootstrap_admin,
)
from app.cloud_audio import CloudAudioJobStorage, CloudAudioStorageError
from app.database_migrations import latest_migration_revision, migration_revision
from app.edge_keys import generate_edge_api_key, hash_edge_api_key
from app.guardian_archive import generate_guardian_archive_token, hash_guardian_archive_token
from app.line import generate_link_code, hash_link_code, parse_link_code, verify_webhook_signature
from app.notion import NotionSyncError, create_delivered_notification_page
from app.models import (
    AuditEvent,
    AuditEventAction,
    Child,
    CloudAudioJob,
    CloudAudioJobStatus,
    EdgeDevice,
    GuardianArchiveLink,
    LineLinkInvitation,
    NotionSync,
    Notification,
    NotificationStatus,
    Record,
    RecordCategory,
    RecordStatus,
    School,
    Teacher,
    TeacherRole,
    VoiceEnrollmentConsent,
    utc_now,
)
from app.schemas import (
    AuditEventRead,
    AuthBootstrapTeacherCreate,
    AuthClientConfig,
    ChildCreate,
    ChildRead,
    ChildUpdate,
    CloudAudioJobRead,
    EdgeDeviceCreate,
    EdgeDeviceCredential,
    EdgeDeviceRead,
    EdgeRecordCreate,
    GuardianArchiveLinkCreate,
    GuardianArchiveLinkCredential,
    GuardianArchiveLinkRead,
    GuardianArchiveNotificationRead,
    GuardianArchiveRead,
    LineLinkInvitationCreate,
    LineLinkInvitationCredential,
    LineLinkInvitationRead,
    ManualRecordCreate,
    NotificationOverviewRead,
    NotificationRead,
    NotificationReschedule,
    NotificationSent,
    NotionSyncRead,
    RecordCreate,
    RecordRead,
    RecordReview,
    SchoolCreate,
    SchoolDigestTimeUpdate,
    SchoolRead,
    RuntimeReadinessRead,
    TeacherCreate,
    TeacherRead,
    TeacherRoleUpdate,
    VoiceConsentCreate,
    VoiceConsentRead,
)

router = APIRouter(prefix="/api/v1")

VOICE_ENROLLMENT_PURPOSE = "teacher_voiceprint_enrollment"
VOICE_ENROLLMENT_POLICY_VERSION = "2026-08-28"
GUARDIAN_NOT_LINKED_FAILURE_KIND = "guardian_not_linked"

AUDIT_EVENT_LABELS = {
    AuditEventAction.line_link_invitation_issued: "保護者LINEの招待コードを発行",
    AuditEventAction.guardian_line_linked: "保護者LINEが連携済みになりました",
    AuditEventAction.guardian_line_unlinked: "保護者LINEの連携を解除",
    AuditEventAction.guardian_archive_issued: "配信アーカイブURLを発行",
    AuditEventAction.guardian_archive_revoked: "配信アーカイブURLを無効化",
    AuditEventAction.record_approved: "記録を承認",
    AuditEventAction.record_rejected: "記録を却下",
    AuditEventAction.notification_retry_scheduled: "LINE通知の再送を予約",
    AuditEventAction.notification_cancelled: "LINE通知を取消",
    AuditEventAction.notification_rescheduled: "LINE通知の配信日時を変更",
    AuditEventAction.child_updated: "園児の表示名を変更",
    AuditEventAction.child_archived: "園児を退園処理",
    AuditEventAction.child_restored: "園児を復園へ戻す",
    AuditEventAction.teacher_disabled: "先生アカウントを利用停止",
    AuditEventAction.teacher_restored: "先生アカウントの利用を再開",
    AuditEventAction.teacher_role_changed: "先生の権限を変更",
    AuditEventAction.school_digest_time_changed: "成長記録の配信時刻を変更",
    AuditEventAction.manual_record_created: "手入力の記録を作成",
    AuditEventAction.record_history_exported: "記録履歴をCSV出力",
    AuditEventAction.audit_history_exported: "操作履歴をCSV出力",
    AuditEventAction.notion_synced: "Notionに記録",
    AuditEventAction.edge_device_created: "録音端末を登録",
    AuditEventAction.edge_device_key_rotated: "録音端末のキーを再発行",
    AuditEventAction.edge_device_disabled: "録音端末を無効化",
}

AUDIT_TARGET_LABELS = {
    "child": "園児情報",
    "record": "記録",
    "record_history": "記録履歴",
    "audit_history": "操作履歴",
    "notification": "LINE通知",
    "guardian_archive": "配信アーカイブ",
    "edge_device": "録音端末",
    "school": "園の設定",
    "teacher": "先生アカウント",
    "voice_consent": "声紋設定",
}


def as_id(value: object) -> str:
    return str(value)


def as_utc_datetime(value: datetime) -> datetime:
    """Normalise SQLite's timezone-naive values before returning or comparing them."""

    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def require_entity(db: Session, model: type, entity_id: str, label: str):
    entity = db.get(model, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return entity


def require_active_child_for_school(db: Session, child_id: str, school_id: str) -> Child:
    """Return an active child belonging to the requested school."""

    child = require_entity(db, Child, child_id, "Child")
    if child.school_id != school_id:
        raise HTTPException(status_code=422, detail="Child does not belong to this school")
    if not child.is_active:
        raise HTTPException(status_code=409, detail="Child is archived")
    return child


def filtered_records_query(
    *,
    db: Session,
    school_id: str,
    record_status: RecordStatus | None,
    category: RecordCategory | None,
    child_id: str | None,
    search: str | None,
    occurred_from: datetime | None,
    occurred_to: datetime | None,
    current_teacher: CurrentTeacher,
):
    """Build one authorised record query for history views and CSV exports."""

    assert_school_access(current_teacher, school_id)
    query = select(Record).where(Record.school_id == school_id)
    if not current_teacher.is_development and not current_teacher.is_school_admin:
        query = query.where(Record.teacher_id == current_teacher.teacher.id)
    if record_status:
        query = query.where(Record.status == record_status)
    if category:
        query = query.where(Record.category == category)
    if child_id:
        child = require_entity(db, Child, child_id, "Child")
        if child.school_id != school_id:
            raise HTTPException(status_code=422, detail="Child does not belong to this school")
        query = query.where(Record.child_id == child.id)
    if search and search.strip():
        query = query.where(Record.summary.contains(search.strip()))

    start = as_utc_datetime(occurred_from) if occurred_from else None
    end = as_utc_datetime(occurred_to) if occurred_to else None
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="The start date must not be after the end date")
    if start:
        query = query.where(Record.occurred_at >= start)
    if end:
        query = query.where(Record.occurred_at <= end)
    return query


def csv_cell(value: object | None) -> str:
    """Prevent spreadsheet applications from interpreting record text as formulas."""

    text = "" if value is None else str(value)
    return f"'{text}" if text.lstrip().startswith(("=", "+", "-", "@")) else text


def filtered_audit_events_query(
    *,
    db: Session,
    school_id: str,
    action: AuditEventAction | None,
    occurred_from: datetime | None,
    occurred_to: datetime | None,
    current_teacher: CurrentTeacher,
):
    """Build one admin-only audit query for the history screen and CSV export."""

    assert_school_access(current_teacher, school_id)
    assert_school_admin(current_teacher)
    query = (
        select(AuditEvent, Teacher.name)
        .outerjoin(Teacher, Teacher.id == AuditEvent.actor_teacher_id)
        .where(AuditEvent.school_id == school_id)
    )
    if action:
        query = query.where(AuditEvent.action == action)

    start = as_utc_datetime(occurred_from) if occurred_from else None
    end = as_utc_datetime(occurred_to) if occurred_to else None
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="The start date must not be after the end date")
    if start:
        query = query.where(AuditEvent.created_at >= start)
    if end:
        query = query.where(AuditEvent.created_at <= end)
    return query


def assert_record_access(current_teacher: CurrentTeacher, record: Record) -> None:
    assert_school_access(current_teacher, record.school_id)
    if (
        not current_teacher.is_development
        and not current_teacher.is_school_admin
        and current_teacher.teacher is not None
        and record.teacher_id != current_teacher.teacher.id
    ):
        raise HTTPException(status_code=403, detail="Access to this record is denied")


def get_next_digest_time(now: datetime, timezone_name: str, digest_time: str) -> datetime:
    try:
        hour, minute = (int(part) for part in digest_time.split(":"))
        target_time = time(hour=hour, minute=minute)
        local_zone = ZoneInfo(timezone_name)
    except (ValueError, TypeError) as error:
        raise RuntimeError("DIGEST_TIME or TIMEZONE is invalid") from error

    local_now = now.astimezone(local_zone)
    scheduled = datetime.combine(local_now.date(), target_time, tzinfo=local_zone)
    if scheduled <= local_now:
        scheduled += timedelta(days=1)
    return scheduled.astimezone(timezone.utc)


def edge_device_credential(device: EdgeDevice, api_key: str) -> EdgeDeviceCredential:
    return EdgeDeviceCredential(
        id=device.id,
        school_id=device.school_id,
        teacher_id=device.teacher_id,
        name=device.name,
        is_active=device.is_active,
        last_seen_at=device.last_seen_at,
        created_at=device.created_at,
        api_key=api_key,
    )


def guardian_archive_link_read(link: GuardianArchiveLink) -> GuardianArchiveLinkRead:
    return GuardianArchiveLinkRead(
        id=link.id,
        school_id=link.school_id,
        child_id=link.child_id,
        expires_at=as_utc_datetime(link.expires_at),
        revoked_at=link.revoked_at,
        created_at=link.created_at,
    )


def line_link_invitation_read(invitation: LineLinkInvitation) -> LineLinkInvitationRead:
    """Return only safe invitation metadata; the usable code is never recoverable."""

    return LineLinkInvitationRead(
        id=invitation.id,
        school_id=invitation.school_id,
        child_id=invitation.child_id,
        expires_at=as_utc_datetime(invitation.expires_at),
        used_at=as_utc_datetime(invitation.used_at) if invitation.used_at else None,
        revoked_at=as_utc_datetime(invitation.revoked_at) if invitation.revoked_at else None,
        created_at=as_utc_datetime(invitation.created_at),
    )


def add_audit_event(
    db: Session,
    *,
    school_id: str,
    action: AuditEventAction,
    target_type: str,
    current_teacher: CurrentTeacher | None = None,
) -> None:
    """Store a minimal event without any action payload, secret, or child data."""

    db.add(
        AuditEvent(
            school_id=school_id,
            actor_teacher_id=current_teacher.teacher.id
            if current_teacher is not None and current_teacher.teacher is not None
            else None,
            action=action,
            target_type=target_type,
        )
    )


def require_guardian_archive_link(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> GuardianArchiveLink:
    """Validate a guardian archive token without revealing why it failed."""

    if not request.app.state.settings.guardian_archive_enabled:
        raise HTTPException(status_code=403, detail="Guardian archive is disabled")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Guardian archive access is invalid or expired")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Guardian archive access is invalid or expired")
    link = db.scalar(
        select(GuardianArchiveLink).where(GuardianArchiveLink.token_hash == hash_guardian_archive_token(token))
    )
    if link is None or link.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Guardian archive access is invalid or expired")
    if as_utc_datetime(link.expires_at) <= utc_now():
        raise HTTPException(status_code=401, detail="Guardian archive access is invalid or expired")
    return link


def cloud_audio_storage(request: Request) -> CloudAudioJobStorage:
    settings = request.app.state.settings
    return CloudAudioJobStorage(
        job_dir=settings.cloud_audio_job_dir,
        max_file_bytes=settings.edge_audio_max_file_bytes,
    )


def voice_consent_is_active(consent: VoiceEnrollmentConsent, now: datetime | None = None) -> bool:
    if consent.revoked_at is not None:
        return False
    expires_at = consent.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > (now or utc_now())


def voice_consent_read(consent: VoiceEnrollmentConsent) -> VoiceConsentRead:
    return VoiceConsentRead(
        id=consent.id,
        school_id=consent.school_id,
        teacher_id=consent.teacher_id,
        purpose=consent.purpose,
        policy_version=consent.policy_version,
        retention_days=consent.retention_days,
        consented_at=consent.consented_at,
        expires_at=consent.expires_at,
        revoked_at=consent.revoked_at,
        is_active=voice_consent_is_active(consent),
        created_at=consent.created_at,
        updated_at=consent.updated_at,
    )


def require_real_teacher(current_teacher: CurrentTeacher) -> Teacher:
    if current_teacher.teacher is None:
        raise HTTPException(status_code=404, detail="A linked teacher account is required")
    return current_teacher.teacher


@router.get("/health", tags=["system"])
def health_check(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/readiness", response_model=RuntimeReadinessRead, tags=["system"])
def readiness_check(request: Request, db: Session = Depends(get_db)) -> RuntimeReadinessRead | JSONResponse:
    """Report whether this API is prepared for its configured runtime mode.

    The response intentionally includes booleans only: it must be safe for a
    load balancer or operator to call without exposing database hosts, API keys,
    model names, uploaded-audio paths, or other private settings.
    """

    settings = request.app.state.settings
    database_ready = False
    database_migration_current = False
    try:
        db.execute(text("SELECT 1"))
        database_ready = True
        database_migration_current = migration_revision(settings.database_url) == latest_migration_revision()
    except Exception:
        # Do not disclose database connection or migration errors publicly.
        database_ready = False
        database_migration_current = False

    cloud_audio_job_storage_ready: bool | None = None
    cloud_audio_llm_configured: bool | None = None
    if settings.cloud_audio_enabled:
        cloud_audio_llm_configured = bool(settings.llm_base_url and settings.llm_model)
        try:
            cloud_audio_storage(request).ensure_directory()
            cloud_audio_job_storage_ready = True
        except (CloudAudioStorageError, OSError):
            cloud_audio_job_storage_ready = False

    result = RuntimeReadinessRead(
        status="ready"
        if database_ready
        and database_migration_current
        and (
            not settings.cloud_audio_enabled
            or (cloud_audio_job_storage_ready is True and cloud_audio_llm_configured is True)
        )
        else "not_ready",
        database_ready=database_ready,
        database_migration_current=database_migration_current,
        cloud_audio_enabled=settings.cloud_audio_enabled,
        cloud_audio_job_storage_ready=cloud_audio_job_storage_ready,
        cloud_audio_llm_configured=cloud_audio_llm_configured,
        line_delivery_configured=bool(settings.line_channel_secret and settings.line_channel_access_token),
    )
    if result.status == "ready":
        return result
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=result.model_dump(mode="json"))


@router.post("/line/webhook", tags=["line"])
async def receive_line_webhook(request: Request) -> dict[str, bool]:
    """Verify LINE's raw webhook request before parsing its JSON body.

    We intentionally do not persist message contents here. The current product
    only needs the signed endpoint for channel verification and outbound family
    notifications; guardian-to-child linking is introduced separately.
    """

    channel_secret = request.app.state.settings.line_channel_secret
    if not channel_secret:
        raise HTTPException(status_code=503, detail="LINE_CHANNEL_SECRET is not configured")

    raw_body = await request.body()
    if not verify_webhook_signature(
        body=raw_body,
        signature=request.headers.get("x-line-signature"),
        channel_secret=channel_secret,
    ):
        raise HTTPException(status_code=401, detail="Invalid LINE webhook signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="LINE webhook body must be valid JSON") from error
    if not isinstance(payload.get("events"), list):
        raise HTTPException(status_code=400, detail="LINE webhook events must be an array")

    # Never retain guardian message text. Only a valid, one-time link code can
    # update the existing guardian LINE user ID for the matching child.
    session = request.app.state.session_factory()
    try:
        for event in payload["events"]:
            if not isinstance(event, dict) or event.get("type") != "message":
                continue
            source = event.get("source")
            message = event.get("message")
            if not isinstance(source, dict) or not isinstance(message, dict):
                continue
            if source.get("type") != "user" or message.get("type") != "text":
                continue
            line_user_id = source.get("userId")
            message_text = message.get("text")
            if not isinstance(line_user_id, str) or not isinstance(message_text, str):
                continue
            link_code = parse_link_code(message_text)
            if link_code is None:
                continue

            invitation = session.scalar(
                select(LineLinkInvitation)
                .where(LineLinkInvitation.code_hash == hash_link_code(code=link_code, channel_secret=channel_secret))
                .where(LineLinkInvitation.used_at.is_(None))
                .where(LineLinkInvitation.revoked_at.is_(None))
                .where(LineLinkInvitation.expires_at > utc_now())
            )
            if invitation is None:
                continue
            child = session.get(Child, invitation.child_id)
            if child is None or child.school_id != invitation.school_id or not child.is_active:
                continue
            child.guardian_line_user_id = line_user_id
            invitation.used_at = utc_now()
            notifications = session.scalars(
                select(Notification)
                .join(Record, Notification.record_id == Record.id)
                .where(Record.child_id == child.id)
                .where(Notification.status.in_([NotificationStatus.waiting_guardian_link, NotificationStatus.failed]))
            )
            for notification in notifications:
                if (
                    notification.status == NotificationStatus.waiting_guardian_link
                    or notification.last_failure_kind == GUARDIAN_NOT_LINKED_FAILURE_KIND
                ):
                    notification.recipient_line_user_id = line_user_id
                    notification.status = NotificationStatus.pending
                    notification.last_failure_kind = None
            add_audit_event(
                session,
                school_id=child.school_id,
                action=AuditEventAction.guardian_line_linked,
                target_type="guardian_line_link",
            )
            session.commit()
    finally:
        session.close()
    return {"ok": True}


@router.post(
    "/line/link-invitations",
    response_model=LineLinkInvitationCredential,
    status_code=status.HTTP_201_CREATED,
    tags=["line"],
)
def create_line_link_invitation(
    payload: LineLinkInvitationCreate,
    request: Request,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> LineLinkInvitationCredential:
    """Issue one guardian code and invalidate any earlier unused code for that child."""

    channel_secret = request.app.state.settings.line_channel_secret
    if not channel_secret:
        raise HTTPException(status_code=503, detail="LINE_CHANNEL_SECRET is not configured")
    child = require_entity(db, Child, as_id(payload.child_id), "Child")
    assert_school_access(current_teacher, child.school_id)
    assert_school_admin(current_teacher)
    if not child.is_active:
        raise HTTPException(status_code=409, detail="Child is archived")

    now = utc_now()
    db.execute(
        update(LineLinkInvitation)
        .where(LineLinkInvitation.child_id == child.id)
        .where(LineLinkInvitation.used_at.is_(None))
        .where(LineLinkInvitation.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    invite_code = generate_link_code()
    invitation = LineLinkInvitation(
        school_id=child.school_id,
        child_id=child.id,
        code_hash=hash_link_code(code=invite_code, channel_secret=channel_secret),
        expires_at=now + timedelta(minutes=payload.expires_in_minutes),
    )
    db.add(invitation)
    add_audit_event(
        db,
        school_id=child.school_id,
        action=AuditEventAction.line_link_invitation_issued,
        target_type="guardian_line_link",
        current_teacher=current_teacher,
    )
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=503, detail="Could not issue a unique LINE link code; please retry") from error
    db.refresh(invitation)
    return LineLinkInvitationCredential(
        **line_link_invitation_read(invitation).model_dump(),
        invite_code=invite_code,
    )


@router.get(
    "/line/link-invitations/active",
    response_model=list[LineLinkInvitationRead],
    tags=["line"],
)
def list_active_line_link_invitations(
    school_id: str,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> list[LineLinkInvitationRead]:
    """Show administrators which unlinked guardians still have a usable code.

    The response deliberately omits the code. A lost code must be replaced,
    which invalidates the previous one instead of exposing a credential again.
    """

    assert_school_access(current_teacher, school_id)
    assert_school_admin(current_teacher)
    invitations = db.scalars(
        select(LineLinkInvitation)
        .join(Child, Child.id == LineLinkInvitation.child_id)
        .where(LineLinkInvitation.school_id == school_id)
        .where(LineLinkInvitation.used_at.is_(None))
        .where(LineLinkInvitation.revoked_at.is_(None))
        .where(LineLinkInvitation.expires_at > utc_now())
        .where(Child.is_active.is_(True))
        .where(Child.guardian_line_user_id.is_(None))
        .order_by(LineLinkInvitation.expires_at)
    )
    return [line_link_invitation_read(invitation) for invitation in invitations]


@router.post("/schools", response_model=SchoolRead, status_code=status.HTTP_201_CREATED, tags=["schools"])
def create_school(
    payload: SchoolCreate,
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
) -> School:
    if request.app.state.settings.auth_mode == "supabase" and not is_bootstrap_admin(request, user):
        raise HTTPException(status_code=403, detail="Only a configured bootstrap administrator can create the first school")

    school = School(
        **payload.model_dump(exclude={"initial_admin_name", "digest_time"}),
        digest_time=payload.digest_time or request.app.state.settings.digest_time,
    )
    db.add(school)
    try:
        db.flush()
        if request.app.state.settings.auth_mode == "supabase":
            db.add(
                Teacher(
                    school_id=school.id,
                    name=payload.initial_admin_name or user.email.split("@", 1)[0],
                    email=user.email,
                    auth_user_id=user.id,
                    role=TeacherRole.school_admin,
                )
            )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="School name already exists") from error
    db.refresh(school)
    return school


@router.get("/schools", response_model=list[SchoolRead], tags=["schools"])
def list_schools(
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> list[School]:
    if not current_teacher.is_development:
        return [require_entity(db, School, current_teacher.school_id, "School")]
    return list(db.scalars(select(School).order_by(School.name)))


@router.patch("/schools/{school_id}/digest-time", response_model=SchoolRead, tags=["schools"])
def update_school_digest_time(
    school_id: str,
    payload: SchoolDigestTimeUpdate,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> School:
    """Change only the default time used by future growth-record approvals."""

    school = require_entity(db, School, school_id, "School")
    assert_school_access(current_teacher, school.id)
    assert_school_admin(current_teacher)
    school.digest_time = payload.digest_time
    add_audit_event(
        db,
        school_id=school.id,
        action=AuditEventAction.school_digest_time_changed,
        target_type="school",
        current_teacher=current_teacher,
    )
    db.commit()
    db.refresh(school)
    return school


@router.get("/auth/config", response_model=AuthClientConfig, tags=["auth"])
def get_auth_client_config(request: Request) -> AuthClientConfig:
    """Expose only the Supabase values that are safe for a browser client."""

    settings = request.app.state.settings
    if settings.auth_mode == "development":
        return AuthClientConfig(auth_mode="development")
    return AuthClientConfig(
        auth_mode="supabase",
        supabase_url=settings.supabase_url,
        supabase_publishable_key=settings.supabase_publishable_key,
    )


@router.get("/auth/bootstrap/schools", response_model=list[SchoolRead], tags=["auth"])
def list_bootstrap_schools(
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
) -> list[School]:
    """Let only the configured initial administrator choose an existing school."""

    if request.app.state.settings.auth_mode != "supabase" or not is_bootstrap_admin(request, user):
        raise HTTPException(status_code=403, detail="Bootstrap administrator access is required")
    return list(db.scalars(select(School).order_by(School.name)))


@router.post("/auth/bootstrap/teacher", response_model=TeacherRead, tags=["auth"])
def bootstrap_school_admin(
    payload: AuthBootstrapTeacherCreate,
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
) -> Teacher:
    """Create or safely link the one initial school administrator after sign-in."""

    if request.app.state.settings.auth_mode != "supabase" or not is_bootstrap_admin(request, user):
        raise HTTPException(status_code=403, detail="Bootstrap administrator access is required")

    existing_link = db.scalar(select(Teacher).where(Teacher.auth_user_id == user.id))
    if existing_link is not None:
        if not existing_link.is_active:
            raise HTTPException(status_code=403, detail="This teacher account is disabled")
        return existing_link

    school_id = as_id(payload.school_id)
    require_entity(db, School, school_id, "School")
    teacher = db.scalar(select(Teacher).where(Teacher.email == user.email))
    if teacher is not None:
        if not teacher.is_active:
            raise HTTPException(status_code=403, detail="This teacher account is disabled")
        if teacher.school_id != school_id:
            raise HTTPException(status_code=409, detail="This email is already registered for another school")
        if teacher.auth_user_id is not None:
            raise HTTPException(status_code=409, detail="Teacher account is already linked to another Auth user")
        teacher.auth_user_id = user.id
        teacher.role = TeacherRole.school_admin
    else:
        teacher = Teacher(
            school_id=school_id,
            name=payload.name,
            email=user.email,
            auth_user_id=user.id,
            role=TeacherRole.school_admin,
        )
        db.add(teacher)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not create the initial teacher account") from error
    db.refresh(teacher)
    return teacher


@router.post("/auth/link-teacher", response_model=TeacherRead, tags=["auth"])
def link_supabase_user_to_teacher(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
) -> Teacher:
    """Link a signed-in user to a teacher record pre-registered by a school admin."""

    teacher = db.scalar(select(Teacher).where(Teacher.auth_user_id == user.id))
    if teacher:
        if not teacher.is_active:
            raise HTTPException(status_code=403, detail="This teacher account is disabled")
        return teacher

    teacher = db.scalar(select(Teacher).where(Teacher.email == user.email))
    if teacher is None:
        raise HTTPException(status_code=404, detail="No pre-registered teacher account exists for this email")
    if not teacher.is_active:
        raise HTTPException(status_code=403, detail="This teacher account is disabled")
    if teacher.auth_user_id is not None:
        raise HTTPException(status_code=409, detail="Teacher account is already linked to another Auth user")

    teacher.auth_user_id = user.id
    db.commit()
    db.refresh(teacher)
    return teacher


@router.get("/auth/me", response_model=TeacherRead, tags=["auth"])
def get_my_teacher_profile(current_teacher: CurrentTeacher = Depends(get_current_teacher)) -> Teacher:
    if current_teacher.teacher is None:
        raise HTTPException(status_code=404, detail="Development account has no teacher profile")
    return current_teacher.teacher


@router.post("/teachers", response_model=TeacherRead, status_code=status.HTTP_201_CREATED, tags=["teachers"])
def create_teacher(
    payload: TeacherCreate,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Teacher:
    require_entity(db, School, as_id(payload.school_id), "School")
    assert_school_access(current_teacher, as_id(payload.school_id))
    assert_school_admin(current_teacher)
    teacher = Teacher(
        **{
            **payload.model_dump(),
            "school_id": as_id(payload.school_id),
            "email": payload.email.lower(),
        }
    )
    db.add(teacher)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Teacher email already exists") from error
    db.refresh(teacher)
    return teacher


@router.get("/teachers", response_model=list[TeacherRead], tags=["teachers"])
def list_teachers(
    school_id: str,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> list[Teacher]:
    """List teacher accounts only for the school's administrators."""

    assert_school_access(current_teacher, school_id)
    assert_school_admin(current_teacher)
    return list(
        db.scalars(
            select(Teacher)
            .where(Teacher.school_id == school_id)
            .order_by(Teacher.is_active.desc(), Teacher.name)
        )
    )


@router.patch("/teachers/{teacher_id}/role", response_model=TeacherRead, tags=["teachers"])
def change_teacher_role(
    teacher_id: str,
    payload: TeacherRoleUpdate,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Teacher:
    """Support a safe school-administrator handover without deleting accounts."""

    teacher = require_entity(db, Teacher, teacher_id, "Teacher")
    assert_school_access(current_teacher, teacher.school_id)
    assert_school_admin(current_teacher)
    if not teacher.is_active:
        raise HTTPException(status_code=409, detail="Disabled teacher accounts cannot change role")
    if current_teacher.teacher is not None and current_teacher.teacher.id == teacher.id:
        raise HTTPException(status_code=409, detail="You cannot change your own teacher role")
    if teacher.role == payload.role:
        raise HTTPException(status_code=409, detail="Teacher already has this role")
    if teacher.role == TeacherRole.school_admin and payload.role == TeacherRole.teacher:
        active_admin_ids = list(
            db.scalars(
                select(Teacher.id)
                .where(Teacher.school_id == teacher.school_id)
                .where(Teacher.role == TeacherRole.school_admin)
                .where(Teacher.is_active.is_(True))
            )
        )
        if len(active_admin_ids) <= 1:
            raise HTTPException(status_code=409, detail="At least one active school administrator is required")

    teacher.role = payload.role
    add_audit_event(
        db,
        school_id=teacher.school_id,
        action=AuditEventAction.teacher_role_changed,
        target_type="teacher",
        current_teacher=current_teacher,
    )
    db.commit()
    db.refresh(teacher)
    return teacher


@router.post("/teachers/{teacher_id}/disable", response_model=TeacherRead, tags=["teachers"])
def disable_teacher(
    teacher_id: str,
    request: Request,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Teacher:
    """Disable a departing teacher without deleting the school's history."""

    teacher = require_entity(db, Teacher, teacher_id, "Teacher")
    assert_school_access(current_teacher, teacher.school_id)
    assert_school_admin(current_teacher)
    if not teacher.is_active:
        raise HTTPException(status_code=409, detail="Teacher account is already disabled")
    if current_teacher.teacher is not None and current_teacher.teacher.id == teacher.id:
        raise HTTPException(status_code=409, detail="You cannot disable your own teacher account")
    if teacher.role == TeacherRole.school_admin:
        active_admin_ids = list(
            db.scalars(
                select(Teacher.id)
                .where(Teacher.school_id == teacher.school_id)
                .where(Teacher.role == TeacherRole.school_admin)
                .where(Teacher.is_active.is_(True))
            )
        )
        if len(active_admin_ids) <= 1:
            raise HTTPException(status_code=409, detail="At least one active school administrator is required")

    now = utc_now()
    teacher.is_active = False
    teacher.disabled_at = now
    db.execute(
        update(VoiceEnrollmentConsent)
        .where(VoiceEnrollmentConsent.teacher_id == teacher.id)
        .where(VoiceEnrollmentConsent.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    for device in db.scalars(
        select(EdgeDevice)
        .where(EdgeDevice.teacher_id == teacher.id)
        .where(EdgeDevice.is_active.is_(True))
    ):
        device.is_active = False

    # Stop unprocessed audio before it can create a new record for a disabled teacher.
    storage = cloud_audio_storage(request)
    for job in db.scalars(
        select(CloudAudioJob)
        .where(CloudAudioJob.teacher_id == teacher.id)
        .where(CloudAudioJob.status.in_([CloudAudioJobStatus.queued, CloudAudioJobStatus.processing]))
    ):
        job.status = CloudAudioJobStatus.expired
        job.claim_token = None
        job.completed_at = now
        storage.delete(job.storage_key)

    add_audit_event(
        db,
        school_id=teacher.school_id,
        action=AuditEventAction.teacher_disabled,
        target_type="teacher",
        current_teacher=current_teacher,
    )
    db.commit()
    db.refresh(teacher)
    return teacher


@router.post("/teachers/{teacher_id}/restore", response_model=TeacherRead, tags=["teachers"])
def restore_teacher(
    teacher_id: str,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Teacher:
    """Allow an administrator to correct an accidental teacher disablement."""

    teacher = require_entity(db, Teacher, teacher_id, "Teacher")
    assert_school_access(current_teacher, teacher.school_id)
    assert_school_admin(current_teacher)
    if teacher.is_active:
        raise HTTPException(status_code=409, detail="Teacher account is already active")

    # Old edge keys, queued audio, and revoked voice consent remain inactive.
    teacher.is_active = True
    teacher.disabled_at = None
    add_audit_event(
        db,
        school_id=teacher.school_id,
        action=AuditEventAction.teacher_restored,
        target_type="teacher",
        current_teacher=current_teacher,
    )
    db.commit()
    db.refresh(teacher)
    return teacher


@router.get("/voice-consent/me", response_model=VoiceConsentRead | None, tags=["voice consent"])
def get_my_voice_consent(
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> VoiceConsentRead | None:
    """Show only the signed-in teacher's local voiceprint consent state."""

    teacher = require_real_teacher(current_teacher)
    consent = db.scalar(select(VoiceEnrollmentConsent).where(VoiceEnrollmentConsent.teacher_id == teacher.id))
    return voice_consent_read(consent) if consent else None


@router.post("/voice-consent/me", response_model=VoiceConsentRead, status_code=status.HTTP_201_CREATED, tags=["voice consent"])
def grant_my_voice_consent(
    payload: VoiceConsentCreate,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> VoiceConsentRead:
    """Grant or renew the current teacher's revocable local-only enrollment consent."""

    teacher = require_real_teacher(current_teacher)
    now = utc_now()
    consent = db.scalar(select(VoiceEnrollmentConsent).where(VoiceEnrollmentConsent.teacher_id == teacher.id))
    fields = {
        "school_id": teacher.school_id,
        "purpose": VOICE_ENROLLMENT_PURPOSE,
        "policy_version": VOICE_ENROLLMENT_POLICY_VERSION,
        "retention_days": payload.retention_days,
        "consented_at": now,
        "expires_at": now + timedelta(days=payload.retention_days),
        "revoked_at": None,
    }
    if consent is None:
        consent = VoiceEnrollmentConsent(teacher_id=teacher.id, **fields)
        db.add(consent)
    else:
        for field, value in fields.items():
            setattr(consent, field, value)
    db.commit()
    db.refresh(consent)
    return voice_consent_read(consent)


@router.post("/voice-consent/me/revoke", response_model=VoiceConsentRead, tags=["voice consent"])
def revoke_my_voice_consent(
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> VoiceConsentRead:
    """Revoke consent immediately before any later voiceprint enrollment work."""

    teacher = require_real_teacher(current_teacher)
    consent = db.scalar(select(VoiceEnrollmentConsent).where(VoiceEnrollmentConsent.teacher_id == teacher.id))
    if consent is None:
        raise HTTPException(status_code=404, detail="Voiceprint consent was not found")
    consent.revoked_at = utc_now()
    db.commit()
    db.refresh(consent)
    return voice_consent_read(consent)


@router.post(
    "/edge-devices",
    response_model=EdgeDeviceCredential,
    status_code=status.HTTP_201_CREATED,
    tags=["edge devices"],
)
def create_edge_device(
    payload: EdgeDeviceCreate,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> EdgeDeviceCredential:
    """Register a wearable/on-premise device and reveal its key once."""
    school_id = as_id(payload.school_id)
    teacher_id = as_id(payload.teacher_id)
    require_entity(db, School, school_id, "School")
    assert_school_access(current_teacher, school_id)
    assert_school_admin(current_teacher)
    teacher = require_entity(db, Teacher, teacher_id, "Teacher")
    if teacher.school_id != school_id:
        raise HTTPException(status_code=422, detail="Teacher does not belong to this school")
    if not teacher.is_active:
        raise HTTPException(status_code=422, detail="Teacher account is disabled")

    api_key = generate_edge_api_key()
    device = EdgeDevice(
        school_id=school_id,
        teacher_id=teacher_id,
        name=payload.name,
        api_key_hash=hash_edge_api_key(api_key),
    )
    db.add(device)
    add_audit_event(
        db,
        school_id=device.school_id,
        action=AuditEventAction.edge_device_created,
        target_type="edge_device",
        current_teacher=current_teacher,
    )
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="An edge device with this name already exists") from error
    db.refresh(device)
    return edge_device_credential(device, api_key)


@router.get("/edge-devices", response_model=list[EdgeDeviceRead], tags=["edge devices"])
def list_edge_devices(
    school_id: str,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> list[EdgeDevice]:
    assert_school_access(current_teacher, school_id)
    assert_school_admin(current_teacher)
    return list(
        db.scalars(select(EdgeDevice).where(EdgeDevice.school_id == school_id).order_by(EdgeDevice.name))
    )


@router.post(
    "/edge-devices/{device_id}/rotate-key",
    response_model=EdgeDeviceCredential,
    tags=["edge devices"],
)
def rotate_edge_device_key(
    device_id: str,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> EdgeDeviceCredential:
    device = require_entity(db, EdgeDevice, device_id, "Edge device")
    assert_school_access(current_teacher, device.school_id)
    assert_school_admin(current_teacher)
    api_key = generate_edge_api_key()
    device.api_key_hash = hash_edge_api_key(api_key)
    device.is_active = True
    add_audit_event(
        db,
        school_id=device.school_id,
        action=AuditEventAction.edge_device_key_rotated,
        target_type="edge_device",
        current_teacher=current_teacher,
    )
    db.commit()
    db.refresh(device)
    return edge_device_credential(device, api_key)


@router.post("/edge-devices/{device_id}/disable", response_model=EdgeDeviceRead, tags=["edge devices"])
def disable_edge_device(
    device_id: str,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> EdgeDevice:
    device = require_entity(db, EdgeDevice, device_id, "Edge device")
    assert_school_access(current_teacher, device.school_id)
    assert_school_admin(current_teacher)
    device.is_active = False
    add_audit_event(
        db,
        school_id=device.school_id,
        action=AuditEventAction.edge_device_disabled,
        target_type="edge_device",
        current_teacher=current_teacher,
    )
    db.commit()
    db.refresh(device)
    return device


@router.post("/children", response_model=ChildRead, status_code=status.HTTP_201_CREATED, tags=["children"])
def create_child(
    payload: ChildCreate,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Child:
    require_entity(db, School, as_id(payload.school_id), "School")
    assert_school_access(current_teacher, as_id(payload.school_id))
    assert_school_admin(current_teacher)
    child = Child(**{**payload.model_dump(), "school_id": as_id(payload.school_id)})
    db.add(child)
    db.commit()
    db.refresh(child)
    return child


@router.get("/children", response_model=list[ChildRead], tags=["children"])
def list_children(
    school_id: str,
    include_archived: bool = False,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> list[Child]:
    assert_school_access(current_teacher, school_id)
    query = select(Child).where(Child.school_id == school_id)
    if not include_archived:
        query = query.where(Child.is_active.is_(True))
    return list(db.scalars(query.order_by(Child.is_active.desc(), Child.display_name)))


@router.patch("/children/{child_id}", response_model=ChildRead, tags=["children"])
def update_child(
    child_id: str,
    payload: ChildUpdate,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Child:
    """Correct a child's display name without changing their historical records."""

    child = require_entity(db, Child, child_id, "Child")
    assert_school_access(current_teacher, child.school_id)
    assert_school_admin(current_teacher)
    if not child.is_active:
        raise HTTPException(status_code=409, detail="Archived children cannot be edited")
    child.display_name = payload.display_name
    add_audit_event(
        db,
        school_id=child.school_id,
        action=AuditEventAction.child_updated,
        target_type="child",
        current_teacher=current_teacher,
    )
    db.commit()
    db.refresh(child)
    return child


@router.post("/children/{child_id}/archive", response_model=ChildRead, tags=["children"])
def archive_child(
    child_id: str,
    request: Request,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Child:
    """Retire a child while retaining existing records and stopping future delivery."""

    child = require_entity(db, Child, child_id, "Child")
    assert_school_access(current_teacher, child.school_id)
    assert_school_admin(current_teacher)
    if not child.is_active:
        raise HTTPException(status_code=409, detail="Child is already archived")

    now = utc_now()
    child.is_active = False
    child.archived_at = now
    child.guardian_line_user_id = None
    db.execute(
        update(LineLinkInvitation)
        .where(LineLinkInvitation.child_id == child.id)
        .where(LineLinkInvitation.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.execute(
        update(GuardianArchiveLink)
        .where(GuardianArchiveLink.child_id == child.id)
        .where(GuardianArchiveLink.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.execute(
        update(Record)
        .where(Record.school_id == child.school_id)
        .where(Record.child_id == child.id)
        .where(Record.status == RecordStatus.pending_review)
        .values(status=RecordStatus.rejected, reviewed_at=now)
    )

    pending_notifications = db.scalars(
        select(Notification)
        .join(Record, Notification.record_id == Record.id)
        .where(Record.school_id == child.school_id)
        .where(Record.child_id == child.id)
        .where(Notification.status.in_([NotificationStatus.pending, NotificationStatus.waiting_guardian_link]))
    )
    for notification in pending_notifications:
        notification.recipient_line_user_id = None
        notification.status = NotificationStatus.cancelled
        notification.provider_message_id = None
        notification.sent_at = None
        notification.last_failure_kind = None

    # Invalidate any worker lease before deleting the short-lived raw upload.
    # A worker that was already running then cannot create a new record.
    storage = cloud_audio_storage(request)
    active_audio_jobs = db.scalars(
        select(CloudAudioJob)
        .where(CloudAudioJob.child_id == child.id)
        .where(CloudAudioJob.status.in_([CloudAudioJobStatus.queued, CloudAudioJobStatus.processing]))
    )
    for job in active_audio_jobs:
        job.status = CloudAudioJobStatus.expired
        job.claim_token = None
        job.completed_at = now
        storage.delete(job.storage_key)

    add_audit_event(
        db,
        school_id=child.school_id,
        action=AuditEventAction.child_archived,
        target_type="child",
        current_teacher=current_teacher,
    )
    db.commit()
    db.refresh(child)
    return child


@router.post("/children/{child_id}/restore", response_model=ChildRead, tags=["children"])
def restore_child(
    child_id: str,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Child:
    """Return a retired child to the active list without restoring private links."""

    child = require_entity(db, Child, child_id, "Child")
    assert_school_access(current_teacher, child.school_id)
    assert_school_admin(current_teacher)
    if child.is_active:
        raise HTTPException(status_code=409, detail="Child is already active")

    # A restoration never revives the former guardian, queued notice, raw audio,
    # invitation, or archive link. The guardian must link again with a new code.
    child.is_active = True
    child.archived_at = None
    child.guardian_line_user_id = None
    add_audit_event(
        db,
        school_id=child.school_id,
        action=AuditEventAction.child_restored,
        target_type="child",
        current_teacher=current_teacher,
    )
    db.commit()
    db.refresh(child)
    return child


@router.delete("/children/{child_id}/guardian-line-link", response_model=ChildRead, tags=["children"])
def unlink_guardian_line_account(
    child_id: str,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Child:
    """Stop future guardian delivery after an administrator deliberately unlinks LINE."""

    child = require_entity(db, Child, child_id, "Child")
    assert_school_access(current_teacher, child.school_id)
    assert_school_admin(current_teacher)
    if not child.is_active:
        raise HTTPException(status_code=409, detail="Child is archived")
    now = utc_now()

    child.guardian_line_user_id = None
    db.execute(
        update(LineLinkInvitation)
        .where(LineLinkInvitation.child_id == child.id)
        .where(LineLinkInvitation.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.execute(
        update(GuardianArchiveLink)
        .where(GuardianArchiveLink.child_id == child.id)
        .where(GuardianArchiveLink.revoked_at.is_(None))
        .values(revoked_at=now)
    )

    pending_notifications = db.scalars(
        select(Notification)
        .join(Record, Notification.record_id == Record.id)
        .where(Record.school_id == child.school_id)
        .where(Record.child_id == child.id)
        .where(Notification.status.in_([NotificationStatus.pending, NotificationStatus.waiting_guardian_link]))
    )
    for notification in pending_notifications:
        notification.recipient_line_user_id = None
        notification.status = NotificationStatus.failed
        notification.provider_message_id = None
        notification.sent_at = None
        notification.last_failure_kind = GUARDIAN_NOT_LINKED_FAILURE_KIND

    add_audit_event(
        db,
        school_id=child.school_id,
        action=AuditEventAction.guardian_line_unlinked,
        target_type="guardian_line_link",
        current_teacher=current_teacher,
    )
    db.commit()
    db.refresh(child)
    return child


@router.post(
    "/guardian-archive-links",
    response_model=GuardianArchiveLinkCredential,
    status_code=status.HTTP_201_CREATED,
    tags=["guardian archive"],
)
def create_guardian_archive_link(
    payload: GuardianArchiveLinkCreate,
    request: Request,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> GuardianArchiveLinkCredential:
    """Issue one expiring archive URL for a LINE-linked guardian.

    Issuing a replacement revokes all earlier links for the same child so a lost
    URL can be invalidated by creating a new one.
    """

    settings = request.app.state.settings
    if not settings.guardian_archive_enabled:
        raise HTTPException(status_code=403, detail="Guardian archive is disabled")
    child = require_entity(db, Child, as_id(payload.child_id), "Child")
    assert_school_access(current_teacher, child.school_id)
    assert_school_admin(current_teacher)
    if not child.is_active:
        raise HTTPException(status_code=409, detail="Child is archived")
    if not child.guardian_line_user_id:
        raise HTTPException(status_code=409, detail="Guardian LINE linking is required before issuing an archive URL")

    now = utc_now()
    expires_in_hours = payload.expires_in_hours or settings.guardian_archive_link_ttl_hours
    db.execute(
        update(GuardianArchiveLink)
        .where(GuardianArchiveLink.child_id == child.id)
        .where(GuardianArchiveLink.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    token = generate_guardian_archive_token()
    link = GuardianArchiveLink(
        school_id=child.school_id,
        child_id=child.id,
        created_by_teacher_id=current_teacher.teacher.id if current_teacher.teacher else None,
        token_hash=hash_guardian_archive_token(token),
        expires_at=now + timedelta(hours=expires_in_hours),
    )
    db.add(link)
    add_audit_event(
        db,
        school_id=child.school_id,
        action=AuditEventAction.guardian_archive_issued,
        target_type="guardian_archive",
        current_teacher=current_teacher,
    )
    db.commit()
    db.refresh(link)
    credential = guardian_archive_link_read(link).model_dump()
    archive_url = f"{settings.guardian_archive_base_url.rstrip('/')}/guardian/#{token}"
    return GuardianArchiveLinkCredential(**credential, archive_url=archive_url)


@router.post(
    "/guardian-archive-links/{link_id}/revoke",
    response_model=GuardianArchiveLinkRead,
    tags=["guardian archive"],
)
def revoke_guardian_archive_link(
    link_id: str,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> GuardianArchiveLinkRead:
    """Immediately invalidate a leaked or no-longer-needed archive URL."""

    link = require_entity(db, GuardianArchiveLink, link_id, "Guardian archive link")
    assert_school_access(current_teacher, link.school_id)
    assert_school_admin(current_teacher)
    if link.revoked_at is None:
        link.revoked_at = utc_now()
        add_audit_event(
            db,
            school_id=link.school_id,
            action=AuditEventAction.guardian_archive_revoked,
            target_type="guardian_archive",
            current_teacher=current_teacher,
        )
        db.commit()
        db.refresh(link)
    return guardian_archive_link_read(link)


@router.get("/guardian/archive", response_model=GuardianArchiveRead, tags=["guardian archive"])
def get_guardian_archive(
    archive_link: GuardianArchiveLink = Depends(require_guardian_archive_link),
    db: Session = Depends(get_db),
) -> GuardianArchiveRead:
    """Return only delivered notices for the one child bound to the URL."""

    child = require_entity(db, Child, archive_link.child_id, "Guardian archive")
    rows = db.execute(
        select(Notification, Record)
        .join(Record, Notification.record_id == Record.id)
        .where(Record.school_id == archive_link.school_id)
        .where(Record.child_id == archive_link.child_id)
        .where(Notification.status == NotificationStatus.sent)
        .where(Notification.sent_at.is_not(None))
        .order_by(Notification.sent_at.desc())
    ).all()
    return GuardianArchiveRead(
        child_display_name=child.display_name,
        expires_at=as_utc_datetime(archive_link.expires_at),
        notifications=[
            GuardianArchiveNotificationRead(
                delivered_at=as_utc_datetime(notification.sent_at),
                category=record.category,
                summary=record.summary,
                conversation_prompt=record.conversation_prompt,
            )
            for notification, record in rows
            if notification.sent_at is not None
        ],
    )


@router.post("/records", response_model=RecordRead, status_code=status.HTTP_201_CREATED, tags=["records"])
def create_record_candidate(
    payload: RecordCreate,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Record:
    """Persist a privacy-filtered result produced by the local edge pipeline."""

    school_id = as_id(payload.school_id)
    teacher_id = as_id(payload.teacher_id)
    child_id = as_id(payload.child_id) if payload.child_id else None
    assert_school_access(current_teacher, school_id)
    if (
        not current_teacher.is_development
        and not current_teacher.is_school_admin
        and current_teacher.teacher is not None
        and teacher_id != current_teacher.teacher.id
    ):
        raise HTTPException(status_code=403, detail="A teacher can only create their own record candidates")
    require_entity(db, School, school_id, "School")
    teacher = require_entity(db, Teacher, teacher_id, "Teacher")
    if teacher.school_id != school_id:
        raise HTTPException(status_code=422, detail="Teacher does not belong to this school")
    if not teacher.is_active:
        raise HTTPException(status_code=422, detail="Teacher account is disabled")
    if child_id:
        require_active_child_for_school(db, child_id, school_id)

    record = Record(
        **{
            **payload.model_dump(exclude={"school_id", "teacher_id", "child_id"}),
            "school_id": school_id,
            "teacher_id": teacher_id,
            "child_id": child_id,
        }
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="source_event_id was already processed") from error
    db.refresh(record)
    return record


@router.post("/records/manual", response_model=RecordRead, status_code=status.HTTP_201_CREATED, tags=["records"])
def create_manual_record_candidate(
    payload: ManualRecordCreate,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Record:
    """Create a reviewed-before-delivery record when no audio candidate exists."""

    school_id = as_id(payload.school_id)
    child_id = as_id(payload.child_id)
    assert_school_access(current_teacher, school_id)
    require_entity(db, School, school_id, "School")
    require_active_child_for_school(db, child_id, school_id)
    if current_teacher.is_development:
        if payload.teacher_id is None:
            raise HTTPException(status_code=422, detail="A teacher must be selected in development mode")
        teacher_id = as_id(payload.teacher_id)
    else:
        assert current_teacher.teacher is not None
        teacher_id = current_teacher.teacher.id

    teacher = require_entity(db, Teacher, teacher_id, "Teacher")
    if teacher.school_id != school_id:
        raise HTTPException(status_code=422, detail="Teacher does not belong to this school")
    if not teacher.is_active:
        raise HTTPException(status_code=422, detail="Teacher account is disabled")
    occurred_at = as_utc_datetime(payload.occurred_at)
    if occurred_at > utc_now():
        raise HTTPException(status_code=422, detail="Manual record time cannot be in the future")

    record = Record(
        school_id=school_id,
        teacher_id=teacher_id,
        child_id=child_id,
        category=payload.category,
        confidence=1.0,
        occurred_at=occurred_at,
        summary=payload.summary,
        conversation_prompt=payload.conversation_prompt,
    )
    db.add(record)
    add_audit_event(
        db,
        school_id=school_id,
        action=AuditEventAction.manual_record_created,
        target_type="record",
        current_teacher=current_teacher,
    )
    db.commit()
    db.refresh(record)
    return record


@router.post("/edge/records", response_model=RecordRead, status_code=status.HTTP_201_CREATED, tags=["edge"])
def create_edge_record_candidate(
    payload: EdgeRecordCreate,
    current_device: CurrentEdgeDevice = Depends(get_current_edge_device),
    db: Session = Depends(get_db),
) -> Record:
    """Accept an anonymized candidate without giving the device user privileges."""
    device = current_device.device
    child_id = as_id(payload.child_id) if payload.child_id else None
    if child_id:
        require_active_child_for_school(db, child_id, device.school_id)

    record = Record(
        **{
            **payload.model_dump(exclude={"child_id"}),
            "school_id": device.school_id,
            "teacher_id": device.teacher_id,
            "child_id": child_id,
        }
    )
    device.last_seen_at = utc_now()
    db.add(record)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="source_event_id was already processed") from error
    db.refresh(record)
    return record


@router.post(
    "/edge/audio-jobs",
    response_model=CloudAudioJobRead,
    status_code=status.HTTP_201_CREATED,
    tags=["cloud audio"],
)
async def create_cloud_audio_job(
    request: Request,
    audio: UploadFile = File(...),
    child_id: str | None = Form(default=None),
    edge_upload_id: str | None = Header(default=None, alias="X-Edge-Upload-Id"),
    current_device: CurrentEdgeDevice = Depends(get_current_edge_device),
    db: Session = Depends(get_db),
) -> CloudAudioJob:
    """Accept one short audio chunk for the opt-in cloud GPU worker.

    The upload filename is discarded. The bytes remain only in the private job
    directory until the worker succeeds, fails, or expires the job.
    """

    settings = request.app.state.settings
    if not settings.cloud_audio_enabled:
        await audio.close()
        raise HTTPException(status_code=403, detail="Cloud audio processing is disabled")

    device = current_device.device
    if edge_upload_id is not None:
        try:
            edge_upload_id = str(UUID(edge_upload_id))
        except ValueError as error:
            await audio.close()
            raise HTTPException(status_code=422, detail="X-Edge-Upload-Id must be a UUID") from error
        existing_job = db.scalar(
            select(CloudAudioJob).where(
                CloudAudioJob.device_id == device.id,
                CloudAudioJob.edge_upload_id == edge_upload_id,
            )
        )
        if existing_job is not None:
            device.last_seen_at = utc_now()
            db.commit()
            await audio.close()
            db.refresh(existing_job)
            return existing_job

    safe_child_id = as_id(child_id) if child_id else None
    if safe_child_id:
        try:
            require_active_child_for_school(db, safe_child_id, device.school_id)
        except HTTPException:
            await audio.close()
            raise

    now = utc_now()
    job = CloudAudioJob(
        school_id=device.school_id,
        teacher_id=device.teacher_id,
        device_id=device.id,
        child_id=safe_child_id,
        edge_upload_id=edge_upload_id,
        # Replaced after the file is atomically stored. This provisional value is never returned.
        storage_key=f"pending-{uuid4()}",
        status=CloudAudioJobStatus.queued,
        expires_at=now + timedelta(minutes=settings.cloud_audio_job_retention_minutes),
    )
    storage = cloud_audio_storage(request)
    storage_key: str | None = None
    try:
        db.add(job)
        db.flush()
        storage_key = await storage.store_upload(upload=audio, job_id=job.id)
        job.storage_key = storage_key
        device.last_seen_at = now
        db.commit()
    except CloudAudioStorageError as error:
        db.rollback()
        if storage_key:
            storage.delete(storage_key)
        raise HTTPException(status_code=422, detail=str(error)) from error
    except IntegrityError as error:
        db.rollback()
        if storage_key:
            storage.delete(storage_key)
        raise HTTPException(status_code=409, detail="Cloud audio job could not be created") from error
    except OSError as error:
        db.rollback()
        if storage_key:
            storage.delete(storage_key)
        raise HTTPException(status_code=503, detail="Cloud audio storage is unavailable") from error
    finally:
        await audio.close()
    db.refresh(job)
    return job


@router.get("/edge/audio-jobs/{job_id}", response_model=CloudAudioJobRead, tags=["cloud audio"])
def get_cloud_audio_job(
    job_id: str,
    current_device: CurrentEdgeDevice = Depends(get_current_edge_device),
    db: Session = Depends(get_db),
) -> CloudAudioJob:
    """Show one device's job metadata without revealing the original audio location."""

    job = require_entity(db, CloudAudioJob, job_id, "Cloud audio job")
    if job.device_id != current_device.device.id:
        raise HTTPException(status_code=404, detail="Cloud audio job not found")
    return job


@router.get("/audio-jobs", response_model=list[CloudAudioJobRead], tags=["cloud audio"])
def list_cloud_audio_jobs(
    school_id: str,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> list[CloudAudioJob]:
    """List safe cloud-audio processing metadata for the teacher dashboard."""

    assert_school_access(current_teacher, school_id)
    query = select(CloudAudioJob).where(CloudAudioJob.school_id == school_id)
    if (
        not current_teacher.is_development
        and not current_teacher.is_school_admin
        and current_teacher.teacher is not None
    ):
        query = query.where(CloudAudioJob.teacher_id == current_teacher.teacher.id)
    return list(db.scalars(query.order_by(CloudAudioJob.queued_at.desc())))


@router.get("/edge/me", response_model=EdgeDeviceRead, tags=["edge"])
def get_edge_device_profile(
    current_device: CurrentEdgeDevice = Depends(get_current_edge_device),
) -> EdgeDevice:
    """Confirm a device key without accepting or creating any record."""
    return current_device.device


@router.post("/edge/heartbeat", response_model=EdgeDeviceRead, tags=["edge"])
def record_edge_device_heartbeat(
    current_device: CurrentEdgeDevice = Depends(get_current_edge_device),
    db: Session = Depends(get_db),
) -> EdgeDevice:
    """Record that an authenticated recording device is reachable.

    The request intentionally contains no audio, filename, transcript, or
    child-related data. It only refreshes the device's safe operational status.
    """

    device = current_device.device
    device.last_seen_at = utc_now()
    db.commit()
    db.refresh(device)
    return device


@router.get("/records", response_model=list[RecordRead], tags=["records"])
def list_records(
    school_id: str,
    record_status: RecordStatus | None = None,
    category: RecordCategory | None = None,
    child_id: str | None = None,
    search: str | None = Query(default=None, max_length=120),
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> list[Record]:
    """List a teacher's records, including delivered and archived-child history."""

    query = filtered_records_query(
        db=db,
        school_id=school_id,
        record_status=record_status,
        category=category,
        child_id=child_id,
        search=search,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        current_teacher=current_teacher,
    )
    return list(db.scalars(query.order_by(Record.occurred_at.desc()).limit(limit)))


@router.get("/records/export.csv", tags=["records"])
def export_record_history_csv(
    school_id: str,
    record_status: RecordStatus | None = None,
    category: RecordCategory | None = None,
    child_id: str | None = None,
    search: str | None = Query(default=None, max_length=120),
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Response:
    """Export up to 1,000 matching records without internal or guardian credentials."""

    assert_school_admin(current_teacher)
    query = filtered_records_query(
        db=db,
        school_id=school_id,
        record_status=record_status,
        category=category,
        child_id=child_id,
        search=search,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        current_teacher=current_teacher,
    )
    records = list(db.scalars(query.order_by(Record.occurred_at.desc()).limit(1_000)))
    children = {
        child.id: child.display_name
        for child in db.scalars(select(Child).where(Child.school_id == school_id))
    }
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["発生日時", "園児", "種別", "状態", "信頼度", "保護者へ伝える内容", "会話のきっかけ", "確認日時"])
    for record in records:
        writer.writerow(
            [
                as_utc_datetime(record.occurred_at).isoformat(),
                csv_cell(children.get(record.child_id, "園児未選択")),
                "怪我" if record.category == RecordCategory.injury else "成長記録",
                {
                    RecordStatus.pending_review: "レビュー待ち",
                    RecordStatus.approved: "承認済み",
                    RecordStatus.rejected: "却下",
                    RecordStatus.dispatched: "配信済み",
                }[record.status],
                record.confidence,
                csv_cell(record.summary),
                csv_cell(record.conversation_prompt),
                as_utc_datetime(record.reviewed_at).isoformat() if record.reviewed_at else "",
            ]
        )

    add_audit_event(
        db,
        school_id=school_id,
        action=AuditEventAction.record_history_exported,
        target_type="record_history",
        current_teacher=current_teacher,
    )
    db.commit()
    return Response(
        content=f"\ufeff{output.getvalue()}",
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="small-step-record-history.csv"'},
    )


@router.post("/records/{record_id}/approve", response_model=RecordRead, tags=["records"])
def approve_record(
    record_id: str,
    payload: RecordReview,
    request: Request,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Record:
    record = require_entity(db, Record, record_id, "Record")
    assert_record_access(current_teacher, record)
    if record.status != RecordStatus.pending_review:
        raise HTTPException(status_code=409, detail="Only pending records can be approved")

    if payload.child_id:
        child = require_active_child_for_school(db, as_id(payload.child_id), record.school_id)
        record.child_id = as_id(payload.child_id)
    if record.child_id is None:
        raise HTTPException(status_code=422, detail="A child must be selected before approval")
    if payload.summary is not None:
        record.summary = payload.summary
    if payload.conversation_prompt is not None:
        record.conversation_prompt = payload.conversation_prompt

    record.status = RecordStatus.approved
    record.reviewed_at = utc_now()
    child = require_entity(db, Child, record.child_id, "Child")
    if not child.is_active:
        raise HTTPException(status_code=409, detail="Child is archived")
    if payload.scheduled_for:
        scheduled_for = payload.scheduled_for
    elif record.category == RecordCategory.injury:
        scheduled_for = utc_now()
    else:
        settings = request.app.state.settings
        school = require_entity(db, School, record.school_id, "School")
        scheduled_for = get_next_digest_time(utc_now(), school.timezone or settings.timezone, school.digest_time)

    recipient_line_user_id = child.guardian_line_user_id
    notification = Notification(
        record_id=record.id,
        recipient_line_user_id=recipient_line_user_id,
        status=(
            NotificationStatus.pending
            if recipient_line_user_id
            else NotificationStatus.waiting_guardian_link
        ),
        scheduled_for=scheduled_for,
    )
    db.add(notification)
    add_audit_event(
        db,
        school_id=record.school_id,
        action=AuditEventAction.record_approved,
        target_type="record",
        current_teacher=current_teacher,
    )
    db.commit()
    db.refresh(record)
    return record


@router.post("/records/{record_id}/reject", response_model=RecordRead, tags=["records"])
def reject_record(
    record_id: str,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Record:
    record = require_entity(db, Record, record_id, "Record")
    assert_record_access(current_teacher, record)
    if record.status != RecordStatus.pending_review:
        raise HTTPException(status_code=409, detail="Only pending records can be rejected")
    record.status = RecordStatus.rejected
    record.reviewed_at = utc_now()
    add_audit_event(
        db,
        school_id=record.school_id,
        action=AuditEventAction.record_rejected,
        target_type="record",
        current_teacher=current_teacher,
    )
    db.commit()
    db.refresh(record)
    return record


@router.get("/notifications/ready", response_model=list[NotificationRead], tags=["notifications"])
def list_ready_notifications(
    now: datetime | None = None,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> list[Notification]:
    """LINE worker polls this endpoint and sends only the returned pending jobs."""

    assert_school_admin(current_teacher)
    effective_now = now or utc_now()
    query = (
        select(Notification)
        .join(Record, Notification.record_id == Record.id)
        .where(Notification.status == NotificationStatus.pending)
        .where(Notification.scheduled_for <= effective_now)
    )
    if not current_teacher.is_development:
        query = query.where(Record.school_id == current_teacher.school_id)
    return list(
        db.scalars(query.order_by(Notification.scheduled_for))
    )


@router.get("/notifications", response_model=list[NotificationOverviewRead], tags=["notifications"])
def list_notification_overview(
    school_id: str,
    notification_status: NotificationStatus | None = None,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> list[NotificationOverviewRead]:
    """Show teachers a school-scoped delivery history without LINE user IDs."""

    assert_school_access(current_teacher, school_id)
    query = (
        select(Notification, Record, Child, NotionSync)
        .join(Record, Notification.record_id == Record.id)
        .outerjoin(Child, Child.id == Record.child_id)
        .outerjoin(NotionSync, NotionSync.record_id == Record.id)
        .where(Record.school_id == school_id)
    )
    if (
        not current_teacher.is_development
        and not current_teacher.is_school_admin
        and current_teacher.teacher is not None
    ):
        query = query.where(Record.teacher_id == current_teacher.teacher.id)
    if notification_status:
        query = query.where(Notification.status == notification_status)

    rows = db.execute(query.order_by(Notification.created_at.desc())).all()
    return [
        NotificationOverviewRead(
            id=notification.id,
            record_id=notification.record_id,
            channel=notification.channel,
            scheduled_for=as_utc_datetime(notification.scheduled_for),
            status=notification.status,
            delivery_attempts=notification.delivery_attempts,
            last_attempt_at=as_utc_datetime(notification.last_attempt_at) if notification.last_attempt_at else None,
            last_failure_kind=notification.last_failure_kind,
            sent_at=as_utc_datetime(notification.sent_at) if notification.sent_at else None,
            created_at=as_utc_datetime(notification.created_at),
            child_id=record.child_id,
            child_display_name=child.display_name if child is not None else None,
            category=record.category,
            summary=record.summary,
            notion_synced_at=as_utc_datetime(notion_sync.synced_at) if notion_sync is not None else None,
            notion_page_url=notion_sync.notion_page_url if notion_sync is not None else None,
        )
        for notification, record, child, notion_sync in rows
    ]


@router.get("/audit-events/export.csv", tags=["audit"])
def export_audit_history_csv(
    school_id: str,
    action: AuditEventAction | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Response:
    """Export up to 1,000 filtered operational events without record or guardian data."""

    query = filtered_audit_events_query(
        db=db,
        school_id=school_id,
        action=action,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        current_teacher=current_teacher,
    )
    rows = db.execute(query.order_by(AuditEvent.created_at.desc()).limit(1_000)).all()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["実行日時", "操作", "対象の種類", "実行者"])
    for event, actor_name in rows:
        writer.writerow(
            [
                as_utc_datetime(event.created_at).isoformat(),
                AUDIT_EVENT_LABELS.get(event.action, "運用操作を実行"),
                AUDIT_TARGET_LABELS.get(event.target_type, "運用対象"),
                csv_cell(actor_name or "システム"),
            ]
        )

    add_audit_event(
        db,
        school_id=school_id,
        action=AuditEventAction.audit_history_exported,
        target_type="audit_history",
        current_teacher=current_teacher,
    )
    db.commit()
    return Response(
        content=f"\ufeff{output.getvalue()}",
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="small-step-audit-history.csv"'},
    )


@router.get("/audit-events", response_model=list[AuditEventRead], tags=["audit"])
def list_audit_events(
    school_id: str,
    action: AuditEventAction | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> list[AuditEventRead]:
    """Show administrators a minimal history of security-relevant operations."""

    query = filtered_audit_events_query(
        db=db,
        school_id=school_id,
        action=action,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        current_teacher=current_teacher,
    )
    rows = db.execute(query.order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return [
        AuditEventRead(
            action=event.action,
            target_type=event.target_type,
            actor_display_name=actor_name,
            created_at=as_utc_datetime(event.created_at),
        )
        for event, actor_name in rows
    ]


@router.post("/notifications/{notification_id}/mark-sent", response_model=NotificationRead, tags=["notifications"])
def mark_notification_sent(
    notification_id: str,
    payload: NotificationSent,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Notification:
    notification = require_entity(db, Notification, notification_id, "Notification")
    assert_school_admin(current_teacher)
    record = require_entity(db, Record, notification.record_id, "Record")
    assert_school_access(current_teacher, record.school_id)
    if notification.status != NotificationStatus.pending:
        raise HTTPException(status_code=409, detail="Only pending notifications can be sent")
    now = utc_now()
    notification.delivery_attempts += 1
    notification.last_attempt_at = now
    notification.last_failure_kind = None
    notification.status = NotificationStatus.sent
    notification.provider_message_id = payload.provider_message_id
    notification.sent_at = now
    record.status = RecordStatus.dispatched
    db.commit()
    db.refresh(notification)
    return notification


@router.post("/notifications/{notification_id}/retry", response_model=NotificationRead, tags=["notifications"])
def retry_failed_notification(
    notification_id: str,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Notification:
    """Re-queue one failed LINE notification after an administrator confirms it."""

    notification = require_entity(db, Notification, notification_id, "Notification")
    assert_school_admin(current_teacher)
    record = require_entity(db, Record, notification.record_id, "Record")
    assert_school_access(current_teacher, record.school_id)
    if notification.status != NotificationStatus.failed:
        raise HTTPException(status_code=409, detail="Only failed notifications can be retried")
    if not notification.recipient_line_user_id:
        raise HTTPException(status_code=409, detail="The guardian LINE account is not linked")

    # Keep the notification ID so LINE receives the same retry key as the original attempt.
    notification.status = NotificationStatus.pending
    notification.scheduled_for = utc_now()
    notification.provider_message_id = None
    notification.sent_at = None
    notification.last_failure_kind = None
    add_audit_event(
        db,
        school_id=record.school_id,
        action=AuditEventAction.notification_retry_scheduled,
        target_type="notification",
        current_teacher=current_teacher,
    )
    db.commit()
    db.refresh(notification)
    return notification


@router.post("/notifications/{notification_id}/cancel", response_model=NotificationRead, tags=["notifications"])
def cancel_pending_notification(
    notification_id: str,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Notification:
    """Cancel a pending delivery, including one waiting for a guardian to link LINE."""

    notification = require_entity(db, Notification, notification_id, "Notification")
    assert_school_admin(current_teacher)
    record = require_entity(db, Record, notification.record_id, "Record")
    assert_school_access(current_teacher, record.school_id)
    if notification.status not in {NotificationStatus.pending, NotificationStatus.waiting_guardian_link}:
        raise HTTPException(status_code=409, detail="Only queued notifications can be cancelled")

    notification.status = NotificationStatus.cancelled
    notification.provider_message_id = None
    notification.sent_at = None
    notification.last_failure_kind = None
    add_audit_event(
        db,
        school_id=record.school_id,
        action=AuditEventAction.notification_cancelled,
        target_type="notification",
        current_teacher=current_teacher,
    )
    db.commit()
    db.refresh(notification)
    return notification


@router.patch("/notifications/{notification_id}/schedule", response_model=NotificationRead, tags=["notifications"])
def reschedule_pending_notification(
    notification_id: str,
    payload: NotificationReschedule,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> Notification:
    """Move a queued delivery to a future time, before or after guardian linking."""

    notification = require_entity(db, Notification, notification_id, "Notification")
    assert_school_admin(current_teacher)
    record = require_entity(db, Record, notification.record_id, "Record")
    assert_school_access(current_teacher, record.school_id)
    if notification.status not in {NotificationStatus.pending, NotificationStatus.waiting_guardian_link}:
        raise HTTPException(status_code=409, detail="Only queued notifications can be rescheduled")

    scheduled_for = as_utc_datetime(payload.scheduled_for)
    if scheduled_for <= utc_now():
        raise HTTPException(status_code=422, detail="The delivery time must be in the future")

    notification.scheduled_for = scheduled_for
    add_audit_event(
        db,
        school_id=record.school_id,
        action=AuditEventAction.notification_rescheduled,
        target_type="notification",
        current_teacher=current_teacher,
    )
    db.commit()
    db.refresh(notification)
    return notification


@router.post(
    "/records/{record_id}/notion-sync",
    response_model=NotionSyncRead,
    status_code=status.HTTP_201_CREATED,
    tags=["notion"],
)
def sync_delivered_record_to_notion(
    record_id: str,
    request: Request,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> NotionSync:
    """Create one Notion page after the matching LINE notice has been delivered."""

    record = require_entity(db, Record, record_id, "Record")
    assert_record_access(current_teacher, record)
    assert_school_admin(current_teacher)
    if record.status != RecordStatus.dispatched:
        raise HTTPException(status_code=409, detail="Only delivered records can be synced to Notion")

    existing_sync = db.scalar(select(NotionSync).where(NotionSync.record_id == record.id))
    if existing_sync is not None:
        return existing_sync

    notification = db.scalar(select(Notification).where(Notification.record_id == record.id))
    if notification is None or notification.status != NotificationStatus.sent or notification.sent_at is None:
        raise HTTPException(status_code=409, detail="The matching LINE notification has not been delivered")

    settings = request.app.state.settings
    if not settings.notion_api_token or not settings.notion_data_source_id:
        raise HTTPException(status_code=503, detail="Notion integration is not configured")

    school = require_entity(db, School, record.school_id, "School")
    child = db.get(Child, record.child_id) if record.child_id else None
    try:
        page_id, page_url = create_delivered_notification_page(
            api_token=settings.notion_api_token,
            data_source_id=settings.notion_data_source_id,
            school_name=school.name,
            child_name=child.display_name if child else None,
            record_id=record.id,
            category=record.category.value,
            occurred_at=record.occurred_at,
            reviewed_at=record.reviewed_at,
            sent_at=notification.sent_at,
            summary=record.summary,
            conversation_prompt=record.conversation_prompt,
            timeout_seconds=settings.notion_api_timeout_seconds,
        )
    except (httpx.HTTPError, NotionSyncError) as error:
        raise HTTPException(status_code=502, detail=f"Notion sync failed: {error}") from error

    sync = NotionSync(record_id=record.id, notion_page_id=page_id, notion_page_url=page_url)
    db.add(sync)
    add_audit_event(
        db,
        school_id=record.school_id,
        action=AuditEventAction.notion_synced,
        target_type="notion",
        current_teacher=current_teacher,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_sync = db.scalar(select(NotionSync).where(NotionSync.record_id == record.id))
        if existing_sync is not None:
            return existing_sync
        raise
    db.refresh(sync)
    return sync
