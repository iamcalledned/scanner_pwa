Cognito setup notes

1) Domain
- Create or configure Cognito Hosted UI domain in the Console. Note the full domain, e.g.
  https://your-cognito-domain-prefix.auth.us-east-1.amazoncognito.com

2) App client and redirect URI
- Create an App client (or configure existing) and add the callback/redirect URI exactly as:
  https://iamcalledned.ai/callback
  (or https://iamcalledned.ai/scanner/callback if you prefer; this implementation will redirect to /scanner)

3) Allowed sign-out URL
- Add a sign-out URL such as https://iamcalledned.ai/

4) OAuth settings
- Enable Authorization code grant and PKCE (S256).
- Scopes: openid, profile, email (as needed)

5) Region
- Note your AWS region (e.g., us-east-1). Put this in the app's `COGNITO_REGION` env var.

6) Example AWS CLI to create an app client (replace placeholders):

aws cognito-idp create-user-pool-client \
  --user-pool-id <your_pool_id> \
  --client-name my-scanner-client \
  --generate-secret false \
  --allowed-oauth-flows-code
  --allowed-oauth-flows authorization_code \
  --allowed-oauth-scopes openid email profile \
  --callback-urls https://iamcalledned.ai/callback \
  --logout-urls https://iamcalledned.ai/ \
  --allowed-oauth-flows-user-pool-client

(Adjust options per your policy)

7) Cloudflare
- Make sure Cloudflare forwards the full callback path and the query parameters `code` and `state`.
- App reads `X-Forwarded-For` to obtain client IP.

8) Testing
- Start app and visit: /api/login?next=/scanner
- Complete Cognito login, confirm redirect to /scanner and that localStorage `session_id` is set.

