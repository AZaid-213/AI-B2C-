from pydantic import BaseModel, Field
from typing import Optional, List

class Campaign(BaseModel):
    id: str
    name: str
    campaign_type: str
    message_type: str
    message_text: Optional[str]
    image_url: Optional[str]
    ai_prompt: Optional[str]
    status: str = Field(default="draft")

class Contact(BaseModel):
    id: str
    name: Optional[str]
    phone: str
    city: Optional[str]
    tags: List[str] = Field(default_factory=list)
    status: str = Field(default="pending")

class CampaignLog(BaseModel):
    campaign_id: str
    contact_id: str
    greenapi_message_id: Optional[str] = None
    status: str = Field(default="queued")
    sent_at: Optional[str] = None
    read_at: Optional[str] = None
    error: Optional[str] = None
