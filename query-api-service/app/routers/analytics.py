from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..data import DataAccessError, DataRepository
from ..dependencies import get_data_repository, require_auth
from ..models import AnalyticsQuery

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_auth)])


@router.get("/provider-summary", summary="Aggregate metrics by provider")
def provider_summary(
    query: AnalyticsQuery = Depends(),
    repository: DataRepository = Depends(get_data_repository),
) -> list[dict]:
    try:
        return repository.fetch_provider_summary("prices", query)
    except DataAccessError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
