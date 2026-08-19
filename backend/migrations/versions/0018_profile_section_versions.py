"""profile section versions and evidence fingerprints

Revision ID: 0018_profile_section_versions
Revises: 0017_recovery_token_hashing
Create Date: 2026-08-18

Adds per-section version metadata to plant profiles so individual profile
sections can record the deterministic evidence fingerprint, applicable aspect
set, generation policy version, provenance, confidence, limitations, and
generation timestamp that produced them. Existing sections are left without
fingerprints; the bounded reconciliation pass treats them as unknown rather
than automatically current.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0018_profile_section_versions"
down_revision: Union[str, None] = "0017_recovery_token_hashing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "plant_profiles",
        sa.Column("generation_policy_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "plant_profiles",
        sa.Column(
            "section_versions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.drop_constraint("ck_application_jobs_type", "application_jobs", type_="check")
    op.create_check_constraint(
        "ck_application_jobs_type",
        "application_jobs",
        "job_type IN ('ingest_validated_claims', 'enrich_confirmed_plant', 'refresh_profile')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_application_jobs_type", "application_jobs", type_="check")
    op.create_check_constraint(
        "ck_application_jobs_type",
        "application_jobs",
        "job_type IN ('ingest_validated_claims', 'enrich_confirmed_plant')",
    )
    op.drop_column("plant_profiles", "section_versions")
    op.drop_column("plant_profiles", "generation_policy_version")
