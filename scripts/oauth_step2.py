#!/usr/bin/env python3
"""Step 2: Exchange code for token using saved PKCE verifier."""

import json
import sys
import requests

CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
REDIRECT_URI = "https://platform.claude.com/oauth/code/callback"
TOKEN_URL = "https://claude.ai/api/oauth/token"
PKCE_FILE = "/tmp/claude_pkce.json"
CREDS_FILE = "/root/.claude/credentials.json"

if len(sys.argv) < 2:
    print("Usage: oauth_step2.py <authorization_code>")
    sys.exit(1)

code = sys.argv[1]

# Load verifier
with open(PKCE_FILE) as f:
    pkce_data = json.load(f)
code_verifier = pkce_data["code_verifier"]

print(f"Code: {code[:20]}...")
print(f"Verifier: {code_verifier[:20]}...")
print()

# Exchange
data = {
    "grant_type": "authorization_code",
    "code": code,
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "code_verifier": code_verifier
}

response = requests.post(TOKEN_URL, data=data)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:500]}")

if response.status_code == 200:
    token_data = response.json()
    access_token = token_data.get("access_token")
    
    if access_token:
        creds = {"claudeAiOauth": {"accessToken": access_token, "expiresAt": token_data.get("expires_at")}}
        with open(CREDS_FILE, 'w') as f:
            json.dump(creds, f, indent=2)
        print(f"\n✅ SUCCESS! Saved to {CREDS_FILE}")
    else:
        print("\n❌ No access_token in response")
else:
    print("\n❌ Token exchange failed")
