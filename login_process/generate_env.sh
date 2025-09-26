#!/usr/bin/env bash
set -euo pipefail

# Simple env generator for login_process
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT_DIR/.env"
DB_DIR="/home/ned/data/login"
DB_FILE="$DB_DIR/login.sqlite3"

echo "Creating DB directory: $DB_DIR"
mkdir -p "$DB_DIR"

if [ ! -f "$DB_FILE" ]; then
  echo "Creating empty sqlite DB file: $DB_FILE"
  touch "$DB_FILE"
fi

cat > "$ENV_FILE" <<EOF
# Generated .env for login_process
FLASK_SECRET_KEY="$(head -c 24 /dev/urandom | base64)"
SESSION_SECRET_KEY="$(head -c 24 /dev/urandom | base64)"

COGNITO_DOMAIN="https://your-cognito-domain.auth.us-east-1.amazoncognito.com"
COGNITO_USER_POOL_ID="us-east-1_XXXXXXXXX"
COGNITO_APP_CLIENT_ID="XXXXXXXXXXXXXXXXXXXX"
COGNITO_REGION="us-east-1"
REDIRECT_URI="https://iamcalledned.ai/callback"

REDIS_HOST="localhost"
REDIS_PORT="6379"

DB_PATH="$DB_FILE"

LOG_PATH="$ROOT_DIR/login_process.log"
LOG_PATH_PROCESS_HANDLER="$ROOT_DIR/login_process_handler.log"

DB_HOST="localhost"
DB_PORT=3306
DB_USER=""
DB_PASSWORD=""
DB_NAME=""

OPENAI_API_KEY=""
ANOTHER_APP_URI=""
ASSISTANT_ID=""
EOF

chmod 600 "$ENV_FILE"

echo "Wrote $ENV_FILE"
