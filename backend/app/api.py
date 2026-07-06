from fastapi import APIRouter
from .routes import campaign
from .routes import settings

router = APIRouter()
router.include_router(campaign.router, prefix="/campaigns", tags=["Campaigns"])
router.include_router(settings.router, prefix="/settings",  tags=["Settings"])
