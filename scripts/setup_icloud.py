#!/usr/bin/env python3
"""
Setup iCloud email and calendar access for ATLAS.

Usage:
    python setup_icloud.py --email user@icloud.com --password "app-specific-password"
"""
import os
import argparse
from pathlib import Path

HIMALAYA_CONFIG = """
[accounts.icloud]
email = "{email}"
display-name = "Matt"
default = true

backend.type = "imap"
backend.host = "imap.mail.me.com"
backend.port = 993
backend.encryption.type = "tls"
backend.login = "{email}"
backend.auth.type = "password"
backend.auth.raw = "{password}"

message.send.backend.type = "smtp"
message.send.backend.host = "smtp.mail.me.com"
message.send.backend.port = 587
message.send.backend.encryption.type = "start-tls"
message.send.backend.login = "{email}"
message.send.backend.auth.type = "password"
message.send.backend.auth.raw = "{password}"

[accounts.icloud.folder.alias]
inbox = "INBOX"
sent = "Sent Messages"
drafts = "Drafts"
trash = "Deleted Messages"
"""


def setup_himalaya(email: str, password: str):
    """Configure himalaya for iCloud email."""
    config_dir = Path.home() / ".config" / "himalaya"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    config_path = config_dir / "config.toml"
    config = HIMALAYA_CONFIG.format(email=email, password=password)
    
    config_path.write_text(config)
    os.chmod(config_path, 0o600)  # Restrict permissions
    
    print(f"✅ Himalaya configured at {config_path}")
    return config_path


def test_email_connection():
    """Test the email connection."""
    import subprocess
    result = subprocess.run(
        ["himalaya", "folder", "list"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("✅ Email connection successful!")
        print(result.stdout)
    else:
        print("❌ Email connection failed:")
        print(result.stderr)


def setup_caldav(email: str, password: str):
    """Test CalDAV connection to iCloud."""
    try:
        import caldav
        
        url = "https://caldav.icloud.com/"
        client = caldav.DAVClient(
            url=url,
            username=email,
            password=password
        )
        
        principal = client.principal()
        calendars = principal.calendars()
        
        print(f"✅ CalDAV connection successful!")
        print(f"   Found {len(calendars)} calendars:")
        for cal in calendars:
            print(f"   - {cal.name}")
            
        return True
    except Exception as e:
        print(f"❌ CalDAV connection failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Setup iCloud access for ATLAS")
    parser.add_argument("--email", required=True, help="iCloud email address")
    parser.add_argument("--password", required=True, help="App-specific password")
    parser.add_argument("--test", action="store_true", help="Test connections after setup")
    
    args = parser.parse_args()
    
    print("🔧 Setting up iCloud access...\n")
    
    # Setup email
    setup_himalaya(args.email, args.password)
    
    if args.test:
        print("\n📧 Testing email connection...")
        test_email_connection()
        
        print("\n📅 Testing calendar connection...")
        setup_caldav(args.email, args.password)


if __name__ == "__main__":
    main()
