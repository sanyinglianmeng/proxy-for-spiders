def parse_free(text):
    import json
    j = json.loads(text)
    for i in j:
        ip, port = i.split(':')
        yield (ip, port,)


class Config(object):

    @staticmethod
    def init_app(app):
        pass

    REDIS_ADDRESS = 'redis://localhost'
    REDIS_HOST = '127.0.0.1'
    REDIS_PORT = 6379
    REDIS_DB = 0

    CONCURRENT = 5
    SELECT_STYLE = 'score'
    INIT_SCORE = 3
    FRESH_INTERVAL = 1
    MIN_VALID_LENGTH = 10
    RESULT_SAVE_NUM = 100
    LOCAL_REQUEST_DELAY = 6

    TAG_API_MAP = {
        'free': 'http://127.0.0.1:8889/get_all/',
    }

    TAG_PARSE_MAP = {
        'free': parse_free,
    }

    TAG_WHITELIST_MAP = {

    }

    NOT_TRUST_404 = {}

    GLOBAL_BLACKLIST = {'ydstatic', 'nail club', 'forbid', 'identified as anonymous', 'weui_input frm_input', '异常访问请求'}

    PATTERN_ENCODING_MAP = {

    }


config = Config()
