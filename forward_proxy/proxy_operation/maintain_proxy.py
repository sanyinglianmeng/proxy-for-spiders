import heapq
import random
import asyncio

import aioredis

from config import config
from model import ProxyManager, PatternManager


proxy_manager = ProxyManager()
pattern_manager = PatternManager()


async def maintain_proxies():
    redis = await aioredis.create_redis_pool(config.REDIS_ADDRESS)
    while True:
        total_proxy_num = len(proxy_manager.proxies()[0])
        if total_proxy_num <= 200:
            proxy_manager.add_proxies(20)

        patterns = list(pattern_manager.patterns()[0].keys())
        patterns.append('default_proxy_hash')
        for pattern in patterns:
            await _maintain_proxies_for_pattern(pattern, redis)

        await asyncio.sleep(config.FRESH_INTERVAL)


async def _maintain_proxies_for_pattern(pattern, redis):
    proxies = await redis.hgetall(pattern)
    if len(proxies) <= 100 and pattern != 'default_proxy_hash':
        proxy_manager.copy_default_proxy_hash(pattern)

    fail_key = '_'.join((pattern, 'fail',))
    if await redis.hlen(pattern) <= 5:
        await redis.delete(fail_key)

    del_threshold = -3 if pattern != 'default_proxy_hash' else -10
    for proxy, score in proxies.items():
        if int(score) <= del_threshold:
            await redis.hdel(pattern, proxy)
            await redis.sadd(fail_key, proxy)

    await _refresh_score_proxies(pattern, redis)
    await _refresh_random_proxies(pattern, redis)


async def _refresh_random_proxies(pattern, redis):
    proxies = await redis.hgetall(pattern)
    shuffle_key = '_'.join((pattern, 'shuffle',))
    it = random.sample(list(proxies), 5) if len(proxies) >= 5 else proxies

    for proxy in it:
        redis.sadd(shuffle_key, proxy)

    key_length = await redis.scard(shuffle_key)
    if key_length > 5:
        for _ in range(key_length-5):
            await redis.spop(shuffle_key)


async def _refresh_score_proxies(pattern, redis):
    proxies = await redis.hgetall(pattern)
    top_five = heapq.nlargest(5, proxies, key=lambda a: int(proxies[a]))
    if len(top_five) < 5 or int(proxies[top_five[-3]]) < 0:
        proxy_manager.add_proxies(10, pattern)

    score_key = '_'.join((pattern, 'score',))
    tr = redis.multi_exec()
    tr.delete(score_key)
    for proxy in top_five:
        tr.zadd(score_key, int(proxies[proxy]), proxy)
    await tr.execute()
