#!/usr/bin/env python3
"""
OAuth Refresh Tool - Proactively refresh Anthropic OAuth tokens.

This can be run periodically to ensure tokens don't expire unexpectedly.
OpenClaw's built-in refresh should handle this, but this provides a backup
and allows manual refresh when needed.

Usage:
    python oauth_refresh.py           # Check status, refresh if needed
    python oauth_refresh.py --force   # Force refresh even if not expired
    python oauth_refresh.py --check   # Just check status, don't refresh
"""

import json
import sys
import requests
from datetime import datetime
from pathlib import Path

AUTH_PROFILES_PATH = Path("/root/.openclaw/agents/main/agent/auth-profiles.json")
CLAUDE_CREDS_PATH = Path("/root/.claude/.credentials.json")

# Anthropic OAuth constants (from pi-ai source)
CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
TOKEN_URL = "https://console.anthropic.com/v1/oauth/token"

# Refresh when less than this many hours remain
REFRESH_THRESHOLD_HOURS = 2


def load_auth_profiles():
    if not AUTH_PROFILES_PATH.exists():
        return None
    with open(AUTH_PROFILES_PATH) as f:
        return json.load(f)


def save_auth_profiles(data):
    with open(AUTH_PROFILES_PATH, 'w') as f:
        json.dump(data, f, indent=2)


def load_claude_creds():
    if not CLAUDE_CREDS_PATH.exists():
        return None
    with open(CLAUDE_CREDS_PATH) as f:
        return json.load(f)


def save_claude_creds(data):
    with open(CLAUDE_CREDS_PATH, 'w') as f:
        json.dump(data, f, indent=2)


def refresh_token(refresh_token_value):
    """Call Anthropic's OAuth refresh endpoint."""
    response = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/json"},
        json={
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": refresh_token_value
        }
    )
    
    if not response.ok:
        raise Exception(f"Refresh failed: {response.status_code} - {response.text}")
    
    data = response.json()
    
    if "access_token" not in data:
        raise Exception(f"No access_token in response: {data}")
    
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_in": data["expires_in"],
        "expires_at": int((datetime.now().timestamp() + data["expires_in"]) * 1000)
    }


def check_and_refresh(force=False, check_only=False):
    """Check OAuth status and refresh if needed."""
    auth = load_auth_profiles()
    if not auth:
        print("ERROR: No auth profiles found")
        return False
    
    oauth_profile = auth.get("profiles", {}).get("anthropic:oauth")
    if not oauth_profile:
        print("ERROR: No OAuth profile configured")
        return False
    
    if oauth_profile.get("type") != "oauth":
        print("ERROR: Profile is not OAuth type")
        return False
    
    # Check expiry
    expires = oauth_profile.get("expires", 0)
    now = datetime.now().timestamp() * 1000
    expires_in_hours = (expires - now) / (1000 * 60 * 60)
    
    print(f"Current status:")
    print(f"  Access token: {oauth_profile.get('access', '')[:30]}...")
    print(f"  Refresh token: {oauth_profile.get('refresh', '')[:30]}...")
    print(f"  Expires in: {expires_in_hours:.1f} hours")
    
    if expires_in_hours < 0:
        print(f"  ⚠️ Token EXPIRED {abs(expires_in_hours):.1f} hours ago")
    elif expires_in_hours < REFRESH_THRESHOLD_HOURS:
        print(f"  ⚠️ Token expires soon (< {REFRESH_THRESHOLD_HOURS}h threshold)")
    else:
        print(f"  ✅ Token valid")
    
    needs_refresh = force or expires_in_hours < REFRESH_THRESHOLD_HOURS
    
    if check_only:
        return expires_in_hours > 0
    
    if not needs_refresh:
        print("\nNo refresh needed.")
        return True
    
    # Get refresh token (prefer Claude CLI creds if fresher)
    refresh_token_value = oauth_profile.get("refresh")
    claude_creds = load_claude_creds()
    if claude_creds and "claudeAiOauth" in claude_creds:
        claude_refresh = claude_creds["claudeAiOauth"].get("refreshToken")
        if claude_refresh:
            refresh_token_value = claude_refresh
            print("\nUsing refresh token from Claude CLI credentials")
    
    if not refresh_token_value:
        print("\nERROR: No refresh token available")
        return False
    
    print(f"\nRefreshing token...")
    try:
        new_creds = refresh_token(refresh_token_value)
        print(f"✅ Refresh successful!")
        print(f"  New access token: {new_creds['access_token'][:30]}...")
        print(f"  New refresh token: {new_creds['refresh_token'][:30]}...")
        print(f"  Expires in: {new_creds['expires_in'] / 3600:.1f} hours")
        
        # Update auth-profiles.json
        auth["profiles"]["anthropic:oauth"] = {
            "type": "oauth",
            "provider": "anthropic",
            "access": new_creds["access_token"],
            "refresh": new_creds["refresh_token"],
            "expires": new_creds["expires_at"]
        }
        save_auth_profiles(auth)
        print("  Updated auth-profiles.json")
        
        # Also update Claude CLI credentials (so they stay in sync)
        if claude_creds and "claudeAiOauth" in claude_creds:
            claude_creds["claudeAiOauth"]["accessToken"] = new_creds["access_token"]
            claude_creds["claudeAiOauth"]["refreshToken"] = new_creds["refresh_token"]
            claude_creds["claudeAiOauth"]["expiresAt"] = new_creds["expires_at"]
            save_claude_creds(claude_creds)
            print("  Updated Claude CLI credentials")
        
        return True
        
    except Exception as e:
        print(f"❌ Refresh failed: {e}")
        return False


def main():
    force = "--force" in sys.argv
    check_only = "--check" in sys.argv
    
    success = check_and_refresh(force=force, check_only=check_only)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
