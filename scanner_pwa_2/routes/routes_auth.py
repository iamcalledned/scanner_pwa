# routes/routes_auth.py
from flask import Blueprint, request, redirect, jsonify, make_response
import os, json, time, requests

auth_bp = Blueprint("auth", __name__)

# ---- Configure via environment (works out of the box with sensible defaults) ----
LOGIN_VALIDATE_URL = os.environ.get("LOGIN_VALIDATE_URL", "http://127.0.0.1:8010/api/me")
COOKIE_NAME       = os.environ.get("AUTH_COOKIE_NAME", "scanner_session")
COOKIE_DOMAIN     = os.environ.get("AUTH_COOKIE_DOMAIN", ".iamcalledned.ai")  # include leading dot
COOKIE_SECURE     = os.environ.get("AUTH_COOKIE_SECURE", "true").lower() == "true"
COOKIE_SAMESITE   = os.environ.get("AUTH_COOKIE_SAMESITE", "None")  # None|Lax|Strict

@auth_bp.route("/scanner/auth/callback")
def auth_callback():
    """
    Receives ?token=<...>&exp=<unix_ts>&redirect=/scanner after login is done,
    sets a first-party cookie on .iamcalledned.ai so every page can read it.
    """
    token = request.args.get("token")
    redirect_to = request.args.get("redirect") or "/scanner"
    exp = request.args.get("exp")

    if not token:
        return redirect(redirect_to)

    # Cookie lifetime (defaults to 7 days unless exp is provided)
    max_age = None
    try:
        if exp:
            max_age = max(0, int(exp) - int(time.time()))
    except Exception:
        pass
    if not max_age:
        max_age = 7 * 24 * 3600

    resp = make_response(redirect(redirect_to))
    resp.set_cookie(
        COOKIE_NAME,
        token,
        max_age=max_age,
        secure=COOKIE_SECURE,
        httponly=True,
        samesite=COOKIE_SAMESITE,   # if cross-site: must be "None" + Secure
        domain=COOKIE_DOMAIN,
        path="/",
    )
    return resp

@auth_bp.route("/scanner/api/me")
def me():
    """
    Returns {authenticated, user?} by validating our cookie with the login service.
    If you'd rather validate Cognito JWTs here, replace the requests.get() call
    with JWKS verification.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return jsonify({"authenticated": False}), 200

    try:
        r = requests.get(
            LOGIN_VALIDATE_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=4,
        )
        if r.ok:
            data = r.json() or {}
            return jsonify({"authenticated": True, "user": data.get("user") or data}), 200
    except Exception:
        pass

    return jsonify({"authenticated": False}), 200

@auth_bp.route("/scanner/logout")
def logout():
    resp = make_response(redirect("/scanner"))
    resp.set_cookie(
        COOKIE_NAME, "", max_age=0, secure=COOKIE_SECURE, httponly=True,
        samesite=COOKIE_SAMESITE, domain=COOKIE_DOMAIN, path="/",
    )
    return resp
