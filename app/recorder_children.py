"""School-scoped, non-authoritative child references for browser recordings."""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Child

if TYPE_CHECKING:
    from app.edge_audio import EdgeAudioCandidate


REFERENCE_PATTERN = re.compile(r"園児候補_[0-9]+")


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    return "".join(chr(ord(char) - 0x60) if "ァ" <= char <= "ヶ" else char for char in value)


def name_variants_pattern(name: str) -> str:
    return "".join(
        f"[{char}{chr(ord(char) + 0x60)}]" if "ぁ" <= char <= "ゖ" else re.escape(char)
        for char in name
    )


class RecorderChildMatcher:
    """Replace registered names before inference; retain IDs only for advice."""

    def __init__(self, *, db: Session, school_id: str) -> None:
        self.school_id = school_id
        self.names: dict[str, set[str]] = {}
        self.active_ids: set[str] = set()
        self.references: dict[str, str] = {}
        self.current: set[str] = set()
        self.matches: set[str] = set()
        self.blocked = False
        # Archived children also block same-name matches, but cannot be advised.
        for child in db.scalars(select(Child).where(Child.school_id == school_id).execution_options(populate_existing=True)):
            if child.is_active:
                self.active_ids.add(child.id)
            for name in [child.display_name, *(child.recording_names or [])]:
                name = normalize_name(name).strip()
                if len(name) >= 2:
                    self.names.setdefault(name, set()).add(child.id)
        self.patterns = [
            (name, re.compile(
                r"(?<![ぁ-ゖァ-ヺ一-龯々A-Za-z])" + re.escape(name)
                + r"(?=ちゃん|くん|君|さん|が|は|[、。，,.!?！？\s]|$)"
            ))
            for name in sorted(self.names, key=len, reverse=True)
        ]

    def prepare(self, transcript: str) -> str:
        self.current.clear()
        # Do not accept a reference spoken/injected by the recording itself.
        text = REFERENCE_PATTERN.sub("園児", normalize_name(transcript))
        for name, pattern in self.patterns:
            ids = self.names[name]

            def replace(_match: re.Match[str]) -> str:
                if len(ids) != 1 or not ids <= self.active_ids:
                    self.blocked = True
                    return "園児"
                child_id = next(iter(ids))
                if child_id not in self.references and len(self.references) >= 999:
                    self.blocked = True
                    return "園児"
                self.current.add(child_id)
                reference = f"園児候補_{len(self.references) + 1:03d}"
                reference = self.references.setdefault(child_id, reference)
                return reference

            text = pattern.sub(replace, text)
        if len(self.current) > 1:
            self.blocked = True
        return text

    def process(self, candidate: EdgeAudioCandidate) -> EdgeAudioCandidate:
        if candidate.recordable:
            reference_to_id = {value: key for key, value in self.references.items()}
            child_id = reference_to_id.get(candidate.subject_reference)
            if len(self.current) != 1 or child_id not in self.current:
                self.blocked = True
            else:
                self.matches.add(child_id)
        fields: dict[str, object] = {"subject_reference": None}
        for field in ("summary", "conversation_prompt", "anonymized_context"):
            value = getattr(candidate, field)
            if value is not None:
                value = unicodedata.normalize("NFKC", value)
                # Remove every known school name, including malformed contexts.
                for name in sorted(self.names, key=len, reverse=True):
                    value = re.sub(name_variants_pattern(name), "園児", value)
                fields[field] = REFERENCE_PATTERN.sub("園児", value)
        return candidate.model_copy(update=fields)

    def candidate(self, db: Session) -> str | None:
        if self.blocked or len(self.matches) != 1:
            return None
        child_id = next(iter(self.matches))
        child = db.get(Child, child_id, populate_existing=True)
        if child is None or child.school_id != self.school_id or not child.is_active:
            return None
        fresh = RecorderChildMatcher(db=db, school_id=self.school_id)
        try:
            if fresh.names != self.names or fresh.active_ids != self.active_ids:
                return None
        finally:
            fresh.clear()
        return child_id

    def clear(self) -> None:
        self.names.clear()
        self.patterns.clear()
        self.references.clear()
        self.current.clear()
        self.matches.clear()
        self.active_ids.clear()
