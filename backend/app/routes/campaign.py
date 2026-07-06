from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Form
from pydantic import BaseModel
from typing import List, Optional
import uuid
import asyncio
import random
import os
import shutil
from pathlib import Path

from ..ai import generate_campaign_copy, spam_score_message
from ..queue import campaign_queue
from ..services import parse_contacts_csv, clean_contacts
from ..tasks import send_campaign_message
from ..greenapi import get_greenapi_client
from ..config import get_settings

router = APIRouter()

# ─── MVP fixed fallback number ────────────────────────────────────────────────
MVP_PHONE = "923422454713"

# ─── Media upload directory ───────────────────────────────────────────────────
MEDIA_DIR = Path(__file__).parent.parent.parent / "data" / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


# ─────────────────────────── Request / Response schemas ───────────────────────

class CampaignCreateRequest(BaseModel):
    name: str
    campaign_type: str
    schedule_at: Optional[str] = None
    segment: Optional[str] = None
    message_type: str          # "text" | "image" | "ai"
    message_text: Optional[str] = None
    image_url: Optional[str] = None
    ai_prompt: Optional[str] = None
    contacts: Optional[List[str]] = None
    # AI copy fields
    business_type: Optional[str] = None
    campaign_goal: Optional[str] = None
    audience: Optional[str] = None
    offer: Optional[str] = None
    tone: Optional[str] = "Friendly"


class CampaignResponse(BaseModel):
    id: str
    message: str
    status: str


class CampaignDraft(BaseModel):
    draft_id: str
    payload: dict


class CopyRequest(BaseModel):
    business_type: str
    campaign_goal: str
    audience: str
    offer: str
    tone: Optional[str] = "Friendly"


class CopyResponse(BaseModel):
    headline: str
    caption: str
    cta: str
    emojis: str
    image_prompt: str
    spam_score: int
    quality: str
    reasons: List[str]


class SpamCheckRequest(BaseModel):
    message: str


class SpamCheckResponse(BaseModel):
    spam_risk: int
    quality: str
    reasons: List[str]


class DirectMessageRequest(BaseModel):
    phone: str
    message_type: str = "text"   # "text" | "image"
    message_text: Optional[str] = None
    image_url: Optional[str] = None


# ─────────────────────────── In-memory draft store ────────────────────────────
draft_store: dict[str, dict] = {}


# ─────────────────────────── Contacts ─────────────────────────────────────────

