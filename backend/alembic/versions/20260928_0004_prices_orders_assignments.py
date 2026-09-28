"""prices orders assignments

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-28 13:13:32.459003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("employer_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("specialization_id", sa.Integer(), nullable=False),
        sa.Column("workers_count", sa.SmallInteger(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration", sa.String(length=12), nullable=True),
        sa.Column("days", sa.SmallInteger(), nullable=False),
        sa.Column("volume", sa.String(length=16), nullable=True),
        sa.Column("is_night", sa.Boolean(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("district_id", sa.Integer(), nullable=False),
        sa.Column("address_text", sa.String(length=300), nullable=False),
        sa.Column("landmark", sa.String(length=200), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("tools_by", sa.String(length=10), nullable=False),
        sa.Column("lunch", sa.Boolean(), nullable=False),
        sa.Column("transport", sa.Boolean(), nullable=False),
        sa.Column("top_only", sa.Boolean(), nullable=False),
        sa.Column("payment_mode", sa.String(length=8), nullable=False),
        sa.Column("price", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], name=op.f("fk_orders_category_id_categories")),
        sa.ForeignKeyConstraint(["district_id"], ["districts.id"], name=op.f("fk_orders_district_id_districts")),
        sa.ForeignKeyConstraint(["employer_id"], ["users.id"], name=op.f("fk_orders_employer_id_users")),
        sa.ForeignKeyConstraint(
            ["specialization_id"], ["specializations.id"], name=op.f("fk_orders_specialization_id_specializations")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
    )
    op.create_index(op.f("ix_orders_district_id"), "orders", ["district_id"], unique=False)
    op.create_index(op.f("ix_orders_employer_id"), "orders", ["employer_id"], unique=False)
    op.create_index(op.f("ix_orders_starts_at"), "orders", ["starts_at"], unique=False)
    op.create_index(op.f("ix_orders_status"), "orders", ["status"], unique=False)
    op.create_table(
        "price_configs",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("specialization_id", sa.Integer(), nullable=True),
        sa.Column("unit", sa.String(length=8), nullable=False),
        sa.Column("base", sa.BigInteger(), nullable=False),
        sa.Column("min_price", sa.BigInteger(), nullable=False),
        sa.Column("max_price", sa.BigInteger(), nullable=False),
        sa.Column("min_order_amount", sa.BigInteger(), nullable=False),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], name=op.f("fk_price_configs_category_id_categories")
        ),
        sa.ForeignKeyConstraint(
            ["specialization_id"],
            ["specializations.id"],
            name=op.f("fk_price_configs_specialization_id_specializations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price_configs")),
    )
    op.create_index(op.f("ix_price_configs_category_id"), "price_configs", ["category_id"], unique=False)
    op.create_table(
        "assignments",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("order_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("slot_no", sa.SmallInteger(), nullable=False),
        sa.Column("worker_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("fk_assignments_order_id_orders"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["worker_id"], ["users.id"], name=op.f("fk_assignments_worker_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignments")),
        sa.UniqueConstraint("order_id", "slot_no", name=op.f("uq_assignments_order_id")),
    )
    op.create_index(op.f("ix_assignments_order_id"), "assignments", ["order_id"], unique=False)
    op.create_index(op.f("ix_assignments_status"), "assignments", ["status"], unique=False)
    op.create_index(op.f("ix_assignments_worker_id"), "assignments", ["worker_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_assignments_worker_id"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_status"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_order_id"), table_name="assignments")
    op.drop_table("assignments")
    op.drop_index(op.f("ix_price_configs_category_id"), table_name="price_configs")
    op.drop_table("price_configs")
    op.drop_index(op.f("ix_orders_status"), table_name="orders")
    op.drop_index(op.f("ix_orders_starts_at"), table_name="orders")
    op.drop_index(op.f("ix_orders_employer_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_district_id"), table_name="orders")
    op.drop_table("orders")
