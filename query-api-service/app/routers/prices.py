from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_data_repository, require_auth
from ..models import PriceQuery
from ..data import DataRepository

router = APIRouter(prefix="/data/prices", tags=["prices"], dependencies=[Depends(require_auth)])


@router.get("", summary="Get price records")
def get_prices(
    query: PriceQuery = Depends(),
    repository: DataRepository = Depends(get_data_repository),
) -> list[dict]:
    return repository.fetch_prices(query)
