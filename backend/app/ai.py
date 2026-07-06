import json
import httpx
from typing import Optional

from .config import get_settings

settings = get_settings()


async def _call_groq(prompt: str) -> str:
    """Call Groq via its OpenAI-compatible chat completions endpoint."""
    if not settings.groq_api_key:
        return (
            "[GROQ API key is not configured. "
            "Set GROQ_API_KEY in your .env to enable AI generation.]"
        )

    payload = {
        "model": settings.groq_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 512,
    }
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        url = f"{settings.groq_api_url}/chat/completions"
        response = await client.post(url, json=payload, headers=headers)
        if not response.is_success:
            error_body = response.text
            raise ValueError(f"Groq API error {response.status_code}: {error_body}")
        body = response.json()
        # OpenAI-compatible response shape
        return body["choices"][0]["message"]["content"]


async def generate_campaign_copy(
    business_type: str,
    campaign_goal: str,
    audience: str,
    offer: str,
    tone: Optional[str] = "Friendly",
) -> dict:
    prompt = (
        "You are a WhatsApp marketing copywriter. "
        "Respond ONLY with a valid JSON object — no explanation, no markdown, no code fences. "
        "The JSON must have exactly these keys: headline, caption, cta, emojis, image_prompt. "
        f"Business type: {business_type}. "
        f"Campaign goal: {campaign_goal}. "
        f"Target audience: {audience}. "
        f"Offer: {offer}. "
        f"Tone: {tone}. "
        "Example format: "
        '{"headline":"...", "caption":"...", "cta":"...", "emojis":"...", "image_prompt":"..."}'
    )

    raw = await _call_groq(prompt)

    # Strip markdown code fences if present
    stripped = raw.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        stripped = "\n".join(lines).strip()

    result = {
        "headline": "",
        "caption": stripped,
        "cta": "",
        "emojis": "",
        "image_prompt": "",
    }

    try:
        parsed = json.loads(stripped)
        # Handle case where model nested JSON inside a caption key
        if isinstance(parsed.get("caption"), str):
            try:
                inner = json.loads(parsed["caption"])
                if isinstance(inner, dict) and "headline" in inner:
                    parsed = inner
            except (json.JSONDecodeError, TypeError):
                pass
        for key in result.keys():
            if key in parsed and isinstance(parsed[key], str):
                result[key] = parsed[key]
    except json.JSONDecodeError:
        # Plain text fallback — use as caption
        pass

    return result


def spam_score_message(message: str) -> dict:
    score = 0
    reasons = []

    if "http" in message or "www" in message:
        score += 30
        reasons.append("contains a link")

    emojis = sum(1 for char in message if char in "😀😃😄😁😆😅🤣😂🙂🙃😉😊😍😘😎🥳✨🔥🎉🎊💥💯")
    if emojis > 5:
        score += 20
        reasons.append("uses many emojis")

    if len(message) > 0 and sum(1 for c in message if c.isupper()) > len(message) * 0.25:
        score += 15
        reasons.append("too much uppercase text")

    if score == 0:
        quality = "low"
    elif score < 30:
        quality = "moderate"
    else:
        quality = "high"

    return {
        "spam_risk": min(score, 100),
        "quality": quality,
        "reasons": reasons,
    }
