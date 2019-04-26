import time
import asyncio

import aiohttp

from utils import utils
from config import config
from model import Response
from crawler import validate


logger = utils.LogHandler(__name__, file=False)


async def async_crawl(url, session, method='GET', proxy=None, data=None, headers=None, encoding=None):
    url = url.replace('https://', 'http://', 1)
    if proxy is not None:
        proxy = 'http://' + proxy
    request = session.get if method == 'GET' else session.post
    response = Response()
    try:
        delay = config.LOCAL_REQUEST_DELAY if proxy is None else 0
        if delay > 0:
            await asyncio.sleep(delay)
            logger.info('local fail back request begin sending')
        async with request(url, headers=headers, data=data, proxy=proxy, ssl=False, timeout=10-delay) as r:
            if r._body is None:
                await r.read()
            if encoding is None:
                encoding = r.get_encoding()
            if encoding.lower() == 'gb2312':
                encoding = 'gbk'
            data = r._body.decode(encoding, errors='strict')
            response = Response(create_time=int(time.time() * 1000), status_code=r.status, url=url,
                                text=data, is_valid=False)
    except asyncio.CancelledError:
        response.is_cancelled = True
    except aiohttp.ClientError:
        pass
    except asyncio.TimeoutError:
        pass
    except Exception as e:
        logger.warning(e, exc_info=True)
    finally:
        return response


async def async_crawl_and_check(url, session, pattern, method='GET', proxy=None, data=None, headers=None, encoding=None,
                                valid_length=None, xpath=None, value=None):
    response = await async_crawl(url, session, method, proxy, data, headers, encoding)
    if not response.is_cancelled:
        is_valid = await validate.check_response(url, pattern, proxy, response.status_code, response.text,
                                                 valid_length, xpath, value)
        if is_valid:
            response.is_valid = True
    return response


async def crawl(url, proxies, pattern=None, method='GET', data=None, headers=None, valid_length=None,
                xpath=None, value=None):
    need_check = all((any(proxies), pattern, valid_length))
    encoding = config.PATTERN_ENCODING_MAP.get(pattern)
    async with aiohttp.ClientSession() as session:
        if need_check:
            tasks = [asyncio.ensure_future(async_crawl_and_check(url, session, pattern, method,
                                                                 proxy, data, headers, encoding,
                                                                 valid_length, xpath, value)) for proxy in proxies]
        else:
            tasks = [asyncio.ensure_future(async_crawl(url, session, method, proxy, data, headers, encoding))
                     for proxy in proxies]
        for task in asyncio.as_completed(tasks):
            response = await task
            if need_check:
                if response.is_valid:
                    for t in tasks:
                        if not t.done():
                            t.cancel()
                    return response
            else:
                return response
