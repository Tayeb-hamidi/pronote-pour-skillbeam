"""question bank versioning and pronote import analytics

Revision ID: 0002_qbank_pronote_import
Revises: 0001_init
Create Date: 2026-02-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_qbank_pronote_import"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "question_bank_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "content_set_id", sa.String(length=36), sa.ForeignKey("content_sets.id"), nullable=True
        ),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("label", sa.String(length=255), nullable=False, server_default="Version"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column(
            "snapshot_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_question_bank_versions_project_id", "question_bank_versions", ["project_id"]
    )

    op.create_table(
        "pronote_import_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("imported_items_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "stats_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_pronote_import_runs_project_id", "pronote_import_runs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_pronote_import_runs_project_id", table_name="pronote_import_runs")
    op.drop_table("pronote_import_runs")

    op.drop_index("ix_question_bank_versions_project_id", table_name="question_bank_versions")
    op.drop_table("question_bank_versions")
