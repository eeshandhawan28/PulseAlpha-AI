from fastapi import APIRouter
from api.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    s = get_settings()
    return {"status": "ok", "version": s.version, "environment": s.app_env}
