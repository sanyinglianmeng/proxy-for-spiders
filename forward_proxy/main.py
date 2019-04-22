import asyncio

from aiohttp import web

from server import relay_proxy
from server import mitm_proxy
from proxy_operation import maintain_proxy

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass


def run_maintainer():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(maintain_proxy.maintain_proxies())


def run_server(port=None):
    app = relay_proxy.init_http_app()
    web.run_app(app, port=port)


def run_https_server(port=None):
    loop = asyncio.get_event_loop()
    app = asyncio.start_server(relay_proxy.relay_request, host='0.0.0.0', port=port, loop=loop)
    loop.run_until_complete(app)
    loop.run_forever()


addons = [
    mitm_proxy.Forward()
]


if __name__ == '__main__':
    # run_server(8893)
    run_maintainer()
    # run_https_server(8893)
