#!/usr/bin/env python3
"""Step 1: Generate OAuth URL and save PKCE verifier."""

import secrets
import hashlib
import base64
import json
from urllib.parse import urlencode

CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
REDIRECT_URI = "https://platform.claude.com/oauth/code/callback"
PKCE_FILE = "/tmp/claude_pkce.json"

def generate_pkce():
    code_verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
    return code_verifier, code_challenge

def generate_state():
    return secrets.token_urlsafe(32)

# Generate
code_verifier, code_challenge = generate_pkce()
state = generate_state()

# Save verifier for step 2
with open(PKCE_FILE, 'w') as f:
    json.dump({"code_verifier": code_verifier, "state": state}, f)

# Build URL
params = {
    "code": "true",
    "client_id": CLIENT_ID,
    "response_type": "code",
    "redirect_uri": REDIRECT_URI,
    "scope": "user:inference",
    "code_challenge": code_challenge,
    "code_challenge_method": "S256",
    "state": state
}
url = f"https://claude.ai/oauth/authorize?{urlencode(params)}"

print(url)
