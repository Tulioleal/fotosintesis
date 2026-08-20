from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import AuthUser
from app.db.session import get_async_session
from app.identification.confirmation import (
    CandidateConfirmationService,
    ConfirmationRejectedError,
    ConfirmationSchedulingUnavailable,
)
from app.identification.gbif import GbifClient, GbifTaxonomy, ProviderLookupError
from app.identification.repository import IdentificationRepository
from app.identification.schemas import (
    ConfirmationResponse,
    GbifCandidate,
    GbifSearchResponse,
    ManualCandidateCreate,
    TaxonomyCandidate,
)
from app.profile_garden.repository import PlantProfileGardenRepository
from app.profile_garden.schemas import LocalPlantSearchResult

router = APIRouter(prefix="/search", tags=["search"])


class SearchLocalResponse(BaseModel):
    results: list[LocalPlantSearchResult] = Field(default_factory=list)


@router.get("", response_model=SearchLocalResponse)
async def search_local(
    q: Annotated[str, Query(min_length=1, max_length=240)],
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> SearchLocalResponse:
    repository = PlantProfileGardenRepository(session)
    results = await repository.search_local_profiles(q)
    return SearchLocalResponse(results=results)


@router.get("/gbif", response_model=GbifSearchResponse)
async def search_gbif(
    q: Annotated[str, Query(min_length=1, max_length=240)],
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> GbifSearchResponse:
    try:
        candidates = await GbifClient().suggest(q)
    except ProviderLookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GBIF lookup failed; retry the external expansion.",
        ) from exc

    collapsed = _collapse_candidates(candidates)
    return GbifSearchResponse(candidates=[_to_candidate(c) for c in collapsed])


@router.post(
    "/candidates",
    response_model=TaxonomyCandidate,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_candidate(
    body: ManualCandidateCreate,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> TaxonomyCandidate:
    taxonomy = _candidate_to_taxonomy(body.gbif)
    repository = IdentificationRepository(session)
    try:
        return await repository.create_manual_candidate(
            user_id=user.id,
            query=body.query,
            taxonomy=taxonomy,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="The selected GBIF identity is not a valid canonical species.",
        ) from exc


@router.post(
    "/candidates/{candidate_id}/confirm",
    response_model=ConfirmationResponse,
)
async def confirm_manual_candidate(
    candidate_id: UUID,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ConfirmationResponse:
    try:
        return await CandidateConfirmationService(session).confirm_manual(
            candidate_id=candidate_id,
            user_id=user.id,
        )
    except ConfirmationRejectedError:
        raise HTTPException(
            status_code=409,
            detail="You can only confirm a taxonomically validated candidate you own.",
        ) from None
    except ConfirmationSchedulingUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Plant enrichment scheduling is temporarily unavailable.",
        ) from None


def _to_candidate(taxonomy: GbifTaxonomy) -> GbifCandidate:
    return GbifCandidate(
        key=taxonomy.key,
        accepted_key=taxonomy.accepted_key,
        accepted_scientific_name=taxonomy.accepted_scientific_name,
        binomial_name=taxonomy.binomial_name,
        rank=taxonomy.rank,
        taxonomic_status=taxonomy.taxonomic_status,
        synonyms=taxonomy.synonyms,
        genus=taxonomy.genus,
        family=taxonomy.family,
        species=taxonomy.species,
    )


def _candidate_to_taxonomy(candidate: GbifCandidate) -> GbifTaxonomy:
    return GbifTaxonomy(
        key=candidate.key,
        accepted_key=candidate.accepted_key,
        accepted_scientific_name=candidate.accepted_scientific_name,
        binomial_name=candidate.binomial_name,
        rank=candidate.rank,
        taxonomic_status=candidate.taxonomic_status,
        synonyms=candidate.synonyms,
        genus=candidate.genus,
        family=candidate.family,
        species=candidate.species,
        matched=True,
    )


def _collapse_candidates(candidates: list[GbifTaxonomy]) -> list[GbifTaxonomy]:
    """Collapse duplicates by accepted GBIF key, falling back to binomial."""
    seen_keys: set[int | str] = set()
    collapsed: list[GbifTaxonomy] = []
    for taxonomy in candidates:
        key: int | str | None = taxonomy.accepted_key
        if key is None:
            key = taxonomy.binomial_name or taxonomy.key
        if key is None:
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        collapsed.append(taxonomy)
    return collapsed


__all__ = ["router"]
