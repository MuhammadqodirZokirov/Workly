from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, UniqueConstraint
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
