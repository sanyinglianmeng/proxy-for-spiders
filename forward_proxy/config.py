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

    CONCURRENT = 3
    SELECT_STYLE = 'score'
    INIT_SCORE = 3
    FRESH_INTERVAL = 1
    MIN_VALID_LENGTH = 10
    RESULT_SAVE_NUM = 100

    TAG_API_MAP = {
        'free': 'http://192.168.8.172:8999/get_all/',
    }

    TAG_PARSE_MAP = {
        'free': parse_free,
    }

    TAG_WHITELIST_MAP = {

    }

    NOT_TRUST_404 = {}

    BLACK_KEYWORDS = {'ydstatic', 'nail club', 'forbid', 'identified as anonymous'}

    PATTERN_ENCODING_MAP = {

    }


config = Config()
