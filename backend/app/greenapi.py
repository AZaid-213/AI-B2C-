"""
GreenAPI WhatsApp messaging service.
Docs: https://green-api.com/en/docs/
"""

import httpx
from typing import Optional

from .config import get_settings


class GreenAPIClient:
    def __init__(self, instance_id: str = None, api_token: str = None, base_url: str = None):
        if instance_id and api_token:
            # Explicit credentials (e.g. from settings page test)
            self.instance_id = instance_id
            self.api_token   = api_token
            self.base_url    = (base_url or "https://api.green-api.com").rstrip("/")
        else:
            # Load from DB first, fall back to .env
            from .db import get_settings_for_user
            db_settings = get_settings_for_user("default")
            settings = get_settings()
            self.instance_id = db_settings.get("greenapi_instance_id") or settings.greenapi_instance_id
            self.api_token   = db_settings.get("greenapi_api_token")   or settings.greenapi_api_token
            self.base_url    = (db_settings.get("greenapi_base_url")   or settings.greenapi_base_url).rstrip("/")

    def _endpoint(self, method: str) -> str:
        return f"{self.base_url}/waInstance{self.instance_id}/{method}/{self.api_token}"

    def _format_phone(self, phone: str) -> str:
        """Return phone in international digits only, e.g. 919876543210."""
        return phone.strip().lstrip("+").replace(" ", "").replace("-", "")

    # ------------------------------------------------------------------ async
    async def send_text(self, phone: str, message: str) -> dict:
        chat_id = f"{self._format_phone(phone)}@c.us"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self._endpoint("sendMessage"),
                json={"chatId": chat_id, "message": message},
            )
            resp.raise_for_status()
            return resp.json()

    async def send_image(self, phone: str, image_url: str, caption: Optional[str] = None) -> dict:
        chat_id = f"{self._format_phone(phone)}@c.us"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self._endpoint("sendFileByUrl"),
                json={"chatId": chat_id, "urlFile": image_url, "fileName": "image.jpg", "caption": caption or ""},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_state(self) -> dict:
        """Returns {"stateInstance": "authorized"} when ready."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(self._endpoint("getStateInstance"))
            resp.raise_for_status()
            return resp.json()

    async def _send_to_chat(self, chat_id: str, message: str) -> dict:
        """Send text to any chatId directly — works for both @c.us and @g.us."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self._endpoint("sendMessage"),
                json={"chatId": chat_id, "message": message},
            )
            resp.raise_for_status()
            return resp.json()

    async def send_image_to_chat(self, chat_id: str, image_url: str, caption: str = "") -> dict:
        """Send image by URL to any chatId (phone @c.us or group @g.us)."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                self._endpoint("sendFileByUrl"),
                json={
                    "chatId":   chat_id,
                    "urlFile":  image_url,
                    "fileName": "image.jpg",
                    "caption":  caption,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def get_settings(self) -> dict:
        """Returns full instance settings from GreenAPI."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(self._endpoint("getSettings"))
            resp.raise_for_status()
            return resp.json()

    async def get_qr(self) -> dict:
        """Returns QR code data for scanning (when not yet authorized)."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(self._endpoint("qr"))
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------ sync (for RQ workers)
    def send_text_sync(self, phone: str, message: str) -> dict:
        chat_id = f"{self._format_phone(phone)}@c.us"
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                self._endpoint("sendMessage"),
                json={"chatId": chat_id, "message": message},
            )
            resp.raise_for_status()
            return resp.json()

    def send_image_sync(self, phone: str, image_url: str, caption: Optional[str] = None) -> dict:
        chat_id = f"{self._format_phone(phone)}@c.us"
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                self._endpoint("sendFileByUrl"),
                json={"chatId": chat_id, "urlFile": image_url, "fileName": "image.jpg", "caption": caption or ""},
            )
            resp.raise_for_status()
            return resp.json()


# Module-level singleton
_client: Optional[GreenAPIClient] = None


def get_greenapi_client() -> GreenAPIClient:
    global _client
    if _client is None:
        _client = GreenAPIClient()
    return _client
