from datetime import date, datetime, time

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BigIntPK, TimestampMixin, utcnow


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    phone: Mapped[str | None] = mapped_column(String(16), unique=True)
    phone_verified_at: Mapped[datetime | None]
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str | None] = mapped_column(String(200))
    lang: Mapped[str] = mapped_column(String(8), default="uz_latn")
    status: Mapped[str] = mapped_column(String(16), default="active")
    deleted_at: Mapped[datetime | None]

    roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
        foreign_keys="UserRole.user_id",
    )

    def __init__(self, **kwargs):
        # Yangi obyektda kolleksiya bo'sh bo'lsin — aks holda async sessiyada lazy-load urinishi bo'ladi
        kwargs.setdefault("roles", [])
        super().__init__(**kwargs)

    @property
    def role_names(self) -> list[str]:
        return sorted(r.role for r in self.roles)


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    granted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    user: Mapped[User] = relationship(back_populates="roles", foreign_keys=[user_id])


class AuthSession(Base):
    """Refresh token sessiyasi (qurilma bo'yicha). Token o'zi emas, faqat hash saqlanadi."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    refresh_hash: Mapped[str] = mapped_column(String(64), unique=True)
    device: Mapped[str | None] = mapped_column(String(200))
    ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_used_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    doc_type: Mapped[str] = mapped_column(String(32))
    version: Mapped[str] = mapped_column(String(16))
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    accepted_at: Mapped[datetime] = mapped_column(default=utcnow)


class NamedMixin:
    name_uz_latn: Mapped[str] = mapped_column(String(120))
    name_uz_cyrl: Mapped[str] = mapped_column(String(120))
    name_ru: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    def name(self, lang: str) -> str:
        return getattr(self, f"name_{lang}", None) or self.name_uz_latn


class Region(NamedMixin, Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    districts: Mapped[list["District"]] = relationship(back_populates="region", order_by="District.sort_order")


class District(NamedMixin, Base):
    __tablename__ = "districts"
    __table_args__ = (UniqueConstraint("region_id", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    code: Mapped[str] = mapped_column(String(32))
    region: Mapped[Region] = relationship(back_populates="districts")


class Category(NamedMixin, Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    specializations: Mapped[list["Specialization"]] = relationship(
        back_populates="category", order_by="Specialization.sort_order", lazy="selectin"
    )


class Specialization(NamedMixin, Base):
    __tablename__ = "specializations"
    __table_args__ = (UniqueConstraint("category_id", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    code: Mapped[str] = mapped_column(String(32))
    category: Mapped[Category] = relationship(back_populates="specializations")


# ---------------- Ishchi (TZ 4-bo'lim) ----------------
class WorkerProfile(TimestampMixin, Base):
    __tablename__ = "worker_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    # Hujjatdagidek; users.full_name = "Familiya Ism Otasining ismi"
    last_name: Mapped[str | None] = mapped_column(String(60))
    first_name: Mapped[str | None] = mapped_column(String(60))
    middle_name: Mapped[str | None] = mapped_column(String(60))
    birth_date: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(8))
    # TODO(2-blok, matching): PostGIS geography(Point) ga o'tkazish
    home_lat: Mapped[float | None] = mapped_column(Float)
    home_lon: Mapped[float | None] = mapped_column(Float)
    emergency_name: Mapped[str | None] = mapped_column(String(120))
    emergency_phone: Mapped[str | None] = mapped_column(String(16))

    verification_status: Mapped[str] = mapped_column(String(16), default="not_submitted", index=True)
    doc_type: Mapped[str | None] = mapped_column(String(16))
    doc_number_enc: Mapped[str | None] = mapped_column(Text)
    doc_number_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    submitted_at: Mapped[datetime | None]
    verified_at: Mapped[datetime | None]
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    rejection_reason: Mapped[str | None] = mapped_column(String(32))
    rejection_comment: Mapped[str | None] = mapped_column(String(500))
    duplicate_of_user_id: Mapped[int | None] = mapped_column(BigInteger)
    badges: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Matching (TZ 4, 7, 11)
    reliability: Mapped[int] = mapped_column(SmallInteger, default=100)
    available_now_until: Mapped[datetime | None]  # "Hozir bo'shman"
    missed_offers_streak: Mapped[int] = mapped_column(SmallInteger, default=0)

    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="joined")
    skills: Mapped[list["WorkerSkill"]] = relationship(lazy="selectin", cascade="all, delete-orphan")
    specializations: Mapped[list["WorkerSpecialization"]] = relationship(lazy="selectin", cascade="all, delete-orphan")
    districts: Mapped[list["WorkerDistrict"]] = relationship(lazy="selectin", cascade="all, delete-orphan")
    availability: Mapped[list["WorkerAvailability"]] = relationship(lazy="selectin", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        for name in ("skills", "specializations", "districts", "availability", "badges"):
            kwargs.setdefault(name, [])
        super().__init__(**kwargs)


class WorkerSkill(Base):
    """Kategoriya bo'yicha tajriba."""

    __tablename__ = "worker_skills"
    __table_args__ = (UniqueConstraint("user_id", "category_id"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("worker_profiles.user_id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    experience: Mapped[str] = mapped_column(String(8))


class WorkerSpecialization(Base):
    __tablename__ = "worker_specializations"
    __table_args__ = (UniqueConstraint("user_id", "specialization_id"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("worker_profiles.user_id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))  # matching uchun denormalizatsiya
    specialization_id: Mapped[int] = mapped_column(ForeignKey("specializations.id"), index=True)


class WorkerDistrict(Base):
    __tablename__ = "worker_districts"
    __table_args__ = (UniqueConstraint("user_id", "district_id"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("worker_profiles.user_id", ondelete="CASCADE"), index=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id"), index=True)


class WorkerAvailability(Base):
    """Haftalik jadval: weekday 0 = dushanba."""

    __tablename__ = "worker_availability"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("worker_profiles.user_id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(SmallInteger)
    start: Mapped[time] = mapped_column(Time)
    end: Mapped[time] = mapped_column(Time)


class WorkerFile(Base):
    """Hujjat, selfie va guvohnoma fayllari (shifrlangan). Faqat moderator imzoli havola bilan ko'radi."""

    __tablename__ = "worker_documents"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    storage_key: Mapped[str] = mapped_column(String(200), unique=True)
    content_type: Mapped[str] = mapped_column(String(40))
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    deleted_at: Mapped[datetime | None]


# ---------------- Tizim (TZ 17-bo'lim) ----------------
class StateTransition(Base):
    __tablename__ = "state_transitions"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    object_type: Mapped[str] = mapped_column(String(32))
    object_id: Mapped[int] = mapped_column(BigInteger)
    from_state: Mapped[str | None] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[int | None] = mapped_column(BigInteger)
    reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (Index("ix_state_transitions_object", "object_type", "object_id"),)


class AuditLog(Base):
    """O'zgarmas jurnal: admin harakatlari va shaxsiy ma'lumotni ko'rish."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(64))
    object_type: Mapped[str] = mapped_column(String(32))
    object_id: Mapped[int | None] = mapped_column(BigInteger)
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


# ---------------- Ish beruvchi (TZ 5-bo'lim) ----------------
class EmployerProfile(TimestampMixin, Base):
    __tablename__ = "employer_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    type: Mapped[str] = mapped_column(String(16), default="individual")
    # biznes
    company_name: Mapped[str | None] = mapped_column(String(200))
    stir: Mapped[str | None] = mapped_column(String(9), index=True)
    activity: Mapped[str | None] = mapped_column(String(200))
    # manzil (jismoniy shaxsda ixtiyoriy)
    address_text: Mapped[str | None] = mapped_column(String(300))
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    # biznes STIR tekshiruvi
    business_status: Mapped[str] = mapped_column(String(16), default="not_submitted", index=True)
    submitted_at: Mapped[datetime | None]
    verified_at: Mapped[datetime | None]
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    rejection_reason: Mapped[str | None] = mapped_column(String(32))
    rejection_comment: Mapped[str | None] = mapped_column(String(500))
    badges: Mapped[list[str]] = mapped_column(JSON, default=list)

    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="joined")

    def __init__(self, **kwargs):
        kwargs.setdefault("badges", [])
        super().__init__(**kwargs)


# ---------------- Narx va buyurtma (TZ 5–8-bo'limlar) ----------------
class PriceConfigRow(Base):
    """Narx sozlamasi versiyasi. Yangi narx — yangi qator (active_from); eski buyurtmalar o'z nusxasini saqlaydi."""

    __tablename__ = "price_configs"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    specialization_id: Mapped[int | None] = mapped_column(ForeignKey("specializations.id"))  # null — kategoriya
    unit: Mapped[str] = mapped_column(String(8))
    base: Mapped[int] = mapped_column(BigInteger)
    min_price: Mapped[int] = mapped_column(BigInteger)
    max_price: Mapped[int] = mapped_column(BigInteger)
    min_order_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    active_from: Mapped[datetime] = mapped_column(default=utcnow)
    created_by: Mapped[int | None] = mapped_column(BigInteger)


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    specialization_id: Mapped[int] = mapped_column(ForeignKey("specializations.id"))
    workers_count: Mapped[int] = mapped_column(SmallInteger)
    starts_at: Mapped[datetime] = mapped_column(index=True)
    duration: Mapped[str | None] = mapped_column(String(12))
    days: Mapped[int] = mapped_column(SmallInteger, default=1)
    volume: Mapped[str | None] = mapped_column(String(16))  # Decimal matn ko'rinishida
    is_night: Mapped[bool] = mapped_column(Boolean, default=False)
    # manzil (TODO(matching): PostGIS geography)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id"), index=True)
    address_text: Mapped[str] = mapped_column(String(300))
    landmark: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(500))
    tools_by: Mapped[str] = mapped_column(String(10), default="employer")
    lunch: Mapped[bool] = mapped_column(Boolean, default=False)
    transport: Mapped[bool] = mapped_column(Boolean, default=False)
    top_only: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_mode: Mapped[str] = mapped_column(String(8), default="cash")
    price: Mapped[dict] = mapped_column(JSON)  # narx nusxasi: sozlama o'zgarsa buyurtma o'zgarmaydi
    status: Mapped[str] = mapped_column(String(20), index=True)
    cancelled_at: Mapped[datetime | None]
    cancel_reason: Mapped[str | None] = mapped_column(String(300))
    # matching
    waves_sent: Mapped[int] = mapped_column(SmallInteger, default=0)
    last_wave_at: Mapped[datetime | None]
    matching_alerted_at: Mapped[datetime | None]

    assignments: Mapped[list["Assignment"]] = relationship(
        back_populates="order", lazy="selectin", cascade="all, delete-orphan", order_by="Assignment.slot_no"
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("assignments", [])
        super().__init__(**kwargs)


class Assignment(TimestampMixin, Base):
    """Buyurtmadagi bitta ishchi o'rni. Ko'p kunlik ishda kunlar keyingi bosqichda (assignment_days)."""

    __tablename__ = "assignments"
    __table_args__ = (UniqueConstraint("order_id", "slot_no"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    slot_no: Mapped[int] = mapped_column(SmallInteger)
    worker_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)

    order: Mapped[Order] = relationship(back_populates="assignments")


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (Index("ix_offers_status_expires", "status", "expires_at"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    wave: Mapped[int] = mapped_column(SmallInteger)  # 0 — ochiq lentadan
    score: Mapped[float | None] = mapped_column(Float)
    distance_km: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(10), default="sent")
    sent_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]
    responded_at: Mapped[datetime | None]
    assignment_id: Mapped[int | None] = mapped_column(ForeignKey("assignments.id"))
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)

    order: Mapped[Order] = relationship(lazy="joined")
