import time
import random
from .greenapi import get_greenapi_client


def send_campaign_message(phone: str, message_type: str, message_text: str, image_url: str | None = None) -> dict:
    # Random delay 1–10s to avoid flooding / spam detection
    delay = random.uniform(1, 10)
    time.sleep(delay)

    client = get_greenapi_client()
    if message_type == "image" and image_url:
        return client.send_image_sync(phone, image_url, caption=message_text)
    return client.send_text_sync(phone, message_text)
