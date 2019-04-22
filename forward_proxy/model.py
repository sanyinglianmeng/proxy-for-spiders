import re
import ast
from functools import total_ordering

import furl
import redis
import requests
from pygtrie import CharTrie

from config import config


class Response(object):

    def __init__(self, create_time=None, status_code=None, url=None, text=None, is_valid=None, info=None):
        if info is not None:
            create_time, url, status_code, is_valid, text = info.split('$$', maxsplit=4)
        self.is_valid = ast.literal_eval(str(is_valid))
        self.status_code = status_code
        self.url = url
        self.text = text
        self.create_time = int(str(create_time).split('.')[0]) if create_time else None

    def __str__(self):
        return '{url} {status} {html}'.format(url=self.url, status=self.status_code, html=str(self.text)[:200])


class RedisModel(object):

    def __init__(self, **kwargs):
        if 'redis_conn' in kwargs and kwargs['redis_conn'] is not None:
            self._redis_conn = kwargs['redis_conn']
        else:
            self._redis_conn = redis.StrictRedis(host=config.REDIS_HOST, port=config.REDIS_PORT,
                                                 db=config.REDIS_DB, decode_responses=True)


class StatisticsMixin(object):

    @property
    def success_rate(self):
        success_num, total_num = 0, 0
        for response in self.recent_responses:
            if response.is_valid:
                success_num += 1
            total_num += 1
        if total_num == 0:
            return 0
        success_rate = success_num / total_num
        return success_rate

    @property
    def recent_responses(self):
        key = '_'.join((str(self), 'result'))
        for info in self._redis_conn.lrange(key, 0, 100):
            if info is None:
                continue
            yield Response(info=info)


@total_ordering
class Proxy(StatisticsMixin, RedisModel):

    def __init__(self, ip, port, **kwargs):
        super(Proxy, self).__init__(**kwargs)
        self.ip = ip
        self.port = int(port)

    def __str__(self):
        return '{0}:{1}'.format(self.ip, self.port)

    def __eq__(self, other):
        return self.success_rate == other.success_rate

    def __gt__(self, other):
        return self.success_rate > other.success_rate

    @classmethod
    def parse(cls, proxy, **kwargs):
        if proxy.startswith('http'):
            proxy = re.sub(r'https?://', '', proxy, 1)
        ip, port = proxy.split(':')
        return Proxy(ip, port, redis_conn=kwargs.get('redis_conn', None))


class ProxyManager(RedisModel):

    def __init__(self, **kwargs):
        super(ProxyManager, self).__init__(**kwargs)

    def proxies(self):
        d = self._redis_conn.hgetall("default_proxy_hash")
        return [{k: {'score': Proxy.parse(k).success_rate} for k in d}]

    def get_proxies_with_pattern(self, pattern, style='score'):
        if style == 'shuffle':
            shuffle_key = ''.join([pattern, '_shuffle'])
            proxies = self._redis_conn.smembers(shuffle_key)
        else:
            score_key = ''.join([pattern, '_score'])
            proxies = self._redis_conn.zrevrange(score_key, 0, 4)
        concurrent_num = min(len(proxies), config.CONCURRENT)
        proxies = [proxies[i] for i in range(concurrent_num)]
        # proxies.append(None)
        return proxies

    def _fetch_proxies(self, num, tag='free'):
        api = config.TAG_API_MAP[tag].format(num)
        response = requests.get(api)
        try:
            f = config.TAG_PARSE_MAP[tag]
            for ip, port in f(response.text):
                yield Proxy(ip, port)
        except NameError:
            raise NotImplementedError('parse function for tag {0} not implemented'.format(tag))

    def _add_proxy2hash(self, proxy, pattern=None):
        default_score = int(config.INIT_SCORE)
        if self._redis_conn.hexists('default_proxy_hash', str(proxy)):
            return False
        self._redis_conn.hset('default_proxy_hash', str(proxy), 0)

        if pattern is not None and pattern != 'default_proxy_hash':
            if self._redis_conn.sismember(pattern + '_fail', str(proxy)) == 0:
                self._redis_conn.hset(pattern, str(proxy), default_score)
            else:
                return False
        return True

    def add_proxies(self, num, pattern=None):
        added_num = 0
        for tag in config.TAG_API_MAP:
            for proxy in self._fetch_proxies(num, tag=tag):
                if self._add_proxy2hash(proxy, pattern):
                    added_num += 1
                    if added_num > num:
                        break
        return added_num

    def copy_default_proxy_hash(self, pattern):
        default_proxy_dict = self._redis_conn.hgetall('default_proxy_hash')
        for k, v in default_proxy_dict.items():
            if self._redis_conn.sismember(pattern + '_fail', k) == 0:
                self._redis_conn.hset(pattern, k, max(v, 0))


class Pattern(StatisticsMixin, RedisModel):

    def __init__(self, pattern, **kwargs):
        super(Pattern, self).__init__(**kwargs)
        self.pattern = pattern

    @property
    def rule(self):
        return self._redis_conn.hget('response_check_pattern', str(self))

    def __str__(self):
        return self.pattern


class PatternManager(RedisModel):

    def __init__(self, **kwargs):
        super(PatternManager, self).__init__(**kwargs)
        self.t = self._init_trie()

    def patterns(self):
        d = self._redis_conn.hgetall('response_check_pattern')
        return [{k: {'rule': Pattern(k).rule, 'score': Pattern(k).success_rate} for k in d}]

    def _init_trie(self):
        patterns = self._redis_conn.hgetall('response_check_pattern')
        return CheckPatternTrie(patterns)

    def restore_trie(self, t):
        self._redis_conn.hmset('response_check_pattern', t)

    def add(self, pattern, rule):
        self.t[pattern] = rule
        self._redis_conn.hset('response_check_pattern', str(pattern), rule)

    def delete(self, pattern):
        del self.t[pattern]
        self._redis_conn.hdel('response_check_pattern', str(pattern))

    def update(self, pattern, rule):
        self.add(pattern, rule)


class CheckPatternTrie(CharTrie):

    def __init__(self, *args, **kwargs):
        super(CheckPatternTrie, self).__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        super(CheckPatternTrie, self).__setitem__(self._remove_http_prefix(key), value)

    def closest_pattern(self, url):
        url = self._remove_http_prefix(url)
        step = self.longest_prefix(url)
        pattern, rule = step.key, step.value
        if pattern is None:
            pattern, rule = 'default_proxy_hash', ', '.join((str(config.MIN_VALID_LENGTH), '', ''))
        return pattern, rule

    @staticmethod
    def _remove_http_prefix(url):
        if url.startswith('http'):
            url = re.sub(r'https?://', '', url, 1)
        return url

    @staticmethod
    def _remove_qs_fg(url):
        return furl.furl(url).remove(args=True, fragment=True).url
