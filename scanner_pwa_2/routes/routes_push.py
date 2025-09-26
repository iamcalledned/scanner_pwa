from flask import Blueprint, request, jsonify, send_file
import os
import json
from . import routes_scanner as scanner_routes
import push_db
import push_utils
import redis

push_bp = Blueprint('push', __name__)

REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
redis_client = redis.from_url(REDIS_URL)

VAPID_PUBLIC_FILE = os.path.join(os.path.dirname(__file__), '..', 'vapid_public.key')
VAPID_PRIVATE_FILE = os.path.join(os.path.dirname(__file__), '..', 'vapid_private.key')


@push_bp.route('/scanner/push/vapid_public')
def get_vapid_public():
    if os.path.exists(VAPID_PUBLIC_FILE):
        # return the raw base64url public key as plain text so the client can consume it directly
        with open(VAPID_PUBLIC_FILE, 'r') as f:
            key = f.read().strip()
        return (key, 200, {'Content-Type': 'text/plain; charset=utf-8'})
    return jsonify({'error': 'no key'}), 404


@push_bp.route('/scanner/push/subscribe', methods=['POST'])
def subscribe():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'invalid json'}), 400
    push_db.save_subscription(data)
    return jsonify({'success': True})


@push_bp.route('/scanner/push/unsubscribe', methods=['POST'])
def unsubscribe():
    data = request.get_json()
    endpoint = data.get('endpoint')
    push_db.remove_subscription(endpoint)
    return jsonify({'success': True})


@push_bp.route('/scanner/push/send', methods=['POST'])
def send_push():
    data = request.get_json() or {}
    message = data.get('message', 'Test push')
    # push job to redis list
    redis_client.lpush('push_queue', json.dumps({'message': message}))
    return jsonify({'queued': True})


@push_bp.route('/scanner/push/send_now', methods=['POST'])
def send_push_now():
    """Send a push to all stored subscriptions immediately (useful for testing).

    WARNING: this will attempt to send to every subscription in the DB and will
    perform network calls synchronously. Intended for local testing only.
    """
    data = request.get_json() or {}
    message = data.get('message', 'Test push')
    vapid_pub, vapid_priv = push_utils.load_vapid_keys()
    if not vapid_priv:
        return jsonify({'error': 'VAPID private key not configured'}), 500
    vapid_claims = {'sub': 'mailto:admin@iamcalledned.ai'}
    results = []
    subs = push_db.list_subscriptions()
    for s in subs:
        try:
            ok, err = push_utils.send_push(s, {'message': message}, vapid_priv, vapid_claims)
            entry = {'endpoint': s.get('endpoint'), 'ok': bool(ok)}
            if err:
                entry['error'] = str(err)
            results.append(entry)
        except Exception as e:
            results.append({'endpoint': s.get('endpoint'), 'ok': False, 'error': str(e)})
    return jsonify({'sent': sum(1 for r in results if r.get('ok')), 'results': results})

