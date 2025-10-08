from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

import os
import base64
import hashlib
import httpx
import jwt
import datetime
import json
import time
import logging
import asyncio
import redis

from config import Config
from process_handler_database import (
    create_db_pool,
    save_code_verifier,
    save_code_verifier_with_return,
    get_code_verifier,
    get_verifier,
    generate_code_verifier_and_challenge,
    get_data_from_db,
    save_user_info_to_userdata,
    delete_code_verifier,
    delete_old_verifiers,
)
from jwt.algorithms import RSAAlgorithm
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

log_file_path = Config.LOG_PATH
LOG_FORMAT = 'LOGIN-PROCESS -  %(asctime)s - %(processName)s - %(name)s - %(levelname)s - %(message)s'

logging.basicConfig(
    filename=Config.LOG_PATH_PROCESS_HANDLER,
    level=logging.DEBUG,
    format=LOG_FORMAT
)

# Initialize Redis client using configurable host/port
REDIS_HOST = Config.REDIS_HOST or 'localhost'
try:
    REDIS_PORT = int(Config.REDIS_PORT) if Config.REDIS_PORT else 6379
except Exception:
    REDIS_PORT = 6379

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
logging.info(f"redis-client created at {REDIS_HOST}:{REDIS_PORT}")
print(f"redis-client created at {REDIS_HOST}:{REDIS_PORT}")

app = FastAPI(strict_slashes=False)

# CORS — allow your real site to talk to this service with credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://iamcalledned.ai"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session middleware (used by your login flow to stash things)
SESSION_SECRET_KEY = Config.SESSION_SECRET_KEY or os.urandom(24).hex()
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

# ------------------------------ Startup ------------------------------

@app.on_event("startup")
async def startup():
    app.state.pool = await create_db_pool()
    logging.info("Database pool created")
    print(f"Database pool created: {app.state.pool}")
    asyncio.create_task(schedule_verifier_cleanup(app.state.pool, redis_client))

async def schedule_verifier_cleanup(pool, redis_client):
    while True:
        try:
            acquired = redis_client.set("verifier_cleanup_lock", "true", nx=True, ex=60)
        except Exception as e:
            logging.error(f"Error acquiring verifier cleanup lock: {e}")
            acquired = False

        if acquired:
            try:
                await delete_old_verifiers(pool)
            except Exception as e:
                logging.error(f"Error deleting old verifiers: {e}")

        await asyncio.sleep(600)

# ------------------------------ Routes ------------------------------

@app.get("/api/login")
async def login(request: Request):
    print("--- In /api/login ---")
    login_timestamp  = datetime.datetime.now()
    client_ip = request.client.host

    # PKCE
    try:
        code_verifier, code_challenge = await generate_code_verifier_and_challenge()
    except Exception as e:
        logging.error(f"Error generating code verifier and challenge: {e}")
        raise HTTPException(500, "Unable to start login")

    # State + optional next
    state = os.urandom(24).hex()
    next_param = request.query_params.get('next')
    logging.info(f"LOGIN start state={state} ip={client_ip}")
    logging.info(f"PKCE challenge (S256) for state={state}: {code_challenge[:16]}...")
    logging.info(f"PKCE verifier fp state={state}: {hashlib.sha256(code_verifier.encode()).hexdigest()[:16]}")

    allowed_paths = ['/scanner', '/overview']
    if next_param and next_param not in allowed_paths:
        logging.warning(f"Requested next param not allowed: {next_param}")
        next_param = None

    try:
        if next_param:
            await save_code_verifier_with_return(app.state.pool, state, code_verifier, client_ip, login_timestamp, next_param)
        else:
            await save_code_verifier(app.state.pool, state, code_verifier, client_ip, login_timestamp)
    except Exception as e:
        logging.error(f"Error saving code verifier: {e}")
        raise HTTPException(500, "Unable to start login")

    cognito_login_url = (
        f"{Config.COGNITO_DOMAIN}/oauth2/authorize?response_type=code&client_id={Config.COGNITO_APP_CLIENT_ID}"
        f"&redirect_uri={Config.REDIRECT_URI}&state={state}&code_challenge={code_challenge}"
        f"&code_challenge_method=S256&prompt=login"
    )
    print(f"Redirecting to Cognito login URL: {cognito_login_url}")
    return RedirectResponse(cognito_login_url)

