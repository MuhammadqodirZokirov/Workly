"""Ishchi: profil, jadval, fayllar va verifikatsiyaga yuborish (TZ 4-bo'lim)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from workly.domain.errors import Forbidden, InvalidState, NotFound, ValidationFailed
from workly.domain.phone import normalize_phone
from workly.domain.users import ConsentDoc, Role
from workly.domain.worker import (
    REQUIRED_FILES,
    DocType,
    Experience,
    FileKind,
    Gender,
    VerificationStatus,
    ensure_adult,
    ensure_transition,
    normalize_doc_number,
)
from workly.infrastructure.crypto import DataCipher
from workly.infrastructure.db.models import (
    Category,
    Consent,
    District,
    Region,
    Specialization,
    User,
    WorkerAvailability,
    WorkerDistrict,
    WorkerFile,
    WorkerProfile,
    WorkerSkill,
    WorkerSpecialization,
)
from workly.infrastructure.storage import FileStorage, sniff_image

from .audit import record_transition

TASHKENT = ZoneInfo("Asia/Tashkent")
REQUIRED_CONSENTS = {ConsentDoc.TERMS, ConsentDoc.PRIVACY, ConsentDoc.WORKER_CONTRACT}
MAX_SLOTS_PER_DAY = 3
# Tasdiqlangandan keyin hujjatdagi ma'lumotlarni o'zgartirib bo'lmaydi (qayta tekshiruvsiz)
LOCKED_WHEN_VERIFIED = ("full_name", "birth_date", "gender")
# Tekshiruv davomida fayl va hujjat o'zgarmasin
EDITABLE_FILE_STATES = {VerificationStatus.NOT_SUBMITTED, VerificationStatus.REJECTED, VerificationStatus.EXPIRED}


def today_tashkent() -> date:
    return datetime.now(TASHKENT).date()


@dataclass
class SkillInput:
    category_id: int
    experience: Experience
    specialization_ids: list[int]


@dataclass
class ProfileInput:
    full_name: str | None = None
    birth_date: date | None = None
    gender: Gender | None = None
    district_ids: list[int] | None = None
    home_point: tuple[float, float] | None = None
    clear_home_point: bool = False
    skills: list[SkillInput] | None = None
    emergency_name: str | None = None
    emergency_phone: str | None = None
    clear_emergency: bool = False


@dataclass
class SlotInput:
    weekday: int
    start: time
    end: time


class WorkerService:
    def __init__(
        self,
        db: AsyncSession,
        storage: FileStorage | None = None,
        cipher: DataCipher | None = None,
        max_upload_bytes: int = 5 * 1024 * 1024,
    ):
        self.db, self.storage, self.cipher = db, storage, cipher
        self.max_upload_bytes = max_upload_bytes

    # ---------- profil ----------
    async def get_profile(self, user: User, *, create: bool = False) -> WorkerProfile:
        if Role.WORKER not in user.role_names:
            raise Forbidden("Avval ishchi rolini qo'shing", code="NOT_A_WORKER")
        profile = await self.db.get(WorkerProfile, user.id)
        if profile is None:
            if not create:
                raise NotFound("Ishchi profili hali to'ldirilmagan", code="WORKER_PROFILE_NOT_FOUND")
            profile = WorkerProfile(user_id=user.id, user=user)
            self.db.add(profile)
            await self.db.flush()
        return profile

    async def update_profile(self, user: User, data: ProfileInput) -> WorkerProfile:
        profile = await self.get_profile(user, create=True)
        status = VerificationStatus(profile.verification_status)

        if status in (VerificationStatus.VERIFIED, VerificationStatus.PENDING):
            changed = [f for f in LOCKED_WHEN_VERIFIED if self._changes(user, profile, f, data)]
            if changed:
                raise InvalidState(
                    "Tekshiruvdan o'tgan ma'lumotni o'zgartirib bo'lmaydi. Qo'llab-quvvatlashga yozing",
                    code="PROFILE_LOCKED",
                    details={"fields": changed},
                )

        if data.full_name is not None:
            name = " ".join(data.full_name.split())
            if len(name) < 3:
                raise ValidationFailed("F.I.Sh to'liq kiritilsin", code="INVALID_FULL_NAME")
            user.full_name = name
        if data.birth_date is not None:
            ensure_adult(data.birth_date, today_tashkent())
            profile.birth_date = data.birth_date
        if data.gender is not None:
            profile.gender = data.gender
        if data.clear_home_point:
            profile.home_lat = profile.home_lon = None
        elif data.home_point is not None:
            profile.home_lat, profile.home_lon = data.home_point
        if data.clear_emergency:
            profile.emergency_name = profile.emergency_phone = None
        elif data.emergency_phone is not None:
            profile.emergency_name = (data.emergency_name or "").strip() or None
            profile.emergency_phone = normalize_phone(data.emergency_phone)
            if user.phone and profile.emergency_phone == user.phone:
                raise ValidationFailed("Favqulodda kontakt o'z raqamingiz bo'lmasin", code="INVALID_EMERGENCY")
        if data.district_ids is not None:
            await self._set_districts(profile, data.district_ids)
        if data.skills is not None:
            await self._set_skills(profile, data.skills)
        await self.db.flush()
        return profile

    @staticmethod
    def _changes(user: User, profile: WorkerProfile, field: str, data: ProfileInput) -> bool:
        new = getattr(data, field)
        if new is None:
            return False
        old = user.full_name if field == "full_name" else getattr(profile, field)
        if field == "full_name":
            new = " ".join(new.split())
        return new != old

    async def _set_districts(self, profile: WorkerProfile, ids: list[int]) -> None:
        ids = list(dict.fromkeys(ids))
        if not ids:
            raise ValidationFailed("Kamida bitta tuman tanlang", code="DISTRICTS_REQUIRED")
        found = set(
            (
                await self.db.scalars(
                    select(District.id)
                    .join(Region)
                    .where(District.id.in_(ids), District.is_active.is_(True), Region.is_active.is_(True))
                )
            ).all()
        )
        if missing := [i for i in ids if i not in found]:
            raise ValidationFailed("Tuman topilmadi yoki faol emas", code="INVALID_DISTRICT", details=missing)
        profile.districts = [WorkerDistrict(district_id=i) for i in ids]

    async def _set_skills(self, profile: WorkerProfile, skills: list[SkillInput]) -> None:
        if not skills:
            raise ValidationFailed("Kamida bitta kategoriya tanlang", code="SKILLS_REQUIRED")
        cat_ids = [s.category_id for s in skills]
        if len(set(cat_ids)) != len(cat_ids):
            raise ValidationFailed("Kategoriya takrorlangan", code="DUPLICATE_CATEGORY")
        active_cats = set(
            (
                await self.db.scalars(select(Category.id).where(Category.id.in_(cat_ids), Category.is_active.is_(True)))
            ).all()
        )
        spec_rows = {}
        all_spec_ids = [i for s in skills for i in s.specialization_ids]
        if all_spec_ids:
            spec_rows = {
                sp.id: sp
                for sp in (
                    await self.db.scalars(
                        select(Specialization).where(
                            Specialization.id.in_(all_spec_ids), Specialization.is_active.is_(True)
                        )
                    )
                ).all()
            }
        new_skills, new_specs = [], []
        for s in skills:
            if s.category_id not in active_cats:
                raise ValidationFailed(
                    "Kategoriya topilmadi yoki faol emas", code="INVALID_CATEGORY", details=[s.category_id]
                )
            if not s.specialization_ids:
                raise ValidationFailed(
                    "Har kategoriyada kamida bitta mutaxassislik tanlang",
                    code="SPECIALIZATION_REQUIRED",
                    details=[s.category_id],
                )
            for sid in dict.fromkeys(s.specialization_ids):
                spec = spec_rows.get(sid)
                if spec is None or spec.category_id != s.category_id:
                    raise ValidationFailed(
                        "Mutaxassislik bu kategoriyaga tegishli emas", code="INVALID_SPECIALIZATION", details=[sid]
                    )
                new_specs.append(WorkerSpecialization(category_id=s.category_id, specialization_id=sid))
            new_skills.append(WorkerSkill(category_id=s.category_id, experience=s.experience))
        profile.skills = new_skills
        profile.specializations = new_specs

    # ---------- jadval ----------
    async def set_availability(self, user: User, slots: list[SlotInput]) -> WorkerProfile:
        profile = await self.get_profile(user, create=True)
        by_day: dict[int, list[SlotInput]] = {}
        for s in slots:
            if not 0 <= s.weekday <= 6:
                raise ValidationFailed("Hafta kuni 0 (dushanba) – 6 (yakshanba)", code="INVALID_SLOT")
            if s.start >= s.end:
                raise ValidationFailed("Boshlanish vaqti tugashdan oldin bo'lsin", code="INVALID_SLOT")
            by_day.setdefault(s.weekday, []).append(s)
        for day, items in by_day.items():
            if len(items) > MAX_SLOTS_PER_DAY:
                raise ValidationFailed(
                    f"Bir kunda {MAX_SLOTS_PER_DAY} tadan ko'p oraliq bo'lmasin", code="INVALID_SLOT", details=[day]
                )
            items.sort(key=lambda x: x.start)
            if any(a.end > b.start for a, b in zip(items, items[1:], strict=False)):
                raise ValidationFailed("Vaqt oraliqlari kesishmasin", code="INVALID_SLOT", details=[day])
        profile.availability = [
            WorkerAvailability(weekday=s.weekday, start=s.start, end=s.end)
            for s in sorted(slots, key=lambda x: (x.weekday, x.start))
        ]
        await self.db.flush()
        return profile

    # ---------- fayllar ----------
    async def list_files(self, user_id: int) -> list[WorkerFile]:
        rows = await self.db.scalars(
            select(WorkerFile)
            .where(WorkerFile.user_id == user_id, WorkerFile.deleted_at.is_(None))
            .order_by(WorkerFile.kind)
        )
        return list(rows)

    async def upload_file(self, user: User, kind: FileKind, data: bytes) -> tuple[WorkerFile, list[str]]:
        """Yangi faylni saqlaydi. Qaytaradi: (yangi fayl, o'chirilishi kerak bo'lgan eski kalitlar).
        Eski nusxalarni chaqiruvchi commit'dan KEYIN o'chiradi — rollback bo'lsa ma'lumot yo'qolmasin."""
        profile = await self.get_profile(user, create=True)
        extra_kinds = {FileKind.QUALIFICATION, FileKind.CRIMINAL_RECORD}
        if kind not in extra_kinds and VerificationStatus(profile.verification_status) not in EDITABLE_FILE_STATES:
            raise InvalidState("Hujjatlar tekshiruvda yoki tasdiqlangan — o'zgartirib bo'lmaydi", code="FILES_LOCKED")
        if not data:
            raise ValidationFailed("Fayl bo'sh", code="EMPTY_FILE")
        if len(data) > self.max_upload_bytes:
            raise ValidationFailed(
                "Fayl hajmi juda katta", code="FILE_TOO_LARGE", details={"max_bytes": self.max_upload_bytes}
            )
        content_type = sniff_image(data)
        allowed = {"image/jpeg", "image/png", "image/webp"}
        if kind in extra_kinds:
            allowed = allowed | {"application/pdf"}
        if content_type not in allowed:
            raise ValidationFailed("Faqat JPEG, PNG yoki WEBP rasm (guvohnoma uchun PDF ham)", code="UNSUPPORTED_FILE")

        key = await self.storage.save(data, prefix=f"workers/{user.id}")
        now = datetime.now(UTC)
        old = await self.db.scalars(
            select(WorkerFile).where(
                WorkerFile.user_id == user.id, WorkerFile.kind == kind, WorkerFile.deleted_at.is_(None)
            )
        )
        old_keys = []
        for f in old:
            f.deleted_at = now
            old_keys.append(f.storage_key)
        new = WorkerFile(user_id=user.id, kind=kind, storage_key=key, content_type=content_type, size=len(data))
        self.db.add(new)
        await self.db.flush()
        return new, old_keys

    # ---------- verifikatsiyaga yuborish ----------
    async def submit_verification(self, user: User, doc_type: DocType, raw_doc_number: str) -> WorkerProfile:
        profile = await self.get_profile(user)
        ensure_transition(profile.verification_status, VerificationStatus.PENDING)

        missing = []
        if not user.full_name:
            missing.append("full_name")
        if profile.birth_date is None:
            missing.append("birth_date")
        if profile.gender is None:
            missing.append("gender")
        if not profile.skills:
            missing.append("skills")
        if not profile.districts:
            missing.append("districts")
        if user.phone_verified_at is None:
            missing.append("phone")
        kinds = {f.kind for f in await self.list_files(user.id)}
        missing += sorted(f"file:{k}" for k in REQUIRED_FILES[doc_type] - kinds)
        accepted = set((await self.db.scalars(select(Consent.doc_type).where(Consent.user_id == user.id))).all())
        missing += sorted(f"consent:{c}" for c in REQUIRED_CONSENTS - accepted)
        if missing:
            raise ValidationFailed("Profil to'liq emas", code="PROFILE_INCOMPLETE", details=missing)
        ensure_adult(profile.birth_date, today_tashkent())

        number = normalize_doc_number(raw_doc_number)
        doc_hash = self.cipher.keyed_hash(number)
        # Takroriy akkaunt — avtomatik aniqlanadi, qarorni moderator qabul qiladi
        duplicate = await self.db.scalar(
            select(WorkerProfile.user_id)
            .where(
                WorkerProfile.doc_number_hash == doc_hash,
                WorkerProfile.user_id != user.id,
                WorkerProfile.verification_status.in_(
                    [VerificationStatus.PENDING, VerificationStatus.VERIFIED, VerificationStatus.EXPIRED]
                ),
            )
            .limit(1)
        )

        old_status = profile.verification_status
        profile.doc_type = doc_type
        profile.doc_number_enc = self.cipher.encrypt_str(number)
        profile.doc_number_hash = doc_hash
        profile.duplicate_of_user_id = duplicate
        profile.verification_status = VerificationStatus.PENDING
        profile.submitted_at = datetime.now(UTC)
        profile.rejection_reason = profile.rejection_comment = None
        record_transition(self.db, "worker_verification", user.id, old_status, VerificationStatus.PENDING, user.id)
        await self.db.flush()
        return profile
