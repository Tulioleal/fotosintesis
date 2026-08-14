"""canonical species identity on plant profiles

Revision ID: 0014_profile_canonical_identity
Revises: 0013_enrichment_job_progress
Create Date: 2026-08-13

Adds nullable canonical identity columns to ``plant_profiles`` and a partial
unique index on non-null ``canonical_species_key``. The migration backfills
only profiles for which every confirmed, validated garden candidate resolves to
a canonical identity and all such identities are the same. No candidate
identity leaves the columns null, multiple canonical identities are never
guessed, and duplicate profiles sharing one canonical key are reported as a
preflight conflict instead of being silently merged.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0014_profile_canonical_identity"
down_revision: Union[str, None] = "0013_enrichment_job_progress"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalize_binomial(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    words = value.split()
    if len(words) != 2:
        return None
    valid_words = all(
        part.isalpha()
        or "-" in part
        and all(piece.isalpha() for piece in part.split("-"))
        for part in words
    )
    if not valid_words:
        return None
    genus, species = words
    return f"{genus[0].upper()}{genus[1:].lower()} {species.lower()}"


def _canonical_key(gbif_key: object, binomial: object) -> str | None:
    normalized = _normalize_binomial(binomial)
    if normalized is None:
        return None
    if gbif_key is None:
        return f"binomial:{normalized}"
    if (
        not isinstance(gbif_key, bool)
        and type(gbif_key) is int
        and int(gbif_key) > 0
    ):
        return f"gbif:{int(gbif_key)}|binomial:{normalized}"
    # A zero, negative, or non-integer GBIF key is invalid under the runtime
    # rule (CanonicalSpeciesIdentity rejects non-positive keys), so no
    # canonical identity is derived and the controlled data stays unchanged.
    return None


def _backfill_canonical_identity() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT pp.id AS profile_id,
                   ic.gbif_accepted_key,
                   ic.binomial_name
            FROM plant_profiles pp
            JOIN garden_plants gp ON gp.profile_id = pp.id
            JOIN identification_candidates ic ON ic.id = gp.confirmed_candidate_id
            WHERE ic.validation_status = 'validated'
              AND ic.confirmed_at IS NOT NULL
            """
        )
    ).fetchall()

    keys_by_profile: dict[str, set[str | None]] = {}
    for row in rows:
        profile_id = str(row.profile_id)
        key = _canonical_key(row.gbif_accepted_key, row.binomial_name)
        keys_by_profile.setdefault(profile_id, set()).add(key)

    updates: list[tuple[str, str]] = []
    for profile_id, keys in keys_by_profile.items():
        if len(keys) != 1 or None in keys:
            continue

        key = next(iter(keys))
        assert key is not None
        updates.append((profile_id, key))

    # Preflight conflict: duplicate profiles sharing one canonical key must be
    # reported, never silently merged.
    by_key: dict[str, list[str]] = {}
    for profile_id, key in updates:
        by_key.setdefault(key, []).append(profile_id)
    conflicts = {key: ids for key, ids in by_key.items() if len(ids) > 1}
    if conflicts:
        detail = "; ".join(
            f"{key}: {', '.join(ids)}" for key, ids in sorted(conflicts.items())
        )
        raise RuntimeError(
            "plant profile canonical identity backfill conflict: multiple "
            "profiles resolve to one canonical species key; resolve before "
            "retrying. " + detail
        )

    for profile_id, key in updates:
        if key.startswith("gbif:"):
            gbif_part = key.removeprefix("gbif:")
            gbif_key = int(gbif_part.split("|")[0])
        else:
            gbif_key = None
        binomial = key.split("binomial:")[-1]
        connection.execute(
            sa.text(
                """
                UPDATE plant_profiles
                SET accepted_gbif_key = :gbif_key,
                    normalized_binomial = :binomial,
                    canonical_species_key = :key
                WHERE id = CAST(:profile_id AS uuid)
                """
            ),
            {
                "profile_id": profile_id,
                "gbif_key": gbif_key,
                "binomial": binomial,
                "key": key,
            },
        )


def upgrade() -> None:
    op.add_column(
        "plant_profiles",
        sa.Column("accepted_gbif_key", sa.Integer(), nullable=True),
    )
    op.add_column(
        "plant_profiles",
        sa.Column("normalized_binomial", sa.String(length=240), nullable=True),
    )
    op.add_column(
        "plant_profiles",
        sa.Column("canonical_species_key", sa.String(length=512), nullable=True),
    )
    _backfill_canonical_identity()
    op.create_index(
        "uq_plant_profiles_canonical_species_key",
        "plant_profiles",
        ["canonical_species_key"],
        unique=True,
        postgresql_where=sa.text("canonical_species_key IS NOT NULL"),
        sqlite_where=sa.text("canonical_species_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_plant_profiles_canonical_species_key",
        table_name="plant_profiles",
    )
    op.drop_column("plant_profiles", "canonical_species_key")
    op.drop_column("plant_profiles", "normalized_binomial")
    op.drop_column("plant_profiles", "accepted_gbif_key")