@app.get("/callback")
async def callback(request: Request, code: str, state: str):
    print("--- In /callback ---")

    xff = request.headers.get('x-forwarded-for')
    client_ip = xff.split(',')[0].strip() if xff else request.client.host
    print(f"Client IP: {client_ip}")

    if not code:
        raise HTTPException(status_code=400, detail="Code parameter is missing")

    verifier = await get_verifier(app.state.pool, state)
    if not verifier:
        raise HTTPException(status_code=400, detail="Invalid state or code_verifier missing")

    code_verifier = verifier.get('code_verifier')
    return_to = verifier.get('return_to') or '/scanner'

    try:
        await delete_code_verifier(app.state.pool, state)
    except Exception as e:
        logging.error(f"Error deleting code verifier: {e}")

    try:
        tokens = await exchange_code_for_token(code, code_verifier)
    except Exception as e:
        logging.error(f"Error exchanging code for token: {e}")
        tokens = None

    print(f"Tokens received: {tokens}")

    if not tokens:
        return JSONResponse({"error": "Token exchange failed"}, status_code=400)

    id_token = tokens.get('id_token')
    try:
        decoded_token = await validate_token(id_token)
    except Exception as e:
        logging.error(f"Error validating token: {e}")
        return JSONResponse({"error": "Invalid token"}, status_code=400)

    # Build session, store in Redis
    session = request.session
    session['email'] = decoded_token.get('email', 'unknown')
    session['username'] = decoded_token.get('cognito:username', 'unknown')
    session['name'] = decoded_token.get('name', 'unknown')
    session['session_id'] = os.urandom(24).hex()

    try:
        await save_user_info_to_userdata(app.state.pool, session)
    except Exception as e:
        logging.error(f"Error saving user information to userdata: {e}")

    session_id = session['session_id']
    session_data = {
        'email': session['email'],
        'username': session['username'],
        'name': session['name'],
        'session_id': session_id,
    }

    try:
        redis_client.set(session_id, json.dumps(session_data), ex=3600)
    except Exception as e:
        logging.error(f"Error saving session data to Redis: {e}")

    logging.info(f"CALLBACK state={state} code_len={len(code)} ip={client_ip}")
    logging.info(f"Fetched verifier fp state={state}: {hashlib.sha256(code_verifier.encode()).hexdigest()[:16]}")

    # Set first-party cookie visible to all subdomains under iamcalledned.ai, then go to the real site
    resp = RedirectResponse(url=f"https://iamcalledned.ai{return_to}", status_code=302)
    resp.set_cookie(
        key="scanner_session",
        value=session_id,
        max_age=3600,           # keep aligned with Redis ex
        httponly=True,
        secure=True,            # site must be HTTPS
        samesite="None",        # cross-site redirect requires None + Secure
        domain=".iamcalledned.ai",
        path="/"
    )
    return resp

# Optional: provide a FastAPI /api/me for safety (your pages should hit Flask’s /scanner/api/me)
@app.get("/api/me")
async def api_me(request: Request):
    session_cookie = request.cookies.get("scanner_session")
    if not session_cookie:
        return JSONResponse({"authenticated": False}, 200)

    try:
        raw = redis_client.get(session_cookie)
        if not raw:
            return JSONResponse({"authenticated": False}, 200)

        session_data = json.loads(raw)
        user = {
            "username": session_data.get("username"),
            "email":    session_data.get("email"),
            "name":     session_data.get("name"),
        }
        return JSONResponse({"authenticated": True, "user": user}, 200)
    except Exception as e:
        logging.error(f"/api/me error: {e}")
        return JSONResponse({"authenticated": False}, 200)

