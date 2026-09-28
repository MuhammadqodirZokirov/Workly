from datetime import datetime

from pydantic import BaseModel, Field

from workly.domain.employer import BusinessRejectReason, EmployerBadge, EmployerType

from .schemas_worker import GeoPoint


class EmployerProfileIn(BaseModel):
    """Qisman yangilash; district_id/point = null — o'chiradi."""

    type: EmployerType | None = None
    company_name: str | None = Field(default=None, max_length=200)
    stir: str | None = Field(default=None, max_length=20)
    activity: str | None = Field(default=None, max_length=200)
    address_text: str | None = Field(default=None, max_length=300)
    district_id: int | None = None
    point: GeoPoint | None = None


class BusinessVerificationOut(BaseModel):
    status: str
    submitted_at: datetime | None
    verified_at: datetime | None
    rejection_reason: str | None
    rejection_comment: str | None


class EmployerProfileOut(BaseModel):
    user_id: int
    type: EmployerType
    full_name: str | None  # jismoniy shaxs yoki biznesda mas'ul shaxs
    company_name: str | None
    stir: str | None
    activity: str | None
    address_text: str | None
    district_id: int | None
    point: GeoPoint | None
    badges: list[EmployerBadge]
    business_verification: BusinessVerificationOut | None

    @classmethod
    def of(cls, p) -> "EmployerProfileOut":
        business = p.type == EmployerType.BUSINESS
        return cls(
            user_id=p.user_id,
            type=p.type,
            full_name=p.user.full_name,
            company_name=p.company_name,
            stir=p.stir,
            activity=p.activity,
            address_text=p.address_text,
            district_id=p.district_id,
            point=GeoPoint(lat=p.lat, lon=p.lon) if p.lat is not None else None,
            badges=p.badges or [],
            business_verification=BusinessVerificationOut(
                status=p.business_status,
                submitted_at=p.submitted_at,
                verified_at=p.verified_at,
                rejection_reason=p.rejection_reason,
                rejection_comment=p.rejection_comment,
            )
            if business
            else None,
        )


class BusinessQueueItem(BaseModel):
    user_id: int
    company_name: str | None
    stir: str | None
    responsible: str | None
    phone: str | None
    submitted_at: datetime | None
    same_stir_user_ids: list[int]


class BusinessRejectIn(BaseModel):
    reason: BusinessRejectReason
    comment: str | None = Field(default=None, max_length=500)
