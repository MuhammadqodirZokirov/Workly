"""initial users auth catalog

Revision ID: 0001
Revises:
Create Date: 2026-09-28 12:22:14.326079
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name_uz_latn", sa.String(length=120), nullable=False),
        sa.Column("name_uz_cyrl", sa.String(length=120), nullable=False),
        sa.Column("name_ru", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("code", name=op.f("uq_categories_code")),
    )
    op.create_table(
        "regions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name_uz_latn", sa.String(length=120), nullable=False),
        sa.Column("name_uz_cyrl", sa.String(length=120), nullable=False),
        sa.Column("name_ru", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_regions")),
        sa.UniqueConstraint("code", name=op.f("uq_regions_code")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("phone", sa.String(length=16), nullable=True),
        sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_username", sa.String(length=64), nullable=True),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("lang", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("phone", name=op.f("uq_users_phone")),
        sa.UniqueConstraint("telegram_id", name=op.f("uq_users_telegram_id")),
    )
    op.create_table(
        "consents",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("doc_type", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=16), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_consents_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consents")),
    )
    op.create_index(op.f("ix_consents_user_id"), "consents", ["user_id"], unique=False)
    op.create_table(
        "districts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name_uz_latn", sa.String(length=120), nullable=False),
        sa.Column("name_uz_cyrl", sa.String(length=120), nullable=False),
        sa.Column("name_ru", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], name=op.f("fk_districts_region_id_regions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_districts")),
        sa.UniqueConstraint("region_id", "code", name=op.f("uq_districts_region_id")),
    )
    op.create_index(op.f("ix_districts_region_id"), "districts", ["region_id"], unique=False)
    op.create_table(
        "sessions",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("refresh_hash", sa.String(length=64), nullable=False),
        sa.Column("device", sa.String(length=200), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("refresh_hash", name=op.f("uq_sessions_refresh_hash")),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_table(
        "specializations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name_uz_latn", sa.String(length=120), nullable=False),
        sa.Column("name_uz_cyrl", sa.String(length=120), nullable=False),
        sa.Column("name_ru", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], name=op.f("fk_specializations_category_id_categories")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_specializations")),
        sa.UniqueConstraint("category_id", "code", name=op.f("uq_specializations_category_id")),
    )
    op.create_index(op.f("ix_specializations_category_id"), "specializations", ["category_id"], unique=False)
    op.create_table(
        "user_roles",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("granted_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], name=op.f("fk_user_roles_granted_by_users")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_roles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_roles")),
        sa.UniqueConstraint("user_id", "role", name=op.f("uq_user_roles_user_id")),
    )
    op.create_index(op.f("ix_user_roles_user_id"), "user_roles", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_roles_user_id"), table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index(op.f("ix_specializations_category_id"), table_name="specializations")
    op.drop_table("specializations")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_index(op.f("ix_districts_region_id"), table_name="districts")
    op.drop_table("districts")
    op.drop_index(op.f("ix_consents_user_id"), table_name="consents")
    op.drop_table("consents")
    op.drop_table("users")
    op.drop_table("regions")
    op.drop_table("categories")
