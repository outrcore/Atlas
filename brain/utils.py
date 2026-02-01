"""
Brain utilities - helper functions.
"""
import os
import json
from pathlib import Path
from typing import Optional


def get_anthropic_api_key() -> Optional[str]:
    """
    Get Anthropic API key from environment or stored key file.
    
    Checks:
    1. ANTHROPIC_API_KEY environment variable
    2. Brain's stored API key file
    3. OpenClaw auth profiles (OAuth tokens - less reliable for direct API)
    
    Returns:
        API key string or None if not found
    """
    # Check environment first
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key and key.startswith("sk-ant-api"):  # Real API key, not OAuth
        return key
        
    # Check brain's stored key file
    key_file = Path("/workspace/clawd/brain_data/.anthropic_key")
    if key_file.exists():
        try:
            key = key_file.read_text().strip()
            if key.startswith("sk-ant-api"):
                return key
        except Exception:
            pass
    
    # Check OpenClaw auth profiles (may be OAuth tokens)
    auth_file = Path("/root/.openclaw/agents/main/agent/auth-profiles.json")
    if auth_file.exists():
        try:
            data = json.loads(auth_file.read_text())
            profiles = data.get("profiles", {})
            
            # Look for real API keys (api format, not oat format)
            for name, profile in profiles.items():
                token = profile.get("token", "")
                if token.startswith("sk-ant-api"):
                    return token
                    
        except Exception:
            pass
            
    return None


def get_openai_api_key() -> Optional[str]:
    """Get OpenAI API key from environment or config."""
    return os.environ.get("OPENAI_API_KEY")


def ensure_api_key():
    """
    Ensure ANTHROPIC_API_KEY is set in environment.
    Call this before running brain operations that need the API.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        key = get_anthropic_api_key()
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key
            return True
    return bool(os.environ.get("ANTHROPIC_API_KEY"))
