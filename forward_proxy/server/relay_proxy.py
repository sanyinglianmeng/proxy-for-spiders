import re
import asyncio

import aioredis
from aiohttp import web

from config import config
from model import PatternManager, ProxyManager
from utils import utils
from crawler.crawler import crawl


logger = utils.LogHandler('server')
pattern_manager = PatternManager()
proxy_manager = ProxyManager()


async def redis_pool(app):
    app['redis'] = await aioredis.create_redis_pool(config.REDIS_ADDRESS)
    yield
    app['redis'].close()
    await app['redis'].wait_closed()


def init_http_app():
    app = web.Application()
    app.cleanup_ctx.append(redis_pool)
    app.add_routes([web.get('/{path:.*}', receive_request)])
    app.add_routes([web.post('/{path:.*}', receive_request)])
    return app


async def receive_request(request):
    body = await request.content.read()
    url = str(request.url)
    headers = request.headers
    method = request.method

    pattern, rule = pattern_manager.t.closest_pattern(url)
    proxies = proxy_manager.get_proxies_with_pattern(pattern, style=config.SELECT_STYLE)
    valid_length, xpath, value = rule.split(', ')

    result = await crawl(url, proxies=proxies, pattern=pattern, data=body, headers=headers, method=method,
                         valid_length=int(valid_length), xpath=xpath, value=value)
    if result and result.status_code and result.text:
        return web.Response(status=result.status_code, text=result.text, headers=result.headers)
    return web.Response(status=417, text="None of proxies' response is valid")


MAX_RETRY_TIMES = 3
RETRY_INTERVAL = 0.2
REGEX_CONTENT_LENGTH = re.compile(r'\r\nContent-Length: ([0-9]+)\r\n', re.IGNORECASE)
REGEX_HOST = re.compile(r'(.+?):([0-9]{1,5})')


async def read_header(reader):
    header = ''
    receive_retried_times = 0
    while True:
        line = await reader.readline()
        if line is None:
            if len(header) == 0 and receive_retried_times < MAX_RETRY_TIMES:
                receive_retried_times += 1
                await asyncio.sleep(RETRY_INTERVAL)
                continue
            else:
                break
        if line == b'\r\n':
            header += line.decode()
            break
        if line != b'':
            header += line.decode()
    return header


def parse_header(header):
    request = header.split('\r\n')[:-1]
    if len(request) == 0:
        raise ValueError('request length too short')
    head = request[0].split(' ')
    method = head[0]
    m = REGEX_HOST.search(head[1])
    host, port = m.group(1), int(m.group(2))
    return method, host, port


async def _relay(reader, writer):
    first_line = True
    while True:
        line = await reader.read(1024)
        if len(line) == 0:
            if first_line:
                raise ConnectionError('first line is empty after connected')
            else:
                break
        writer.write(line)
        first_line = False


async def relay_request(input_reader, input_writer):
    header = await read_header(input_reader)
    method, host, port = parse_header(header)
    if method == 'CONNECT':
        logger.info('relaying SSL connection, destination is {0}:{1}'.format(host, port))
    proxies = proxy_manager.get_proxies_with_pattern('default_proxy_hash', style=config.SELECT_STYLE)
    for proxy in proxies:
        proxy = proxy.replace('http://', '')
        proxy_host, proxy_port = proxy.split(':')[0], int(proxy.split(':')[1])
        tasks = list()
        output_writer = None
        try:
            output_reader, output_writer = await asyncio.open_connection(proxy_host, proxy_port, ssl=False)
            output_writer.write(header.encode())
            tasks = [
                asyncio.create_task(_relay(output_reader, input_writer)),
                asyncio.create_task(_relay(input_reader, output_writer)),
            ]
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.info(e, exc_info=True)
            for task in tasks:
                task.cancel()
            if output_writer is not None:
                output_writer.close()
            continue
        else:
            input_writer.close()
            break
