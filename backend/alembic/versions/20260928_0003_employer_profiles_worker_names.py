"""employer profiles worker names

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-28 13:04:22.624370
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employer_profiles",
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column("stir", sa.String(length=9), nullable=True),
        sa.Column("activity", sa.String(length=200), nullable=True),
        sa.Column("address_text", sa.String(length=300), nullable=True),
        sa.Column("district_id", sa.Integer(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("business_status", sa.String(length=16), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("rejection_reason", sa.String(length=32), nullable=True),
        sa.Column("rejection_comment", sa.String(length=500), nullable=True),
        sa.Column("badges", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["district_id"], ["districts.id"], name=op.f("fk_employer_profiles_district_id_districts")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_employer_profiles_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], name=op.f("fk_employer_profiles_verified_by_users")),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_employer_profiles")),
    )
    op.create_index(
        op.f("ix_employer_profiles_business_status"), "employer_profiles", ["business_status"], unique=False
    )
    op.create_index(op.f("ix_employer_profiles_stir"), "employer_profiles", ["stir"], unique=False)
    op.add_column("worker_profiles", sa.Column("last_name", sa.String(length=60), nullable=True))
    op.add_column("worker_profiles", sa.Column("first_name", sa.String(length=60), nullable=True))
    op.add_column("worker_profiles", sa.Column("middle_name", sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column("worker_profiles", "middle_name")
    op.drop_column("worker_profiles", "first_name")
    op.drop_column("worker_profiles", "last_name")
    op.drop_index(op.f("ix_employer_profiles_stir"), table_name="employer_profiles")
    op.drop_index(op.f("ix_employer_profiles_business_status"), table_name="employer_profiles")
    op.drop_table("employer_profiles")
