"""Shared, atomic fixed-window login throttling. Redis failure fails closed."""
from functools import lru_cache
from fastapi import HTTPException
from redis.asyncio import Redis
from redis.exceptions import RedisError
from .config import settings
from .security import digest

SCRIPT = '''
local coarse = redis.call('INCR', KEYS[1])
if coarse == 1 then redis.call('EXPIRE', KEYS[1], 60) end
if coarse > tonumber(ARGV[1]) then return 0 end
local account = redis.call('INCR', KEYS[2])
if account == 1 then redis.call('EXPIRE', KEYS[2], 60) end
if account > tonumber(ARGV[2]) then return 0 end
return 1
'''

@lru_cache(maxsize=1)
def redis_client():
    return Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2,
                          max_connections=30, decode_responses=True)

async def shared_auth_limit(ip, account_key, path):
    # Raw email addresses and IPs are never stored as Redis keys.
    try:
        allowed = await redis_client().eval(SCRIPT, 2,
            'bc:auth:ip:'+digest(ip), 'bc:auth:account:'+digest(account_key),
            settings.auth_ip_limit_per_minute, 60 if path=='/v1/auth/google/challenge' else 10)
    except RedisError:
        raise HTTPException(503, 'Sign-in temporarily unavailable; please retry shortly') from None
    if not allowed:
        raise HTTPException(429, 'Too many attempts; retry in one minute', headers={'Retry-After':'60'})
