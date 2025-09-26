from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from starlette.requests import Request


import os
import base64
import hashlib
import httpx
import jwt
import datetime
import json
import time


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
import logging
import asyncio

from fastapi.responses import HTMLResponse



import redis

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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)




# Define session middleware. Prefer secret from environment/config when provided.
SESSION_SECRET_KEY = Config.SESSION_SECRET_KEY or os.urandom(24).hex()
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

#####!!!!  Startup   !!!!!!################
@app.on_event("startup")
async def startup():
    app.state.pool = await create_db_pool()  # No argument is passed here
    logging.info(f"Database pool created")
    print(f"Database pool created: {app.state.pool}")
    asyncio.create_task(schedule_verifier_cleanup(app.state.pool, redis_client))


#####!!!!  Startup   !!!!!!################

async def schedule_verifier_cleanup(pool, redis_client):
    while True:
        # Attempt to acquire the lock
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

        # Wait for 10 minutes before the next attempt
        await asyncio.sleep(600)


################################################################## 
######!!!!       Routes                !!!!!######################
##################################################################

################################################################## 
######!!!!     Start login endpoint    !!!!!######################
##################################################################

@app.get("/api/login")
async def login(request: Request):
    print("--- In /api/login ---")
    #set login timestemp
    login_timestamp  = datetime.datetime.now()


    # Getting the client's IP address
    client_ip = request.client.host
        
    #get code_verifier and code_challenge
    try:
        code_verifier, code_challenge = await generate_code_verifier_and_challenge()
    # Continue with your logic if the function succeeds
    except Exception as e:
        # Log the error and/or handle it appropriately
        logging.error(f"Error generating code verifier and challenge: {e}")
        print(f"Error generating code verifier and challenge: {e}")
        # Depending on your application's needs, you might want to return an error response, raise another exception, or take some other action.

    
    
    # generate a state code to link things later
    state = os.urandom(24).hex()  # Generate a random state value
    
    # Allow an optional `next` param so callers can request where to land after login.
    next_param = request.query_params.get('next')
    # Whitelist allowed return paths to prevent open redirect vulnerabilities.
    allowed_paths = ['/scanner', '/overview']
    if next_param and next_param not in allowed_paths:
        logging.warning(f"Requested next param not allowed: {next_param}")
        next_param = None

    try:
        # If a return_to path is provided, use the save function that stores it
        if next_param:
            await save_code_verifier_with_return(app.state.pool, state, code_verifier, client_ip, login_timestamp, next_param)
        else:
            await save_code_verifier(app.state.pool, state, code_verifier, client_ip, login_timestamp)
    except Exception as e:
        logging.error(f"Error saving code verifier: {e}")
        print(f"Error saving code verifier: {e}")
        
    
    cognito_login_url = (
        f"{Config.COGNITO_DOMAIN}/oauth2/authorize?response_type=code&client_id={Config.COGNITO_APP_CLIENT_ID}"
        f"&redirect_uri={Config.REDIRECT_URI}&state={state}&code_challenge={code_challenge}"
        f"&code_challenge_method=S256&prompt=login"
    )
    print(f"Redirecting to Cognito login URL: {cognito_login_url}")
    return RedirectResponse(cognito_login_url)

################################################################## 
######!!!!     End login endpoint      !!!!!######################
##################################################################

################################################################## 
######!!!!     Start callback  endpoint!!!!!######################
##################################################################

