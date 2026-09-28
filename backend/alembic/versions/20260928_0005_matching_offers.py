"""matching offers

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-28 13:44:17.241759
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "offers",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("order_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("worker_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("wave", sa.SmallInteger(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assignment_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["assignment_id"], ["assignments.id"], name=op.f("fk_offers_assignment_id_assignments")
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("fk_offers_order_id_orders"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["worker_id"], ["users.id"], name=op.f("fk_offers_worker_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_offers")),
    )
    op.create_index(op.f("ix_offers_order_id"), "offers", ["order_id"], unique=False)
    op.create_index("ix_offers_status_expires", "offers", ["status", "expires_at"], unique=False)
    op.create_index(op.f("ix_offers_worker_id"), "offers", ["worker_id"], unique=False)
    op.add_column("orders", sa.Column("waves_sent", sa.SmallInteger(), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("last_wave_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("matching_alerted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("worker_profiles", sa.Column("reliability", sa.SmallInteger(), nullable=False, server_default="100"))
    op.add_column("worker_profiles", sa.Column("available_now_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "worker_profiles", sa.Column("missed_offers_streak", sa.SmallInteger(), nullable=False, server_default="0")
    )


def downgrade() -> None:
    op.drop_column("worker_profiles", "missed_offers_streak")
    op.drop_column("worker_profiles", "available_now_until")
    op.drop_column("worker_profiles", "reliability")
    op.drop_column("orders", "matching_alerted_at")
    op.drop_column("orders", "last_wave_at")
    op.drop_column("orders", "waves_sent")
    op.drop_index(op.f("ix_offers_worker_id"), table_name="offers")
    op.drop_index("ix_offers_status_expires", table_name="offers")
    op.drop_index(op.f("ix_offers_order_id"), table_name="offers")
    op.drop_table("offers")
