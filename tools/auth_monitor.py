#!/usr/bin/env python3
"""
Auth Monitor - Checks OpenClaw auth profile status and alerts on issues.

Checks:
1. If OAuth profile is in cooldown (means it failed)
2. If OAuth token is about to expire (< 2 hours)
3. If currently using API key instead of OAuth

Usage:
    python auth_monitor.py              # Check and print status
    python auth_monitor.py --alert      # Check and return alert message if issues
    python auth_monitor.py --json       # Output JSON status
"""

import json
import sys
from pathlib import Path
from datetime import datetime

AUTH_PROFILES_PATH = Path("/root/.openclaw/agents/main/agent/auth-profiles.json")
ALERT_THRESHOLD_HOURS = 0.5  # Alert only if token expires within 30 min (refresh token auto-renews)


def load_auth_profiles():
    """Load the auth profiles JSON file."""
    if not AUTH_PROFILES_PATH.exists():
        return None
    with open(AUTH_PROFILES_PATH) as f:
        return json.load(f)


def check_auth_status():
    """Check auth status and return issues."""
    issues = []
    warnings = []
    
    profiles = load_auth_profiles()
    if not profiles:
        issues.append("Auth profiles file not found!")
        return {"issues": issues, "warnings": warnings, "status": "error", "oauth_expires_in_hours": None}
    
    oauth_profile = profiles.get("profiles", {}).get("anthropic:oauth")
    api_key_profile = profiles.get("profiles", {}).get("anthropic:api-key")
    usage_stats = profiles.get("usageStats", {})
    last_good = profiles.get("lastGood", {}).get("anthropic")
    
    expires_in_hours = None
    
    # Check if OAuth profile exists
    if not oauth_profile:
        issues.append("OAuth profile not configured!")
    else:
        # Check if OAuth token is expired or expiring soon
        expires = oauth_profile.get("expires", 0)
        now = datetime.now().timestamp() * 1000  # Convert to ms
        expires_in_hours = (expires - now) / (1000 * 60 * 60)
        
        if expires_in_hours < 0:
            issues.append(f"OAuth token EXPIRED {abs(expires_in_hours):.1f} hours ago!")
        elif expires_in_hours < ALERT_THRESHOLD_HOURS:
            warnings.append(f"OAuth token expires in {expires_in_hours:.1f} hours")
        
        # Check if OAuth is in cooldown
        oauth_stats = usage_stats.get("anthropic:oauth", {})
        cooldown_until = oauth_stats.get("cooldownUntil", 0)
        if cooldown_until > now:
            cooldown_remaining = (cooldown_until - now) / (1000 * 60)
            issues.append(f"OAuth profile in COOLDOWN for {cooldown_remaining:.0f} more minutes")
        
        # Check error count
        error_count = oauth_stats.get("errorCount", 0)
        if error_count > 0:
            warnings.append(f"OAuth profile has {error_count} recent errors")
    
    # Check if API key was the last successful profile
    # NOTE: lastGood is historical - use session_status for real-time current profile
    if last_good == "anthropic:api-key":
        warnings.append("Last successful auth was API key (gateway may have switched back to OAuth since)")
    
    # Check API key profile exists (backup)
    if not api_key_profile:
        warnings.append("No API key backup configured")
    
    # Determine overall status
    if issues:
        status = "critical" if any("EXPIRED" in i or "COOLDOWN" in i or "API KEY" in i for i in issues) else "warning"
    elif warnings:
        status = "warning"
    else:
        status = "ok"
    
    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "current_profile": last_good,
        "oauth_expires_in_hours": expires_in_hours
    }


def format_alert(result):
    """Format result as an alert message."""
    if result["status"] == "ok":
        return None
    
    lines = ["⚠️ **Auth Alert**"]
    
    if result["issues"]:
        lines.append("")
        lines.append("**Issues:**")
        for issue in result["issues"]:
            lines.append(f"• {issue}")
    
    if result["warnings"]:
        lines.append("")
        lines.append("**Warnings:**")
        for warning in result["warnings"]:
            lines.append(f"• {warning}")
    
    lines.append("")
    lines.append(f"Current profile: `{result.get('current_profile', 'unknown')}`")
    
    if result.get("oauth_expires_in_hours") is not None:
        lines.append(f"OAuth expires in: {result['oauth_expires_in_hours']:.1f} hours")
    
    lines.append("")
    lines.append("**To fix OAuth:**")
    lines.append("```")
    lines.append("claude setup-token")
    lines.append("openclaw models auth paste-token --provider anthropic")
    lines.append("```")
    
    return "\n".join(lines)


def main():
    alert_mode = "--alert" in sys.argv
    json_mode = "--json" in sys.argv
    
    result = check_auth_status()
    
    if json_mode:
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["status"] == "ok" else 1)
    
    if alert_mode:
        alert = format_alert(result)
        if alert:
            print(alert)
            sys.exit(1)  # Non-zero exit for issues
        else:
            print("AUTH_OK")  # Clear signal that everything is fine
            sys.exit(0)
    else:
        # Print full status
        print(f"Status: {result['status']}")
        print(f"Current profile: {result.get('current_profile', 'unknown')}")
        
        if result.get("oauth_expires_in_hours") is not None:
            print(f"OAuth expires in: {result['oauth_expires_in_hours']:.1f} hours")
        
        if result["issues"]:
            print("\nIssues:")
            for issue in result["issues"]:
                print(f"  ❌ {issue}")
        
        if result["warnings"]:
            print("\nWarnings:")
            for warning in result["warnings"]:
                print(f"  ⚠️ {warning}")
        
        if result["status"] == "ok":
            print("\n✅ All auth checks passed")


if __name__ == "__main__":
    main()
