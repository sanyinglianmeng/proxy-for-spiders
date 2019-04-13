from flask import jsonify

from .app import app, get_request_connection
from model import Proxy, ProxyManager


@app.route("/proxy/<proxy_str>")
def proxy_info(proxy_str):
    proxy = Proxy.parse(proxy_str, redis_conn=get_request_connection())
    data = {
        'success_rate': proxy.success_rate,
        'recent_responses': [str(r) for r in proxy.recent_responses]
    }
    return jsonify(data=data, status=100, msg="OK")


@app.route("/proxies")
def proxies():
    pm = ProxyManager(redis_conn=get_request_connection())
    return jsonify(data=pm.proxies(), status=100, msg="OK")
