from flask import jsonify, request

from .app import app, get_request_connection
from model import Pattern, PatternManager


@app.route('/pattern/<pattern_str>', methods=('GET',))
def pattern_info(pattern_str):
    pattern = Pattern(pattern_str, redis_conn=get_request_connection())
    data = {
        'success_rate': pattern.success_rate,
        'recent_responses': [str(r) for r in pattern.recent_responses],
        'rule': pattern.rule,
    }
    return jsonify(data=data, status=100, msg='OK')


@app.route('/pattern/<pattern_str>', methods=('POST',))
def modify_pattern(pattern_str):
    pattern = Pattern(pattern_str)
    rule = request.args.get('rule', '')
    action = request.args.get('action', 'add')
    pm = PatternManager(redis_conn=get_request_connection())
    if action == 'add':
        pm.add(pattern, rule)
    elif action == 'delete':
        pm.delete(pattern)
    else:
        pm.update(pattern, rule)
    return jsonify(msg='OK', status=100)


@app.route('/patterns')
def patterns():
    pm = PatternManager(redis_conn=get_request_connection())
    return jsonify(data=pm.patterns(), status=100, msg='OK')