@router.post("/upload-contacts", summary="Upload a CSV file of contacts")
async def upload_contacts(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV uploads are supported.")
    content = await file.read()
    rows = parse_contacts_csv(content)
    result = clean_contacts(rows)
    return {
        "filename": file.filename,
        "status": "parsed",
        "summary": {
            "total": result["total"],
            "valid": result["valid"],
            "duplicates": result["duplicates"],
            "invalid": result["invalid"],
        },
        "contacts": [c.model_dump() for c in result["contacts"]],
    }


# ─────────────────────────── AI copy generation ───────────────────────────────

@router.post("/generate-copy", response_model=CopyResponse, summary="Generate AI campaign copy via Groq")
async def generate_copy(payload: CopyRequest):
    try:
        generated = await generate_campaign_copy(
            business_type=payload.business_type,
            campaign_goal=payload.campaign_goal,
            audience=payload.audience,
            offer=payload.offer,
            tone=payload.tone,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Groq error: {exc}")
    spam_result = spam_score_message(generated["caption"])
    return {
        "headline": generated["headline"],
        "caption": generated["caption"],
        "cta": generated["cta"],
        "emojis": generated["emojis"],
        "image_prompt": generated["image_prompt"],
        "spam_score": spam_result["spam_risk"],
        "quality": spam_result["quality"],
        "reasons": spam_result["reasons"],
    }


@router.post("/spam-check", response_model=SpamCheckResponse, summary="Check a message for spam risk")
async def spam_check(payload: SpamCheckRequest):
    result = spam_score_message(payload.message)
    return result


# ─────────────────────────── Campaign CRUD ────────────────────────────────────

@router.post("/create", response_model=CampaignDraft, summary="Save a campaign as a draft")
async def create_campaign(payload: CampaignCreateRequest):
    """
    If message_type is 'ai', Groq will generate the copy automatically
    using business_type / campaign_goal / audience / offer / tone fields.
    The draft can then be confirmed via POST /confirm?draft_id=...
    """
    data = payload.model_dump()

    # Auto-generate copy when message_type == "ai"
    if payload.message_type == "ai":
        if not all([payload.business_type, payload.campaign_goal, payload.audience, payload.offer]):
            raise HTTPException(
                status_code=400,
                detail="business_type, campaign_goal, audience and offer are required for AI campaigns.",
            )
        generated = await generate_campaign_copy(
            business_type=payload.business_type,
            campaign_goal=payload.campaign_goal,
            audience=payload.audience,
            offer=payload.offer,
            tone=payload.tone or "Friendly",
        )
        data["generated_copy"] = generated
        data["message_text"] = f"{generated['headline']}\n\n{generated['caption']}\n\n{generated['cta']}"

    draft_id = str(uuid.uuid4())
    draft_store[draft_id] = data
    return {"draft_id": draft_id, "payload": data}


@router.get("/drafts", summary="List all campaign drafts")
def list_drafts():
    return [{"draft_id": k, "name": v.get("name"), "status": "draft"} for k, v in draft_store.items()]


@router.get("/drafts/{draft_id}", response_model=CampaignDraft, summary="Get a single draft")
def get_campaign_draft(draft_id: str):
    draft = draft_store.get(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return {"draft_id": draft_id, "payload": draft}


@router.delete("/drafts/{draft_id}", summary="Delete a draft")
def delete_draft(draft_id: str):
    if draft_id not in draft_store:
        raise HTTPException(status_code=404, detail="Draft not found.")
    draft_store.pop(draft_id)
    return {"message": "Draft deleted."}


@router.post("/confirm", response_model=CampaignResponse, summary="Confirm a draft and queue messages")
def confirm_campaign(draft_id: str = Query(..., description="Draft ID returned by /create")):
    draft = draft_store.get(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")

    contacts = draft.get("contacts") or []
    if not contacts:
        raise HTTPException(status_code=400, detail="No contacts in draft. Add contacts before confirming.")

    campaign_id = str(uuid.uuid4())

    for phone in contacts:
        campaign_queue.enqueue(
            send_campaign_message,
            phone,
            draft["message_type"],
            draft.get("message_text") or "",
            draft.get("image_url"),
            job_timeout=300,
        )

    draft_store.pop(draft_id, None)
    return {
        "id": campaign_id,
        "message": f"Campaign confirmed. {len(contacts)} message(s) queued.",
        "status": "queued",
    }


# ─────────────────────────── Direct / test messaging ─────────────────────────

@router.post("/send-message", response_model=dict, summary="Send a single WhatsApp message directly")
async def send_direct_message(payload: DirectMessageRequest):
    """
    Sends immediately (no queue). Applies a random 1–10s delay before sending
    to avoid spam detection.
    """
    delay = random.uniform(1, 10)
    await asyncio.sleep(delay)

    client = get_greenapi_client()
    try:
        if payload.message_type == "image":
            if not payload.image_url:
                raise HTTPException(status_code=400, detail="image_url is required for image messages.")
            result = await client.send_image(payload.phone, payload.image_url, caption=payload.message_text)
        else:
            if not payload.message_text:
                raise HTTPException(status_code=400, detail="message_text is required for text messages.")
            result = await client.send_text(payload.phone, payload.message_text)
        return {"status": "sent", "delay_seconds": round(delay, 2), "greenapi_response": result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GreenAPI send failed: {exc}")


# ─────────────────────────── GreenAPI management ──────────────────────────────

@router.get("/greenapi/state", summary="Check GreenAPI instance authorization state")
async def greenapi_state():
    client = get_greenapi_client()
    try:
        return await client.get_state()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GreenAPI error: {exc}")


@router.get("/greenapi/settings", summary="Get GreenAPI instance settings")
async def greenapi_settings():
    client = get_greenapi_client()
    try:
        return await client.get_settings()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GreenAPI error: {exc}")


@router.get("/greenapi/qr", summary="Get QR code for GreenAPI (use when not yet authorized)")
async def greenapi_qr():
    client = get_greenapi_client()
    try:
        return await client.get_qr()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GreenAPI error: {exc}")


# ─────────────────────────── Media upload ─────────────────────────────────────

@router.post("/media/upload", summary="Upload an image to use in campaigns")
async def upload_media(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Only images are allowed (jpeg/png/gif/webp). Got: {file.content_type}",
        )
    # Max 10MB
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be under 10MB.")

    ext      = Path(file.filename).suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest     = MEDIA_DIR / filename

    with open(dest, "wb") as f:
        f.write(content)

    # Return a URL the frontend can use (served via /media/ static route)
    return {
        "filename":  filename,
        "url":       f"/media/{filename}",
        "size_bytes": len(content),
        "mime_type": file.content_type,
    }


# ══════════════════════════════════════════════════════════════════════════════
# MVP Pipeline  — CSV → Filter → AI (personalised) → Preview → Send
# ══════════════════════════════════════════════════════════════════════════════

class MVPGenerateRequest(BaseModel):
    contacts_json:    List[dict]
    user_query:       Optional[str] = ""   # free-text campaign brief from user
    business_context: Optional[str] = ""   # kept for backward compat
    tone:             Optional[str] = "Friendly"


class MVPCampaignPreview(BaseModel):
    headline:        str
    message:         str
    cta:             str
    emojis:          str
    spam_score:      int
    quality:         str
    target_phone:    str
    contact_summary: dict


class MVPSendRequest(BaseModel):
    message:     str
    image_url:   Optional[str] = None   # public URL or /media/... local URL
    recipients:  Optional[List[str]] = None


class MVPSendResult(BaseModel):
    status:  str
    results: List[dict]
    total:   int
    sent:    int
    failed:  int


@router.post(
    "/mvp/generate",
    response_model=MVPCampaignPreview,
    summary="MVP: Generate personalised AI campaign from CSV + user query",
    tags=["MVP"],
)
async def mvp_generate(payload: MVPGenerateRequest):
    contacts = payload.contacts_json
    if not contacts:
        raise HTTPException(status_code=400, detail="No contacts provided.")

    names  = [c.get("name", "").strip() for c in contacts if c.get("name", "").strip()]
    cities = list({c.get("city", "").strip() for c in contacts if c.get("city", "").strip()})
    total  = len(contacts)

    contact_summary = {
        "total":        total,
        "names_sample": names[:3],
        "cities":       cities,
    }

    city_str = ", ".join(cities) if cities else "various cities"
    audience = f"{total} customer(s) from {city_str}"
    if names:
        audience += f" including {', '.join(names[:3])}"

    # User query takes priority; fall back to business_context
    query         = (payload.user_query or payload.business_context or "").strip()
    business_type = query or "General Business"
    campaign_goal = query or "Engage customers and drive conversions"

    # If names exist, instruct AI to personalise
    personalisation_note = ""
    if names:
        personalisation_note = (
            f" Personalise the message — address the customer by name. "
            f"Use {{{{name}}}} as a placeholder where the customer's name should appear "
            f"(e.g. 'Hello {{{{name}}}}!'). "
        )

    offer = query if query else f"Special offer for {audience}"

    try:
        generated = await generate_campaign_copy(
            business_type=business_type,
            campaign_goal=campaign_goal,
            audience=audience + personalisation_note,
            offer=offer,
            tone=payload.tone or "Friendly",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI generation failed: {exc}")

    spam     = spam_score_message(generated["caption"])
    settings = get_settings()

    return MVPCampaignPreview(
        headline=generated["headline"],
        message=generated["caption"],
        cta=generated["cta"],
        emojis=generated["emojis"],
        spam_score=spam["spam_risk"],
        quality=spam["quality"],
        target_phone=settings.test_phone,
        contact_summary=contact_summary,
    )


def _resolve_chat_id(recipient: str) -> str:
    if "@g.us" in recipient:
        return recipient
    phone_clean = recipient.lstrip("+").replace(" ", "").replace("-", "")
    return f"{phone_clean}@c.us"


def _personalise(message: str, name: str | None) -> str:
    """Replace {{name}} placeholder with actual contact name."""
    if not name:
        return message.replace("{{name}}", "").replace("{{ name }}", "").strip()
    return message.replace("{{name}}", name).replace("{{ name }}", name)


@router.post(
    "/mvp/send",
    response_model=MVPSendResult,
    summary="MVP: Send personalised campaign (text or image) to recipients",
    tags=["MVP"],
)
async def mvp_send(payload: MVPSendRequest):
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    settings   = get_settings()
    raw        = payload.recipients or []
    seen: set  = set()
    recipients = []
    for r in raw:
        r = r.strip()
        if r and r not in seen:
            seen.add(r)
            # Support dicts like {"phone":"...","name":"Ali"} or plain strings
            recipients.append(r)
    if not recipients:
        recipients = [settings.test_phone]

    # Resolve absolute image URL if a local /media/ path was passed
    image_url = None
    if payload.image_url:
        if payload.image_url.startswith("/media/"):
            image_url = f"http://localhost:8000{payload.image_url}"
        else:
            image_url = payload.image_url

    client  = get_greenapi_client()
    results = []

    for entry in recipients:
        # entry may be plain phone string or "name::phone" encoded string
        if "::" in str(entry):
            contact_name, phone_or_id = str(entry).split("::", 1)
        else:
            contact_name, phone_or_id = None, str(entry)

        chat_id      = _resolve_chat_id(phone_or_id)
        personalised = _personalise(payload.message, contact_name)

        delay = random.uniform(1, 10)
        await asyncio.sleep(delay)

        try:
            if image_url:
                resp = await client.send_image_to_chat(chat_id, image_url, caption=personalised)
            else:
                resp = await client._send_to_chat(chat_id, personalised)

            results.append({
                "recipient":     phone_or_id,
                "name":          contact_name or "",
                "chat_id":       chat_id,
                "message_id":    resp.get("idMessage", ""),
                "delay_seconds": round(delay, 2),
                "status":        "sent",
            })
        except Exception as exc:
            results.append({
                "recipient":     phone_or_id,
                "name":          contact_name or "",
                "chat_id":       chat_id,
                "message_id":    "",
                "delay_seconds": round(delay, 2),
                "status":        "failed",
                "error":         str(exc),
            })

    sent   = sum(1 for r in results if r["status"] == "sent")
    failed = len(results) - sent

    return MVPSendResult(
        status="done",
        results=results,
        total=len(results),
        sent=sent,
        failed=failed,
    )
