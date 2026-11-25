from django.core.cache import cache
from ninja.errors import HttpError


def enforce_quota(user):
    key=f'lms-ai-minute-{user.id}'
    cache.add(key,0,timeout=60)
    try:count=cache.incr(key)
    except ValueError:cache.set(key,1,timeout=60);count=1
    if count>20:raise HttpError(429,'AI request limit reached. Wait one minute and retry.')
