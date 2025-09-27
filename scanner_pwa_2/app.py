# app.py
from flask import Flask, send_from_directory, send_file, request, jsonify
import os
import json
import datetime
import threading
import logging
import redis

# Blueprints
from routes.routes_scanner import scanner_bp
from routes.routes_api_scanner import api_scanner_bp
from routes.routes_push import push_bp
from routes.routes_auth import auth_bp  # your auth blueprint

# Optional push helpers (as in your original)
import push_db
import push_utils

# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.register_blueprint(scanner_bp)
app.register_blueprint(api_scanner_bp)
app.register_blueprint(push_bp)
app.register_blueprint(auth_bp)

# -----------------------------------------------------------------------------
# Redis client (used by /api/me and push worker)
# -----------------------------------------------------------------------------
REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
redis_client = redis.from_url(REDIS_URL)

# -----------------------------------------------------------------------------
# Service Worker + Manifest (root scope and /scanner scope)
# -----------------------------------------------------------------------------
@app.route('/sw.js')
def service_worker():
    """
    Serve the service worker at the site root so its scope covers the whole app.
    """
    sw_path = os.path.join(app.static_folder or 'static', 'sw.js')
    if not os.path.exists(sw_path):
        # Fallback to normal static serving (will 404 if truly missing)
        return send_from_directory(app.static_folder or 'static', 'sw.js')
    return send_file(sw_path, mimetype='application/javascript')


@app.route('/manifest.json')
def manifest():
    """
    Serve the PWA manifest with the correct JSON mimetype.
    """
    mf_path = os.path.join(app.static_folder or 'static', 'manifest.json')
    if not os.path.exists(mf_path):
        return send_from_directory(app.static_folder or 'static', 'manifest.json')
    return send_file(mf_path, mimetype='application/json')


# Mirror SW + manifest under /scanner so the PWA works when hosted at /scanner
@app.route('/scanner/sw.js')
def scanner_service_worker():
    return service_worker()


@app.route('/scanner/manifest.json')
def scanner_manifest():
    return manifest()


# Icons under /scanner/static/icons/*
@app.route('/scanner/static/icons/<path:filename>')
def scanner_icons(filename):
    return send_from_directory(os.path.join(app.static_folder or 'static', 'icons'), filename)


# Offline page under /scanner
@app.route('/scanner/offline.html')
def scanner_offline():
    return send_from_directory(app.static_folder or 'static', 'offline.html')

# -----------------------------------------------------------------------------
# Auth status endpoint for the frontend (Flask style)
# -----------------------------------------------------------------------------
@app.route("/api/me", methods=["GET"])
def api_me():
    """
    Returns { authenticated: bool, user?: {username,email,name} }
    Reads the session ID from the first-party cookie 'scanner_session',
    then looks up user info in Redis (written by your FastAPI callback).
    """
    session_cookie = request.cookies.get("scanner_session")
    if not session_cookie:
        return jsonify({"authenticated": False}), 200

    try:
        raw = redis_client.get(session_cookie)
        if not raw:
            return jsonify({"authenticated": False}), 200

        session_data = json.loads(raw)
        user = {
            "username": session_data.get("username"),
            "email":    session_data.get("email"),
            "name":     session_data.get("name"),
        }
        return jsonify({"authenticated": True, "user": user}), 200
    except Exception as e:
        app.logger.error(f"/api/me error: {e}")
        return jsonify({"authenticated": False}), 200

# -----------------------------------------------------------------------------
# Prevent stale HTML from being cached by the browser/PWA
# -----------------------------------------------------------------------------
@app.after_request
def no_store_for_html(resp):
    ct = resp.headers.get('Content-Type', '')
    if resp.status_code == 200 and ('text/html' in ct):
        resp.headers['Cache-Control'] = 'no-store'
    return resp

# -----------------------------------------------------------------------------
# Jinja2 filter
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# Background push worker (unchanged from your snippet)
# -----------------------------------------------------------------------------
def push_worker():
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
                push_utils.send_push(s, {'message': job.get('message')}, vapid_priv, vapid_claims)
        except Exception as e:
            print('push_worker error', e)

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # ensure push DB is ready, start worker thread
    push_db.ensure_db()
    t = threading.Thread(target=push_worker, daemon=True)
    t.start()

    # Run Flask dev server
    app.run(host="0.0.0.0", port=5005, debug=True)
