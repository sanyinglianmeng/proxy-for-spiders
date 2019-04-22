import time
import asyncio
from lxml import etree

import aioredis

from utils import utils
from config import config


logger = utils.LogHandler(__name__, file=False)
pattern_lock_map = dict()


def _status_checker(pattern, status):
    if status is None or (status == 404 and pattern in config.NOT_TRUST_404) or (status != 404 and status >= 400):
        return False
    return True


def _xpath_checker(html, xpath, value):
    try:
        et = etree.HTML(html)
        assert et.xpath(xpath)[0] == value
    except IndexError:
        pass
    except AssertionError:
        pass
    except Exception as e:
        logger.warning(e, exc_info=True)
    else:
        return True
    return False


def _html_checker(html, valid_length, xpath, value):
    if html is None or len(html) < valid_length or any((word in html
                                                        for word in config.GLOBAL_BLACKLIST)):
        return False
    if xpath == 'whitelist' and value not in html:
        return False
    elif xpath == 'blacklist' and any((word in html for word in value.split('|'))):
        return False
    elif len(xpath.strip()) == 0 or len(value.strip()) == 0:
        return True
    else:
        return _xpath_checker(html, xpath, value)


async def _result_saver(key, url, status, html, is_valid, redis):
    result_key = '_'.join((key, 'result',))
    value = "$$".join((str(time.time() * 1000), url, str(status), str(is_valid), str(html)))
    await redis.lpush(result_key, value)
    await redis.ltrim(result_key, 0, config.RESULT_SAVE_NUM)


async def _score_counters(pattern, proxy, is_valid, redis):
    if pattern not in pattern_lock_map:
        pattern_lock_map[pattern] = asyncio.Lock()
    async with pattern_lock_map[pattern]:
        v = await redis.hget(pattern, proxy)
        if is_valid:
            if v is None or int(v) < 0:
                await redis.hset(pattern, proxy, 0)
                await redis.hset('default_proxy_hash', proxy, 0)
            elif 0 <= int(v) < 10:
                await redis.hincrby(pattern, proxy, 1)
                if pattern != 'default_proxy_hash':
                    await redis.hincrby('default_proxy_hash', proxy, 1)
        else:
            if v is not None:
                await redis.hincrby(pattern, proxy, -1)
                if pattern != 'default_proxy_hash':
                    await redis.hincrby('default_proxy_hash', proxy, -1)


async def check_response(url, pattern, proxy, status, html, valid_length, xpath, value):
    redis = await aioredis.create_redis(config.REDIS_ADDRESS)
    is_valid = all((_status_checker(pattern, status), _html_checker(html, valid_length, xpath, value),))
    if proxy is not None:
        await _result_saver(proxy, url, status, html, is_valid, redis)
        await _result_saver(pattern, url, status, html, is_valid, redis)
        await _score_counters(pattern, proxy, is_valid, redis)
    redis.close()
    await redis.wait_closed()
    return is_valid
