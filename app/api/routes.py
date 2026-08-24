from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, text
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
from app.edge_keys import generate_edge_api_key, hash_edge_api_key
from app.models import (
    Child,
    EdgeDevice,
    Notification,
    NotificationStatus,
    Record,
    RecordCategory,
    RecordStatus,
    School,
    Teacher,
    TeacherRole,
    utc_now,
)
from app.schemas import (
    ChildCreate,
    ChildRead,
    EdgeDeviceCreate,
    EdgeDeviceCredential,
    EdgeDeviceRead,
    EdgeRecordCreate,
    NotificationRead,
    NotificationSent,
    RecordCreate,
    RecordRead,
    RecordReview,
    SchoolCreate,
    SchoolRead,
    TeacherCreate,
    TeacherRead,
)

router = APIRouter(prefix="/api/v1")


def as_id(value: object) -> str:
    return str(value)


def require_entity(db: Session, model: type, entity_id: str, label: str):
    entity = db.get(model, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return entity


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


@router.get("/health", tags=["system"])
def health_check(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.post("/schools", response_model=SchoolRead, status_code=status.HTTP_201_CREATED, tags=["schools"])
def create_school(
    payload: SchoolCreate,
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
) -> School:
    if request.app.state.settings.auth_mode == "supabase" and not is_bootstrap_admin(request, user):
        raise HTTPException(status_code=403, detail="Only a configured bootstrap administrator can create the first school")

    school = School(**payload.model_dump(exclude={"initial_admin_name"}))
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


@router.post("/auth/link-teacher", response_model=TeacherRead, tags=["auth"])
def link_supabase_user_to_teacher(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
) -> Teacher:
    """Link a signed-in user to a teacher record pre-registered by a school admin."""

    teacher = db.scalar(select(Teacher).where(Teacher.auth_user_id == user.id))
    if teacher:
        return teacher

    teacher = db.scalar(select(Teacher).where(Teacher.email == user.email))
    if teacher is None:
        raise HTTPException(status_code=404, detail="No pre-registered teacher account exists for this email")
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

    api_key = generate_edge_api_key()
    device = EdgeDevice(
        school_id=school_id,
        teacher_id=teacher_id,
        name=payload.name,
        api_key_hash=hash_edge_api_key(api_key),
    )
    db.add(device)
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
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> list[Child]:
    assert_school_access(current_teacher, school_id)
    return list(
        db.scalars(select(Child).where(Child.school_id == school_id).order_by(Child.display_name))
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
    if child_id:
        child = require_entity(db, Child, child_id, "Child")
        if child.school_id != school_id:
            raise HTTPException(status_code=422, detail="Child does not belong to this school")

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
        child = require_entity(db, Child, child_id, "Child")
        if child.school_id != device.school_id:
            raise HTTPException(status_code=422, detail="Child does not belong to this school")

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


@router.get("/edge/me", response_model=EdgeDeviceRead, tags=["edge"])
def get_edge_device_profile(
    current_device: CurrentEdgeDevice = Depends(get_current_edge_device),
) -> EdgeDevice:
    """Confirm a device key without accepting or creating any record."""
    return current_device.device


@router.get("/records", response_model=list[RecordRead], tags=["records"])
def list_records(
    school_id: str,
    record_status: RecordStatus | None = None,
    category: RecordCategory | None = None,
    current_teacher: CurrentTeacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> list[Record]:
    assert_school_access(current_teacher, school_id)
    query = select(Record).where(Record.school_id == school_id)
    if not current_teacher.is_development and not current_teacher.is_school_admin:
        query = query.where(Record.teacher_id == current_teacher.teacher.id)
    if record_status:
        query = query.where(Record.status == record_status)
    if category:
        query = query.where(Record.category == category)
    return list(db.scalars(query.order_by(Record.occurred_at.desc())))


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
        child = require_entity(db, Child, as_id(payload.child_id), "Child")
        if child.school_id != record.school_id:
            raise HTTPException(status_code=422, detail="Child does not belong to this school")
        record.child_id = as_id(payload.child_id)
    if payload.summary is not None:
        record.summary = payload.summary
    if payload.conversation_prompt is not None:
        record.conversation_prompt = payload.conversation_prompt

    record.status = RecordStatus.approved
    record.reviewed_at = utc_now()
    child = db.get(Child, record.child_id) if record.child_id else None
    if payload.scheduled_for:
        scheduled_for = payload.scheduled_for
    elif record.category == RecordCategory.injury:
        scheduled_for = utc_now()
    else:
        settings = request.app.state.settings
        school = require_entity(db, School, record.school_id, "School")
        scheduled_for = get_next_digest_time(utc_now(), school.timezone or settings.timezone, settings.digest_time)

    notification = Notification(
        record_id=record.id,
        recipient_line_user_id=child.guardian_line_user_id if child else None,
        scheduled_for=scheduled_for,
    )
    db.add(notification)
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
    notification.status = NotificationStatus.sent
    notification.provider_message_id = payload.provider_message_id
    notification.sent_at = utc_now()
    record.status = RecordStatus.dispatched
    db.commit()
    db.refresh(notification)
    return notification
