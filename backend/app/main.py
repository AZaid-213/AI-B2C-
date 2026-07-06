from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from .api import router as api_router
from .config import get_settings

settings = get_settings()

MEDIA_DIR = Path(__file__).parent.parent / "data" / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="AI B2C WhatsApp Campaign Manager",
    description="Backend API for AI-powered WhatsApp marketing campaigns.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Serve uploaded media files
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

app.include_router(api_router, prefix="/api")


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "env": settings.app_env,
        "groq_configured": bool(settings.groq_api_key),
        "greenapi_configured": bool(
            settings.greenapi_instance_id and settings.greenapi_api_token
            and settings.greenapi_instance_id != "your_instance_id_here"
        ),
    }