@app.get("/callback")
async def callback(request: Request, code: str, state: str):
    print("--- In /callback ---")

    # The 'code' and 'state' parameters are now injected by FastAPI directly from the query string.
    # The redundant extraction from request.query_params has been removed to avoid confusion.

    # Respect X-Forwarded-For when behind proxies (e.g., Cloudflare). Fall back to request.client.host
    xff = request.headers.get('x-forwarded-for')
    client_ip = xff.split(',')[0].strip() if xff else request.client.host
    print(f"Client IP: {client_ip}")
    
    if not code:
        raise HTTPException(status_code=400, detail="Code parameter is missing")

    # Retrieve the code_verifier using the state and get any stored return_to
    verifier = await get_verifier(app.state.pool, state)
    if not verifier:
        raise HTTPException(status_code=400, detail="Invalid state or code_verifier missing")
    code_verifier = verifier.get('code_verifier')
    return_to = verifier.get('return_to') or '/scanner'

    #delete the code verifier since we don't really need it anymore and it's risky
    try:
        await delete_code_verifier(app.state.pool, state)
    except Exception as e:
        logging.error(f"Error deleting code verifier: {e}")
        print(f"Error deleting code verifier: {e}")
    
    try:
        tokens = await exchange_code_for_token(code, code_verifier)
    except Exception as e:
        logging.error(f"Error exchanging code for token: {e}")
        print(f"Error exchanging code for token: {e}")
    print(f"Tokens received: {tokens}")
    if tokens:
        print(f"Exchanged code for tokens successfully.")
        id_token = tokens['id_token']
        try:
            decoded_token = await validate_token(id_token)
        except Exception as e:
            logging.error(f"Error validating token: {e}")
            print(f"Error validating token: {e}")

        # Retrieve session data
        session = request.session

        # Store user information in session
        session['email'] = decoded_token.get('email', 'unknown')
        session['username'] = decoded_token.get('cognito:username', 'unknown')
        session['name'] = decoded_token.get('name', 'unknown')
        session['session_id'] = os.urandom(24).hex()  # Generate a random state value

        #await save_user_info_to_mysql(app.state.pool, session, client_ip, state)
        try:
            await save_user_info_to_userdata(app.state.pool, session)
        except Exception as e:
            logging.error(f"Error saving user information to userdata: {e}")
            print(f"Error saving user information to userdata: {e}")

        session_id = session['session_id']
        try:
            session_data = {
            'email': decoded_token.get('email', 'unknown'),
            'username': decoded_token.get('cognito:username', 'unknown'),
            'name': decoded_token.get('name', 'unknown'),
            'session_id': session['session_id']
            }
        except Exception as e:
            logging.error(f"Error creating session data: {e}")
            print(f"Error creating session data: {e}")

        try:
            redis_client.set(session_id, json.dumps(session_data), ex=3600)  # ex is expiry time in seconds
        except Exception as e:
            logging.error(f"Error saving session data to Redis: {e}")
            print(f"Error saving session data to Redis: {e}")

        
        
        


        # Redirect to the scanner app's callback, which will set the session_id in localStorage
        # and then redirect to the final destination.
        scanner_callback_url = f"http://127.0.0.1:5005/scanner/callback?session_id={session['session_id']}&return_to={return_to}"
        return RedirectResponse(url=scanner_callback_url)

        # Redirect the user to the chatbot interface with query parameters
        #return RedirectResponse(url=redirect_url, status_code=302)
    else:
        return 'Error during token exchange.', 400
    

##################################################################
######!!!!     End callback endpoint   !!!!!######################
##################################################################


##################################################################
######!!!!     start get ssession endpoint!!######################
##################################################################

@app.get("/get_session_data")
async def get_session_data(request: Request):
    """Return session data stored in Redis for a session id.

    Session id is read in this order: server-side session, x-session-id header, query param `session_id`.
    """
    # Try server-side session first
    session_id = request.session.get('session_id')

    # Fall back to header or query param
    if not session_id:
        session_id = request.headers.get('x-session-id') or request.query_params.get('session_id')

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

    # Prepare return values
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
        # Try to get session_id from JSON body, for sendBeacon
        body = await request.json()
        session_id = body.get("session_id")
    except Exception:
        # Fallback for other request types
        pass

    if not session_id:
        # Fallback to header or query param
        session_id = request.headers.get('x-session-id') or request.query_params.get('session_id')

    if not session_id:
        # If still no session_id, it's a bad request
        raise HTTPException(status_code=400, detail="Session ID not provided")

    try:
        # Attempt to delete the session from Redis
        deleted_count = redis_client.delete(session_id)
        if deleted_count > 0:
            logging.info(f"Session {session_id} deleted from Redis.")
            return JSONResponse(content={"message": "Logout successful"}, status_code=200)
        else:
            # This is not an error, just a session that was already gone
            logging.warning(f"Session {session_id} not found in Redis during logout attempt.")
            return JSONResponse(content={"message": "Session not found or already expired"}, status_code=404)
    except Exception as e:
        logging.error(f"Error deleting session {session_id} from Redis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during logout")

@app.get("/api/status2")
async def server_status2():
    try:
        # Perform a lightweight check (e.g., return a success message)
        return JSONResponse(content={"status": "ok"}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)



##################################################################
######!!!!     end get ssession endpoint  !!######################
##################################################################

##################################################################
######!!!!     Start Functions           !!!!!####################
##################################################################

# exhange code for token
async def exchange_code_for_token(code, code_verifier):
    print("--- In exchange_code_for_token ---")
    token_url = f"{Config.COGNITO_DOMAIN}/oauth2/token"

    # Prepare auth header for confidential client
    auth_str = f"{Config.COGNITO_APP_CLIENT_ID}:{Config.COGNITO_CLIENT_SECRET}"
    auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {auth_b64}'
    }

    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': Config.REDIRECT_URI,
        'code_verifier': code_verifier
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json()
    else:
        error_details = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response.text,
        }
        logging.error(f"Failed to exchange code for token. Details: {json.dumps(error_details, indent=2)}")
        print(f"Failed to exchange code for token. Details: {json.dumps(error_details, indent=2)}")
        return None

# validate token info
async def validate_token(id_token):
    COGNITO_USER_POOL_ID = Config.COGNITO_USER_POOL_ID
    COGNITO_APP_CLIENT_ID = Config.COGNITO_APP_CLIENT_ID
    jwks_url = f"https://cognito-idp.{Config.COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    #jwks_response = requests.get(jwks_url)
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

######   Sessions

async def get_session(request: Request):
    return request.session






##################################################################


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
    #uvicorn process_handler:app --workers 4

# uvicorn process_handler:app --host 0.0.0.0 --port 8010

