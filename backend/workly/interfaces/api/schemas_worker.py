from datetime import date, datetime, time

from pydantic import BaseModel, Field, model_validator

from workly.domain.worker import Badge, DocType, Experience, FileKind, Gender, RejectReason


class GeoPoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class EmergencyContact(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    phone: str = Field(max_length=32)


class SkillIn(BaseModel):
    category_id: int
    experience: Experience
    specialization_ids: list[int] = Field(min_length=1, max_length=20)


class WorkerProfileIn(BaseModel):
    """Qisman yangilash: yuborilmagan maydon o'zgarmaydi; home_point/emergency_contact = null — o'chiradi."""

    last_name: str | None = Field(default=None, max_length=60)
    first_name: str | None = Field(default=None, max_length=60)
    middle_name: str | None = Field(default=None, max_length=60)
    birth_date: date | None = None
    gender: Gender | None = None
    district_ids: list[int] | None = Field(default=None, max_length=30)
    home_point: GeoPoint | None = None
    skills: list[SkillIn] | None = Field(default=None, max_length=10)
    emergency_contact: EmergencyContact | None = None


class SlotIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start: time
    end: time


class AvailabilityIn(BaseModel):
    slots: list[SlotIn] = Field(max_length=21)


class SkillOut(BaseModel):
    category_id: int
    experience: Experience
    specialization_ids: list[int]


class FileOut(BaseModel):
    id: int
    kind: FileKind
    content_type: str
    size: int
    created_at: datetime


class VerificationOut(BaseModel):
    status: str
    doc_type: DocType | None
    submitted_at: datetime | None
    verified_at: datetime | None
    rejection_reason: str | None
    rejection_comment: str | None


class WorkerProfileOut(BaseModel):
    user_id: int
    last_name: str | None
    first_name: str | None
    middle_name: str | None
    full_name: str | None
    birth_date: date | None
    gender: Gender | None
    district_ids: list[int]
    home_point: GeoPoint | None
    skills: list[SkillOut]
    availability: list[SlotIn]
    emergency_contact: EmergencyContact | None
    badges: list[Badge]
    verification: VerificationOut
    files: list[FileOut]

    @classmethod
    def of(cls, p, files) -> "WorkerProfileOut":
        spec_by_cat: dict[int, list[int]] = {}
        for sp in p.specializations:
            spec_by_cat.setdefault(sp.category_id, []).append(sp.specialization_id)
        return cls(
            user_id=p.user_id,
            last_name=p.last_name,
            first_name=p.first_name,
            middle_name=p.middle_name,
            full_name=p.user.full_name,
            birth_date=p.birth_date,
            gender=p.gender,
            district_ids=[d.district_id for d in p.districts],
            home_point=GeoPoint(lat=p.home_lat, lon=p.home_lon) if p.home_lat is not None else None,
            skills=[
                SkillOut(
                    category_id=s.category_id,
                    experience=s.experience,
                    specialization_ids=spec_by_cat.get(s.category_id, []),
                )
                for s in p.skills
            ],
            availability=[
                SlotIn(weekday=a.weekday, start=a.start, end=a.end)
                for a in sorted(p.availability, key=lambda a: (a.weekday, a.start))
            ],
            emergency_contact=EmergencyContact(name=p.emergency_name, phone=p.emergency_phone)
            if p.emergency_phone
            else None,
            badges=p.badges or [],
            verification=VerificationOut(
                status=p.verification_status,
                doc_type=p.doc_type,
                submitted_at=p.submitted_at,
                verified_at=p.verified_at,
                rejection_reason=p.rejection_reason,
                rejection_comment=p.rejection_comment,
            ),
            files=[
                FileOut(id=f.id, kind=f.kind, content_type=f.content_type, size=f.size, created_at=f.created_at)
                for f in files
            ],
        )


class SubmitIn(BaseModel):
    doc_type: DocType
    doc_number: str = Field(min_length=5, max_length=20)


# ---------- moderator ----------
class QueueItem(BaseModel):
    user_id: int
    full_name: str | None
    age: int | None
    submitted_at: datetime | None
    duplicate_of_user_id: int | None


class FileLink(FileOut):
    url: str
    expires_at: int


class CaseOut(BaseModel):
    profile: WorkerProfileOut
    phone: str | None
    doc_number: str | None
    duplicate_of_user_id: int | None
    files: list[FileLink]


class ApproveIn(BaseModel):
    badges: list[Badge] = Field(default_factory=list)


class RejectIn(BaseModel):
    reason: RejectReason
    comment: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _strip(self):
        if self.comment is not None:
            self.comment = self.comment.strip() or None
        return self


# ---------- ommaviy rezyume ----------
class ResumeSkill(BaseModel):
    category_id: int
    experience: Experience
    specialization_ids: list[int]


class ResumeStats(BaseModel):
    rating: float | None
    reviews_count: int
    reliability: int
    completed_jobs: int
    no_shows_90d: int
    avg_response_minutes: float | None


class ResumeOut(BaseModel):
    worker_id: int
    display_name: str | None
    avatar_url: str | None
    is_new: bool
    badges: list[Badge]
    skills: list[ResumeSkill]
    district_ids: list[int]
    stats: ResumeStats
    recent_reviews: list = []
