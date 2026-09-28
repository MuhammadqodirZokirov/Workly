"""worker profiles verification audit

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-28 12:50:43.547332
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("object_type", sa.String(length=32), nullable=False),
        sa.Column("object_id", sa.BigInteger(), nullable=True),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(op.f("ix_audit_logs_actor_id"), "audit_logs", ["actor_id"], unique=False)
    op.create_table(
        "state_transitions",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("object_type", sa.String(length=32), nullable=False),
        sa.Column("object_id", sa.BigInteger(), nullable=False),
        sa.Column("from_state", sa.String(length=32), nullable=True),
        sa.Column("to_state", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_state_transitions")),
    )
    op.create_index("ix_state_transitions_object", "state_transitions", ["object_type", "object_id"], unique=False)
    op.create_table(
        "worker_documents",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("storage_key", sa.String(length=200), nullable=False),
        sa.Column("content_type", sa.String(length=40), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_worker_documents_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_worker_documents")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_worker_documents_storage_key")),
    )
    op.create_index(op.f("ix_worker_documents_user_id"), "worker_documents", ["user_id"], unique=False)
    op.create_table(
        "worker_profiles",
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(length=8), nullable=True),
        sa.Column("home_lat", sa.Float(), nullable=True),
        sa.Column("home_lon", sa.Float(), nullable=True),
        sa.Column("emergency_name", sa.String(length=120), nullable=True),
        sa.Column("emergency_phone", sa.String(length=16), nullable=True),
        sa.Column("verification_status", sa.String(length=16), nullable=False),
        sa.Column("doc_type", sa.String(length=16), nullable=True),
        sa.Column("doc_number_enc", sa.Text(), nullable=True),
        sa.Column("doc_number_hash", sa.String(length=64), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("rejection_reason", sa.String(length=32), nullable=True),
        sa.Column("rejection_comment", sa.String(length=500), nullable=True),
        sa.Column("duplicate_of_user_id", sa.BigInteger(), nullable=True),
        sa.Column("badges", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_worker_profiles_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], name=op.f("fk_worker_profiles_verified_by_users")),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_worker_profiles")),
    )
    op.create_index(op.f("ix_worker_profiles_doc_number_hash"), "worker_profiles", ["doc_number_hash"], unique=False)
    op.create_index(
        op.f("ix_worker_profiles_verification_status"), "worker_profiles", ["verification_status"], unique=False
    )
    op.create_table(
        "worker_availability",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start", sa.Time(), nullable=False),
        sa.Column("end", sa.Time(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["worker_profiles.user_id"],
            name=op.f("fk_worker_availability_user_id_worker_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_worker_availability")),
    )
    op.create_index(op.f("ix_worker_availability_user_id"), "worker_availability", ["user_id"], unique=False)
    op.create_table(
        "worker_districts",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("district_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["district_id"], ["districts.id"], name=op.f("fk_worker_districts_district_id_districts")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["worker_profiles.user_id"],
            name=op.f("fk_worker_districts_user_id_worker_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_worker_districts")),
        sa.UniqueConstraint("user_id", "district_id", name=op.f("uq_worker_districts_user_id")),
    )
    op.create_index(op.f("ix_worker_districts_district_id"), "worker_districts", ["district_id"], unique=False)
    op.create_index(op.f("ix_worker_districts_user_id"), "worker_districts", ["user_id"], unique=False)
    op.create_table(
        "worker_skills",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("experience", sa.String(length=8), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], name=op.f("fk_worker_skills_category_id_categories")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["worker_profiles.user_id"],
            name=op.f("fk_worker_skills_user_id_worker_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_worker_skills")),
        sa.UniqueConstraint("user_id", "category_id", name=op.f("uq_worker_skills_user_id")),
    )
    op.create_index(op.f("ix_worker_skills_user_id"), "worker_skills", ["user_id"], unique=False)
    op.create_table(
        "worker_specializations",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("specialization_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], name=op.f("fk_worker_specializations_category_id_categories")
        ),
        sa.ForeignKeyConstraint(
            ["specialization_id"],
            ["specializations.id"],
            name=op.f("fk_worker_specializations_specialization_id_specializations"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["worker_profiles.user_id"],
            name=op.f("fk_worker_specializations_user_id_worker_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_worker_specializations")),
        sa.UniqueConstraint("user_id", "specialization_id", name=op.f("uq_worker_specializations_user_id")),
    )
    op.create_index(
        op.f("ix_worker_specializations_specialization_id"),
        "worker_specializations",
        ["specialization_id"],
        unique=False,
    )
    op.create_index(op.f("ix_worker_specializations_user_id"), "worker_specializations", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_worker_specializations_user_id"), table_name="worker_specializations")
    op.drop_index(op.f("ix_worker_specializations_specialization_id"), table_name="worker_specializations")
    op.drop_table("worker_specializations")
    op.drop_index(op.f("ix_worker_skills_user_id"), table_name="worker_skills")
    op.drop_table("worker_skills")
    op.drop_index(op.f("ix_worker_districts_user_id"), table_name="worker_districts")
    op.drop_index(op.f("ix_worker_districts_district_id"), table_name="worker_districts")
    op.drop_table("worker_districts")
    op.drop_index(op.f("ix_worker_availability_user_id"), table_name="worker_availability")
    op.drop_table("worker_availability")
    op.drop_index(op.f("ix_worker_profiles_verification_status"), table_name="worker_profiles")
    op.drop_index(op.f("ix_worker_profiles_doc_number_hash"), table_name="worker_profiles")
    op.drop_table("worker_profiles")
    op.drop_index(op.f("ix_worker_documents_user_id"), table_name="worker_documents")
    op.drop_table("worker_documents")
    op.drop_index("ix_state_transitions_object", table_name="state_transitions")
    op.drop_table("state_transitions")
    op.drop_index(op.f("ix_audit_logs_actor_id"), table_name="audit_logs")
    op.drop_table("audit_logs")
