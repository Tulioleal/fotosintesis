from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tables import identification_candidates, identification_images
from app.identification.gbif import GbifTaxonomy
from app.identification.schemas import IdentificationResponse, TaxonomyCandidate
from app.providers.types import PlantCandidate


def _possible_match_copy(candidate: PlantCandidate) -> str:
    confidence = candidate.confidence_label.value
    return (
        f"Posible coincidencia, no definitiva. Confianza {confidence}; "
        "confirmala despues de revisar rasgos visibles y taxonomia GBIF."
    )


class IdentificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_identification(
        self,
        *,
        user_id: UUID,
        storage_path: str,
        mime_type: str,
        size_bytes: int,
        metadata: dict[str, object],
        status: str,
        message: str,
        sad_path: str | None = None,
    ) -> UUID:
        identification_id = uuid4()
        await self.session.execute(
            insert(identification_images).values(
                id=identification_id,
                user_id=user_id,
                storage_path=storage_path,
                mime_type=mime_type,
                size_bytes=size_bytes,
                metadata=metadata,
                status=status,
                sad_path=sad_path,
                message=message,
            )
        )
        await self.session.commit()
        return identification_id

    async def add_candidate(
        self,
        *,
        identification_id: UUID,
        candidate: PlantCandidate,
        taxonomy: GbifTaxonomy,
    ) -> None:
        await self.session.execute(
            insert(identification_candidates).values(
                id=uuid4(),
                identification_id=identification_id,
                common_name=candidate.common_name,
                suggested_scientific_name=candidate.scientific_name,
                confidence_label=candidate.confidence_label.value,
                visible_traits=candidate.visible_traits,
                possible_match_copy=_possible_match_copy(candidate),
                gbif_key=taxonomy.key,
                gbif_accepted_key=taxonomy.accepted_key,
                accepted_scientific_name=taxonomy.accepted_scientific_name,
                taxonomic_status=taxonomy.taxonomic_status,
                synonyms=taxonomy.synonyms,
                genus=taxonomy.genus,
                family=taxonomy.family,
                species=taxonomy.species,
                validation_status="validated" if taxonomy.matched else "no_gbif_match",
            )
        )
        await self.session.commit()

    async def get_response(self, identification_id: UUID, user_id: UUID) -> IdentificationResponse | None:
        image = (
            await self.session.execute(
                select(identification_images).where(
                    identification_images.c.id == identification_id,
                    identification_images.c.user_id == user_id,
                )
            )
        ).first()
        if image is None:
            return None

        rows = (
            await self.session.execute(
                select(identification_candidates)
                .where(identification_candidates.c.identification_id == identification_id)
                .order_by(identification_candidates.c.created_at)
            )
        ).all()
        candidates = [TaxonomyCandidate.model_validate(row._mapping) for row in rows]
        return IdentificationResponse(
            id=image.id,
            status=image.status,
            sad_path=image.sad_path,
            message=image.message,
            image={
                "path": image.storage_path,
                "mime_type": image.mime_type,
                "size_bytes": image.size_bytes,
                "metadata": image.metadata,
            },
            candidates=candidates,
        )

    async def mark_recoverable(
        self, *, identification_id: UUID, status: str, sad_path: str, message: str
    ) -> None:
        await self.session.execute(
            update(identification_images)
            .where(identification_images.c.id == identification_id)
            .values(status=status, sad_path=sad_path, message=message)
        )
        await self.session.commit()

    async def confirm_candidate(
        self, *, identification_id: UUID, candidate_id: UUID, user_id: UUID
    ) -> TaxonomyCandidate | None:
        image = (
            await self.session.execute(
                select(identification_images.c.id).where(
                    identification_images.c.id == identification_id,
                    identification_images.c.user_id == user_id,
                    identification_images.c.status == "needs_confirmation",
                )
            )
        ).first()
        if image is None:
            return None

        candidate = (
            await self.session.execute(
                select(identification_candidates).where(
                    identification_candidates.c.id == candidate_id,
                    identification_candidates.c.identification_id == identification_id,
                    identification_candidates.c.validation_status == "validated",
                )
            )
        ).first()
        if candidate is None:
            return None

        confirmed_at = datetime.now(timezone.utc)
        await self.session.execute(
            update(identification_candidates)
            .where(identification_candidates.c.identification_id == identification_id)
            .values(confirmed_at=None)
        )
        await self.session.execute(
            update(identification_candidates)
            .where(identification_candidates.c.id == candidate_id)
            .values(confirmed_at=confirmed_at)
        )
        await self.session.commit()

        row = (
            await self.session.execute(
                select(identification_candidates).where(identification_candidates.c.id == candidate_id)
            )
        ).first()
        return TaxonomyCandidate.model_validate(row._mapping) if row else None
