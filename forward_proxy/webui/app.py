import redis
from flask import Flask, g

from config import config


app = Flask(__name__)
app.config.from_object(config)
config.init_app(app)


def request_has_connection():
    return hasattr(g, 'redis_conn')


def get_request_connection():
    if not request_has_connection():
        g.redis_conn = redis.StrictRedis(host=config.REDIS_HOST, port=config.REDIS_PORT,
                                         db=config.REDIS_DB, decode_responses=True)
    return g.redis_conn
