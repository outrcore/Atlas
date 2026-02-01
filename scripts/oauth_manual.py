#!/usr/bin/env python3
"""
Manual OAuth token exchange for Claude Code.
Bypasses the claude setup-token terminal issues.
"""

import secrets
import hashlib
import base64
import json
import sys
from urllib.parse import urlencode
import requests

CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
REDIRECT_URI = "https://platform.claude.com/oauth/code/callback"
TOKEN_URL = "https://claude.ai/api/oauth/token"
CREDS_FILE = "/root/.claude/credentials.json"

def generate_pkce():
    """Generate PKCE code_verifier and code_challenge."""
    code_verifier = secrets.token_urlsafe(32)
    
    # S256 challenge
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
    
    return code_verifier, code_challenge

def generate_state():
    """Generate random state parameter."""
    return secrets.token_urlsafe(32)

def build_auth_url(code_challenge, state):
    """Build the OAuth authorization URL."""
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
    return f"https://claude.ai/oauth/authorize?{urlencode(params)}"

def exchange_code(code, code_verifier):
    """Exchange authorization code for access token."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    response = requests.post(TOKEN_URL, data=data, headers=headers)
    return response

def save_credentials(access_token, expires_at=None):
    """Save credentials to Claude config file."""
    creds = {
        "claudeAiOauth": {
            "accessToken": access_token,
            "expiresAt": expires_at
        }
    }
    
    with open(CREDS_FILE, 'w') as f:
        json.dump(creds, f, indent=2)
    
    print(f"✅ Credentials saved to {CREDS_FILE}")

def main():
    # Generate PKCE parameters
    code_verifier, code_challenge = generate_pkce()
    state = generate_state()
    
    # Build and display URL
    auth_url = build_auth_url(code_challenge, state)
    
    print("=" * 60)
    print("🔐 Manual OAuth Flow for Claude Code")
    print("=" * 60)
    print()
    print("1. Open this URL in your browser:")
    print()
    print(auth_url)
    print()
    print(f"2. After authorizing, copy the 'code' parameter from the redirect URL")
    print(f"   (The URL will look like: {REDIRECT_URI}?code=XXXXX&state=...)")
    print()
    print("3. Enter the code below:")
    print()
    
    # Store verifier for later
    print(f"[PKCE verifier stored: {code_verifier[:20]}...]")
    print()
    
    # Read code from stdin or argument
    if len(sys.argv) > 1:
        code = sys.argv[1]
        print(f"Using code from argument: {code[:20]}...")
    else:
        code = input("Code: ").strip()
    
    print()
    print("🔄 Exchanging code for token...")
    
    response = exchange_code(code, code_verifier)
    
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text[:500]}")
    
    if response.status_code == 200:
        data = response.json()
        access_token = data.get("access_token")
        expires_at = data.get("expires_at")
        
        if access_token:
            save_credentials(access_token, expires_at)
            print()
            print("🎉 SUCCESS! Claude Code should now be authenticated.")
        else:
            print("❌ No access token in response")
    else:
        print(f"❌ Token exchange failed: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    main()
