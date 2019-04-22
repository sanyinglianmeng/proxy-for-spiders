import asyncio

from utils import utils
from model import PatternManager, ProxyManager
from config import config
from crawler.crawler import crawl


logger = utils.LogHandler(__name__, file=False)
pattern_manager = PatternManager()
proxy_manager = ProxyManager()


class Forward(object):

    @staticmethod
    async def forward_request(flow):
        url = flow.request.pretty_url
        headers = flow.request.headers
        body = flow.request.content
        method = flow.request.method

        pattern, rule = pattern_manager.t.closest_pattern(url)
        proxies = proxy_manager.get_proxies_with_pattern(pattern, style=config.SELECT_STYLE)
        valid_length, xpath, value = rule.split(', ')

        result = await crawl(url, proxies=proxies, pattern=pattern, data=body, headers=headers, method=method,
                             valid_length=int(valid_length), xpath=xpath, value=value)
        if result is not None:
            flow.response.text = result.text
            flow.response.status_code = result.status_code
        flow.resume()

    def response(self, flow):
        flow.intercept()
        loop = asyncio.get_event_loop()
        loop.create_task(self.forward_request(flow))
