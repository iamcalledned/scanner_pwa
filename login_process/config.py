import os
from dotenv import load_dotenv

# Specify the path to your .env file

# Load environment variables from the specified .env file
load_dotenv()

class Config:
    FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')
    COGNITO_USER_POOL_ID = os.getenv('COGNITO_USER_POOL_ID')
    COGNITO_APP_CLIENT_ID = os.getenv('COGNITO_APP_CLIENT_ID')
    COGNITO_CLIENT_SECRET = os.getenv('COGNITO_CLIENT_SECRET')
    COGNITO_DOMAIN = os.getenv('COGNITO_DOMAIN')
    REDIRECT_URI = os.getenv('REDIRECT_URI')
    ANOTHER_APP_URI = os.getenv('ANOTHER_APP_URI')
    REDIS_HOST = os.getenv('REDIS_HOST')
    REDIS_PORT = os.getenv('REDIS_PORT')
    ASSISTANT_ID = os.getenv('ASSISTANT_ID')
    # Path to SQLite file. Use env var DB_PATH or default to a local file under the project.
    DB_PATH = os.getenv('DB_PATH', os.path.join(os.getcwd(), 'login.sqlite3'))
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    LOG_PATH = os.getenv('LOG_PATH')
    DB_HOST = os.getenv('DB_HOST')
    DB_PORT = int(os.getenv('DB_PORT', 3306))  # Default MySQL port is 3306
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_NAME = os.getenv('DB_NAME')
    SESSION_SECRET_KEY = os.getenv('SESSION_SECRET_KEY')
    LOG_PATH_PROCESS_HANDLER = os.getenv('LOG_PATH_PROCESS_HANDLER')
    # Optional: AWS Cognito region (used to fetch JWKS). Default to us-east-1 if not provided.
    COGNITO_REGION = os.getenv('COGNITO_REGION', 'us-east-1')