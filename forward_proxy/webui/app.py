import redis
from flask import Flask, jsonify, g

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


@app.errorhandler(404)
def not_found(e):
    return jsonify({
        'reason': 'resource not found',
        'status_code': 404
    })


@app.errorhandler(500)
def not_found(e):
    return jsonify({
        'reason': 'internal server error',
        'status_code': 500
    })
