import os
from redis import Redis
from rq import Queue

from .config import get_settings

settings = get_settings()
redis_client = Redis.from_url(settings.redis_url)
campaign_queue = Queue("campaigns", connection=redis_client)
