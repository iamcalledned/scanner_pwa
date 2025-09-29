from flask import Flask, send_from_directory, send_file, jsonify
import os
from routes.routes_scanner import scanner_bp
from routes.routes_api_scanner import api_scanner_bp
import datetime
import json
from routes.routes_push import push_bp
import threading
import redis
import push_db
import push_utils

app = Flask(__name__)
app.register_blueprint(scanner_bp)
app.register_blueprint(api_scanner_bp)
app.register_blueprint(push_bp)


# Serve service worker and manifest at site root so scope covers the whole app
@app.route('/sw.js')
def service_worker():
    sw_path = os.path.join(app.static_folder, 'sw.js')
    if not os.path.exists(sw_path):
        return send_from_directory(app.static_folder, 'sw.js')
    return send_file(sw_path, mimetype='application/javascript')


@app.route('/manifest.json')
def manifest():
    mf_path = os.path.join(app.static_folder, 'manifest.json')
    if not os.path.exists(mf_path):
        return send_from_directory(app.static_folder, 'manifest.json')
    return send_file(mf_path, mimetype='application/json')


@app.route('/scanner/sw.js')
def scanner_service_worker():
    return service_worker()


@app.route('/scanner/manifest.json')
def scanner_manifest():
    return manifest()


@app.route('/scanner/static/icons/<path:filename>')
def scanner_icons(filename):
    return send_from_directory(os.path.join(app.static_folder, 'icons'), filename)


@app.route('/scanner/offline.html')
def scanner_offline():
    return send_from_directory(app.static_folder, 'offline.html')


# ---- API endpoint for user count ----
@app.route('/scanner/api/users')
def api_users():
    """Return number of connected/unregistered users (via push subscriptions)."""
    try:
        subs = push_db.list_subscriptions()
        return jsonify({"users": len(subs)})
    except Exception as e:
        return jsonify({"users": 0, "error": str(e)}), 500


# ---- Alias so /api/users also works ----
@app.route('/api/users')
def api_users_alias():
    return api_users()


# Register Jinja2 filter
@app.template_filter("datetimeformat")
def datetimeformat(value, format="%b %d, %I:%M %p"):
    if isinstance(value, (int, float)):
        value = datetime.datetime.fromtimestamp(value)
    elif isinstance(value, str):
        try:
            value = datetime.datetime.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime(format)


if __name__ == "__main__":
    # start push queue worker in background
    def push_worker():
        REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
        r = redis.from_url(REDIS_URL)
        vapid_pub, vapid_priv = push_utils.load_vapid_keys()
        vapid_claims = {'sub': 'mailto:admin@iamcalledned.ai'}
        while True:
            item = r.brpop('push_queue', timeout=5)
            if not item:
                continue
            _, payload = item
            try:
                job = json.loads(payload)
                subs = push_db.list_subscriptions()
                for s in subs:
                    push_utils.send_push(
                        s,
                        {'message': job.get('message')},
                        vapid_priv,
                        vapid_claims
                    )
            except Exception as e:
                print('push_worker error', e)

    push_db.ensure_db()
    t = threading.Thread(target=push_worker, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5005, debug=True)
