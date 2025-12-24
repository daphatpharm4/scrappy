from __future__ import annotations

from fastapi import APIRouter, Depends

from ..data import DataRepository
from ..dependencies import get_data_repository, require_auth

router = APIRouter(prefix="/data/providers", tags=["providers"], dependencies=[Depends(require_auth)])


@router.get("", summary="List available providers")
def list_providers(repository: DataRepository = Depends(get_data_repository)) -> list[str]:
    return repository.list_providers()
