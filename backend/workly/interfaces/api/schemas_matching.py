from datetime import datetime

from pydantic import BaseModel

from workly.domain.orders import ToolsBy
from workly.domain.pricing import Duration

from .schemas_worker import GeoPoint


class EmployerBrief(BaseModel):
    name: str | None
    verified: bool


class JobCard(BaseModel):
    """Taklif/lenta kartasi: aniq manzil va telefon yo'q (tayinlovdan keyin ochiladi)."""

    order_id: int
    category_id: int
    specialization_id: int
    district_id: int
    distance_km: float | None
    starts_at: datetime
    duration: Duration | None
    days: int
    is_night: bool
    lunch: bool
    transport: bool
    tools_by: ToolsBy
    worker_net: int  # "Siz olasiz"
    open_slots: int
    employer: EmployerBrief
    description: str | None


class OfferOut(JobCard):
    offer_id: int
    expires_at: datetime


class WorkerAssignmentOut(JobCard):
    assignment_id: int
    status: str
    address_text: str
    landmark: str | None
    point: GeoPoint
    employer_phone: str | None


class AvailabilityStatusIn(BaseModel):
    available_now: bool


class AvailabilityStatusOut(BaseModel):
    available_now: bool
    until: datetime | None
