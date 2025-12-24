from __future__ import annotations

from fastapi import APIRouter, Depends

from ..data import DataRepository
from ..dependencies import get_data_repository, require_auth
from ..models import RealEstateQuery

router = APIRouter(prefix="/data/realestate", tags=["realestate"], dependencies=[Depends(require_auth)])


@router.get("", summary="Get real estate listings")
def get_real_estate(
    query: RealEstateQuery = Depends(),
    repository: DataRepository = Depends(get_data_repository),
) -> list[dict]:
    return repository.fetch_realestate(query)
