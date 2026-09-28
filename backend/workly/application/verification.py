"""Moderator: verifikatsiya navbati, ko'rish, tasdiqlash va rad etish (TZ 4, 16-bo'limlar)."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from workly.domain.errors import NotFound, ValidationFailed
from workly.domain.worker import Badge, FileKind, RejectReason, VerificationStatus, ensure_transition
from workly.infrastructure.crypto import DataCipher
from workly.infrastructure.db.models import User, WorkerFile, WorkerProfile

from .audit import audit, record_transition


class VerificationService:
    def __init__(self, db: AsyncSession, cipher: DataCipher):
        self.db, self.cipher = db, cipher

    async def queue(
        self, status: VerificationStatus = VerificationStatus.PENDING, limit: int = 50, offset: int = 0
    ) -> list[WorkerProfile]:
        rows = await self.db.scalars(
            select(WorkerProfile)
            .where(WorkerProfile.verification_status == status)
            .order_by(WorkerProfile.submitted_at.asc().nulls_last(), WorkerProfile.user_id)
            .limit(limit)
            .offset(offset)
        )
        return list(rows)

    async def _profile(self, user_id: int) -> WorkerProfile:
        profile = await self.db.get(WorkerProfile, user_id)
        if profile is None:
            raise NotFound("Ishchi profili topilmadi")
        return profile

    async def open_case(
        self, moderator: User, user_id: int, ip: str | None
    ) -> tuple[WorkerProfile, str | None, list[WorkerFile]]:
        """Hujjat raqami va fayllarni ko'rsatadi; har ko'rish audit jurnaliga yoziladi (TZ 19-bo'lim)."""
        profile = await self._profile(user_id)
        files = list(
            await self.db.scalars(
                select(WorkerFile).where(WorkerFile.user_id == user_id, WorkerFile.deleted_at.is_(None))
            )
        )
        doc_number = self.cipher.decrypt_str(profile.doc_number_enc) if profile.doc_number_enc else None
        audit(
            self.db, moderator.id, "verification.view", "worker", user_id, ip=ip, after={"files": [f.id for f in files]}
        )
        await self.db.flush()
        return profile, doc_number, files

    async def approve(self, moderator: User, user_id: int, badges: list[Badge], ip: str | None) -> WorkerProfile:
        profile = await self._profile(user_id)
        ensure_transition(profile.verification_status, VerificationStatus.VERIFIED)
        if badges:
            kinds = {
                f.kind
                for f in await self.db.scalars(
                    select(WorkerFile).where(WorkerFile.user_id == user_id, WorkerFile.deleted_at.is_(None))
                )
            }
            need = {Badge.QUALIFIED: FileKind.QUALIFICATION, Badge.BACKGROUND_CHECKED: FileKind.CRIMINAL_RECORD}
            if missing := [b for b in badges if need[b] not in kinds]:
                raise ValidationFailed(
                    "Belgi uchun tasdiqlovchi hujjat yuklanmagan", code="BADGE_WITHOUT_FILE", details=missing
                )
        before = {"status": profile.verification_status, "badges": list(profile.badges)}
        profile.verification_status = VerificationStatus.VERIFIED
        profile.verified_at = datetime.now(UTC)
        profile.verified_by = moderator.id
        profile.badges = sorted(set(profile.badges) | set(badges))
        record_transition(
            self.db, "worker_verification", user_id, before["status"], VerificationStatus.VERIFIED, moderator.id
        )
        audit(
            self.db,
            moderator.id,
            "verification.approve",
            "worker",
            user_id,
            ip=ip,
            before=before,
            after={"status": VerificationStatus.VERIFIED, "badges": profile.badges},
        )
        await self.db.flush()
        return profile

    async def reject(
        self, moderator: User, user_id: int, reason: RejectReason, comment: str | None, ip: str | None
    ) -> WorkerProfile:
        profile = await self._profile(user_id)
        ensure_transition(profile.verification_status, VerificationStatus.REJECTED)
        if reason == RejectReason.OTHER and not (comment and comment.strip()):
            raise ValidationFailed("'Boshqa' sababda izoh majburiy", code="COMMENT_REQUIRED")
        old = profile.verification_status
        profile.verification_status = VerificationStatus.REJECTED
        profile.rejection_reason = reason
        profile.rejection_comment = (comment or "").strip() or None
        record_transition(
            self.db, "worker_verification", user_id, old, VerificationStatus.REJECTED, moderator.id, reason=reason
        )
        audit(
            self.db,
            moderator.id,
            "verification.reject",
            "worker",
            user_id,
            ip=ip,
            before={"status": old},
            after={"status": VerificationStatus.REJECTED, "reason": reason},
        )
        await self.db.flush()
        return profile