@app.get("/get_session_data")
async def get_session_data(request: Request):
    """
    Return session data stored in Redis for a session id.
    Session id is read in this order: server-side session, x-session-id header, query param `session_id`.
    """
    session_id = request.session.get('session_id') or request.headers.get('x-session-id') or request.query_params.get('session_id')
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID not provided")

    try:
        raw = redis_client.get(session_id)
        if not raw:
            raise HTTPException(status_code=404, detail="Session not found")
        session_data = json.loads(raw)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error reading session from Redis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    username = session_data.get('username')
    nonce = session_data.get('nonce') or None

    return JSONResponse(content={
        "sessionId": session_id,
        "nonce": nonce,
        "userInfo": username,
        "session": session_data
    })

@app.post("/api/logout")
async def logout(request: Request):
    session_id = None
    try:
        body = await request.json()
        session_id = body.get("session_id")
    except Exception:
        pass

    if not session_id:
        session_id = request.headers.get('x-session-id') or request.query_params.get('session_id')

    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID not provided")

    try:
        deleted_count = redis_client.delete(session_id)
        if deleted_count > 0:
            logging.info(f"Session {session_id} deleted from Redis.")
            return JSONResponse(content={"message": "Logout successful"}, status_code=200)
        else:
            logging.warning(f"Session {session_id} not found or expired during logout.")
            return JSONResponse(content={"message": "Session not found or already expired"}, status_code=404)
    except Exception as e:
        logging.error(f"Error deleting session {session_id} from Redis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during logout")

@app.get("/api/status2")
async def server_status2():
    try:
        return JSONResponse(content={"status": "ok"}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

# ------------------------------ Helpers ------------------------------

async def exchange_code_for_token(code, code_verifier):
    print("--- In exchange_code_for_token ---")
    token_url = f"{Config.COGNITO_DOMAIN}/oauth2/token"

    # Base headers (form post)
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    # Common form fields for Authorization Code + PKCE
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': Config.REDIRECT_URI,   # MUST exactly match what you used in /authorize
        'code_verifier': code_verifier         # MUST match the challenge from /authorize
    }

    # Decide client authentication mode based on whether you actually have a secret
    client_secret = (getattr(Config, "COGNITO_CLIENT_SECRET", None) or "").strip()
    if client_secret:
        # CONFIDENTIAL client: use Basic auth (client_id:client_secret)
        auth_str = f"{Config.COGNITO_APP_CLIENT_ID}:{client_secret}"
        auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
        headers['Authorization'] = f'Basic {auth_b64}'
        # Do NOT send client_id in body when using Basic (Cognito tolerates it sometimes, but keep it clean)
    else:
        # PUBLIC client: NO Authorization header; send client_id in the body
        data['client_id'] = Config.COGNITO_APP_CLIENT_ID

    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, headers=headers, data=data)

    if response.status_code == 200:
        return response.json()

    # Better diagnostics to see the real cause
    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text}

    logging.error("Token exchange failed",
                  extra={"status": response.status_code, "body": body})
    print(f"Failed to exchange code. Status={response.status_code} Body={body}")
    return None

async def validate_token(id_token):
    COGNITO_USER_POOL_ID = Config.COGNITO_USER_POOL_ID
    COGNITO_APP_CLIENT_ID = Config.COGNITO_APP_CLIENT_ID
    jwks_url = f"https://cognito-idp.{Config.COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    with httpx.Client() as client:
        jwks_response = client.get(jwks_url)
    jwks = jwks_response.json()

    headers = jwt.get_unverified_header(id_token)
    kid = headers['kid']
    key = [k for k in jwks['keys'] if k['kid'] == kid][0]
    pem = RSAAlgorithm.from_jwk(json.dumps(key))

    decoded_token = jwt.decode(
        id_token,
        pem,
        algorithms=['RS256'],
        audience=COGNITO_APP_CLIENT_ID
    )
    return decoded_token

# ------------------------------ Main ------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
