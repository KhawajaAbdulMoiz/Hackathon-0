#!/usr/bin/env python3
"""
Re-authenticate Gmail with SEND permissions

Run this to get proper authentication for sending emails.
"""

import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

VAULT_ROOT = Path(__file__).parent.resolve()
CREDENTIALS_FILE = VAULT_ROOT / "client_secret_1005799766116-6oj47f92vtmaacrvrfm0dgocjrkv8ukr.apps.googleusercontent.com.json"
TOKEN_FILE = VAULT_ROOT / "token.json"

# Full scopes for sending emails
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.modify",
]

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def main():
    print("")
    print("=" * 60)
    print("  🔐 Gmail OAuth - SEND Permission Setup")
    print("=" * 60)
    print("")

    # Remove old token
    if TOKEN_FILE.exists():
        print("🗑️  Deleting old token with read-only scopes...")
        TOKEN_FILE.unlink()
        print("   Done!")
        print("")

    # Check credentials file
    if not CREDENTIALS_FILE.exists():
        print(f"❌ Credentials file not found: {CREDENTIALS_FILE}")
        sys.exit(1)

    print("📱 Starting OAuth flow...")
    print("   1. Browser will open")
    print("   2. Sign in with your Gmail account")
    print("   3. Click 'Continue' or 'Allow' on permission screen")
    print("   4. Browser will show 'Authentication successful'")
    print("")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_FILE), SCOPES
        )
        # Try multiple ports if one is blocked
        for port in [8085, 8086, 8087, 9090, 9091]:
            try:
                print(f"   Trying port {port}...")
                creds = flow.run_local_server(port=port, open_browser=True)
                break
            except OSError as e:
                if "access" in str(e).lower():
                    print(f"   Port {port} blocked, trying next...")
                    continue
                raise

        # Save token
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

        print("")
        print("=" * 60)
        print("  ✅ SUCCESS!")
        print("=" * 60)
        print("")
        print(f"📁 Token saved to: {TOKEN_FILE}")
        print("🔑 Scopes granted:")
        for scope in SCOPES:
            print(f"   • {scope}")
        print("")
        print("📧 You can now send emails!")
        print("")
        print("Next step: Run 'python send_email_direct.py'")
        print("")

    except Exception as e:
        print("")
        print(f"❌ Authentication failed: {e}")
        print("")
        print("Troubleshooting:")
        print("   1. Make sure browser opened")
        print("   2. Complete the sign-in flow")
        print("   3. If blocked, click 'Advanced' → 'Go to (unsafe)'")
        print("")
        sys.exit(1)


if __name__ == "__main__":
    main()
