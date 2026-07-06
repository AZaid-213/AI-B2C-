from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..db import get_settings_for_user, save_settings_for_user
from ..greenapi import GreenAPIClient

router = APIRouter()


class GreenAPISettings(BaseModel):
    instance_id: str
    api_token: str
    base_url: Optional[str] = "https://api.green-api.com"


class SettingsOut(BaseModel):
    instance_id: str
    api_token_masked: str   # show last 6 chars only
    base_url: str
    is_configured: bool


@router.get("", response_model=SettingsOut, summary="Get current GreenAPI settings")
def get_settings():
    s = get_settings_for_user("default")
    instance_id = s.get("greenapi_instance_id", "")
    token       = s.get("greenapi_api_token",   "")
    base_url    = s.get("greenapi_base_url", "https://api.green-api.com")
    masked      = ("*" * max(0, len(token) - 6)) + token[-6:] if token else ""
    return SettingsOut(
        instance_id=instance_id,
        api_token_masked=masked,
        base_url=base_url,
        is_configured=bool(instance_id and token),
    )


@router.post("", summary="Save GreenAPI credentials")
def save_settings(payload: GreenAPISettings):
    existing = get_settings_for_user("default")
    existing.update({
        "greenapi_instance_id": payload.instance_id.strip(),
        "greenapi_api_token":   payload.api_token.strip(),
        "greenapi_base_url":    (payload.base_url or "https://api.green-api.com").rstrip("/"),
    })
    save_settings_for_user(existing, "default")

    # Reset the cached GreenAPI client singleton so it picks up new creds
    import app.greenapi as ga
    ga._client = None

    return {"status": "saved", "instance_id": payload.instance_id}


@router.post("/test", summary="Test GreenAPI connection with saved credentials")
async def test_connection():
    s = get_settings_for_user("default")
    if not s.get("greenapi_instance_id") or not s.get("greenapi_api_token"):
        raise HTTPException(status_code=400, detail="No credentials saved yet.")

    # Create a temporary client with DB credentials
    client = GreenAPIClient(
        instance_id=s["greenapi_instance_id"],
        api_token=s["greenapi_api_token"],
        base_url=s.get("greenapi_base_url", "https://api.green-api.com"),
    )
    try:
        state = await client.get_state()
        return {
            "status": "ok",
            "state": state.get("stateInstance", "unknown"),
            "authorized": state.get("stateInstance") == "authorized",
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GreenAPI connection failed: {exc}")
