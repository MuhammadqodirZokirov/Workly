"""Ish beruvchi: profil va biznes (STIR) tekshiruvi (TZ 5-bo'lim)."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from workly.domain.employer import BusinessRejectReason, EmployerBadge, EmployerType, normalize_stir
from workly.domain.errors import Forbidden, InvalidState, NotFound, ValidationFailed
from workly.domain.users import ConsentDoc, Role
from workly.domain.worker import VerificationStatus, ensure_transition
from workly.infrastructure.db.models import Consent, District, EmployerProfile, Region, User

from .audit import audit, record_transition

REQUIRED_CONSENTS = {ConsentDoc.TERMS, ConsentDoc.PRIVACY, ConsentDoc.EMPLOYER_CONTRACT}
LOCKED_BUSINESS_FIELDS = ("type", "company_name", "stir")
_UNSET = object()


@dataclass
class EmployerInput:
    type: EmployerType | None = None
    company_name: str | None = None
    stir: str | None = None
    activity: str | None = None
    address_text: str | None = None
    district_id: int | None | object = _UNSET
    point: tuple[float, float] | None | object = _UNSET


class EmployerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_profile(self, user: User, *, create: bool = False) -> EmployerProfile:
        if Role.EMPLOYER not in user.role_names:
            raise Forbidden("Avval ish beruvchi rolini qo'shing", code="NOT_AN_EMPLOYER")
        profile = await self.db.get(EmployerProfile, user.id)
        if profile is None:
            if not create:
                raise NotFound("Ish beruvchi profili topilmadi", code="EMPLOYER_PROFILE_NOT_FOUND")
            profile = EmployerProfile(user_id=user.id, user=user, type=EmployerType.INDIVIDUAL)
            self.db.add(profile)
            await self.db.flush()
        return profile

    async def update_profile(self, user: User, data: EmployerInput) -> EmployerProfile:
        profile = await self.get_profile(user, create=True)
        new_stir = normalize_stir(data.stir) if data.stir is not None else None
        new_company = " ".join(data.company_name.split()) if data.company_name is not None else None

        if profile.business_status in (VerificationStatus.PENDING, VerificationStatus.VERIFIED):
            proposed = {"type": data.type, "company_name": new_company, "stir": new_stir}
            changed = [
                f for f in LOCKED_BUSINESS_FIELDS if proposed[f] is not None and proposed[f] != getattr(profile, f)
            ]
            if changed:
                raise InvalidState(
                    "Tekshiruvdagi yoki tasdiqlangan kompaniya ma'lumotini o'zgartirib bo'lmaydi",
                    code="PROFILE_LOCKED",
                    details={"fields": changed},
                )

        if data.type is not None and data.type != profile.type:
            profile.type = data.type
            if data.type == EmployerType.INDIVIDUAL:
                profile.company_name = profile.stir = profile.activity = None
                profile.business_status = VerificationStatus.NOT_SUBMITTED
                profile.rejection_reason = profile.rejection_comment = None
        is_business = profile.type == EmployerType.BUSINESS
        if (new_company or new_stir or data.activity) and not is_business:
            raise ValidationFailed("Kompaniya ma'lumotlari faqat biznes uchun", code="NOT_A_BUSINESS")
        if new_company is not None:
            profile.company_name = new_company or None
        if new_stir is not None:
            profile.stir = new_stir
        if data.activity is not None:
            profile.activity = " ".join(data.activity.split()) or None
        if data.address_text is not None:
            profile.address_text = " ".join(data.address_text.split()) or None
        if data.district_id is not _UNSET:
            if data.district_id is not None:
                ok = await self.db.scalar(
                    select(District.id)
                    .join(Region)
                    .where(District.id == data.district_id, District.is_active.is_(True), Region.is_active.is_(True))
                )
                if ok is None:
                    raise ValidationFailed("Tuman topilmadi yoki faol emas", code="INVALID_DISTRICT")
            profile.district_id = data.district_id
        if data.point is not _UNSET:
            profile.lat, profile.lon = data.point if data.point is not None else (None, None)
        await self.db.flush()
        return profile

    async def submit_business(self, user: User) -> EmployerProfile:
        profile = await self.get_profile(user, create=True)
        if profile.type != EmployerType.BUSINESS:
            raise ValidationFailed("Faqat biznes STIR tekshiruvidan o'tadi", code="NOT_A_BUSINESS")
        ensure_transition(profile.business_status, VerificationStatus.PENDING)
        missing = [
            f
            for f in ("company_name", "stir", "activity", "address_text", "district_id")
            if getattr(profile, f) is None
        ]
        if not user.full_name:
            missing.append("full_name")  # mas'ul shaxs
        if user.phone_verified_at is None:
            missing.append("phone")
        accepted = set((await self.db.scalars(select(Consent.doc_type).where(Consent.user_id == user.id))).all())
        missing += sorted(f"consent:{c}" for c in REQUIRED_CONSENTS - accepted)
        if missing:
            raise ValidationFailed("Profil to'liq emas", code="PROFILE_INCOMPLETE", details=missing)
        old = profile.business_status
        profile.business_status = VerificationStatus.PENDING
        profile.submitted_at = datetime.now(UTC)
        profile.rejection_reason = profile.rejection_comment = None
        record_transition(self.db, "business_verification", user.id, old, VerificationStatus.PENDING, user.id)
        await self.db.flush()
        return profile


class BusinessModerationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def queue(self, status: VerificationStatus, limit: int, offset: int) -> list[EmployerProfile]:
        rows = await self.db.scalars(
            select(EmployerProfile)
            .where(EmployerProfile.type == EmployerType.BUSINESS, EmployerProfile.business_status == status)
            .order_by(EmployerProfile.submitted_at.asc().nulls_last(), EmployerProfile.user_id)
            .limit(limit)
            .offset(offset)
        )
        return list(rows)

    async def same_stir_users(self, profile: EmployerProfile) -> list[int]:
        """Shu STIR bilan boshqa akkauntlar — moderator uchun ma'lumot (Faza 2 da bir kompaniyada bir necha menejer)."""
        rows = await self.db.scalars(
            select(EmployerProfile.user_id).where(
                EmployerProfile.stir == profile.stir, EmployerProfile.user_id != profile.user_id
            )
        )
        return list(rows)

    async def _profile(self, user_id: int) -> EmployerProfile:
        profile = await self.db.get(EmployerProfile, user_id)
        if profile is None or profile.type != EmployerType.BUSINESS:
            raise NotFound("Biznes profili topilmadi")
        return profile

    async def approve(self, moderator: User, user_id: int, ip: str | None) -> EmployerProfile:
        profile = await self._profile(user_id)
        ensure_transition(profile.business_status, VerificationStatus.VERIFIED)
        old = profile.business_status
        profile.business_status = VerificationStatus.VERIFIED
        profile.verified_at = datetime.now(UTC)
        profile.verified_by = moderator.id
        profile.badges = sorted(set(profile.badges) | {EmployerBadge.VERIFIED})
        record_transition(self.db, "business_verification", user_id, old, VerificationStatus.VERIFIED, moderator.id)
        audit(
            self.db,
            moderator.id,
            "business.approve",
            "employer",
            user_id,
            ip=ip,
            before={"status": old},
            after={"status": VerificationStatus.VERIFIED, "stir": profile.stir},
        )
        await self.db.flush()
        return profile

    async def reject(
        self, moderator: User, user_id: int, reason: BusinessRejectReason, comment: str | None, ip: str | None
    ) -> EmployerProfile:
        profile = await self._profile(user_id)
        ensure_transition(profile.business_status, VerificationStatus.REJECTED)
        if reason == BusinessRejectReason.OTHER and not comment:
            raise ValidationFailed("'Boshqa' sababda izoh majburiy", code="COMMENT_REQUIRED")
        old = profile.business_status
        profile.business_status = VerificationStatus.REJECTED
        profile.rejection_reason = reason
        profile.rejection_comment = comment
        record_transition(
            self.db, "business_verification", user_id, old, VerificationStatus.REJECTED, moderator.id, reason=reason
        )
        audit(
            self.db,
            moderator.id,
            "business.reject",
            "employer",
            user_id,
            ip=ip,
            before={"status": old},
            after={"status": VerificationStatus.REJECTED, "reason": reason},
        )
        await self.db.flush()
        return profile
