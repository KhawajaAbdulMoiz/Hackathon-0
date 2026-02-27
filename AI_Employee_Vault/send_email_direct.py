#!/usr/bin/env python3
"""
Direct Email Sender - Send approved email drafts via Gmail API

Usage:
    python send_email_direct.py
"""

import base64
import json
import sys
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

VAULT_ROOT = Path(__file__).parent.resolve()
APPROVED_DIR = VAULT_ROOT / "Approved"
DONE_DIR = VAULT_ROOT / "Done"
LOGS_DIR = VAULT_ROOT / "Logs"
TOKEN_FILE = VAULT_ROOT / "token.json"
CREDENTIALS_FILE = VAULT_ROOT / "client_secret_1005799766116-6oj47f92vtmaacrvrfm0dgocjrkv8ukr.apps.googleusercontent.com.json"

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


# ─────────────────────────────────────────────────────────────────────────────
# Functions
# ─────────────────────────────────────────────────────────────────────────────


def get_gmail_service():
    """Authenticate and return Gmail API service."""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired token...")
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        else:
            print("❌ Authentication required. Run OAuth setup first.")
            return None

    try:
        service = build("gmail", "v1", credentials=creds)
        print("✅ Gmail API connected successfully")
        return service
    except Exception as e:
        print(f"❌ Failed to build Gmail service: {e}")
        return None


def parse_draft_file(filepath):
    """Parse email draft markdown file."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract YAML frontmatter
    email_data = {"to": "", "subject": "", "body": ""}

    # Parse frontmatter
    if content.startswith("---"):
        lines = content.split("\n")
        in_frontmatter = False
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip().strip('"')
                if key in ["to", "subject", "created", "status", "priority"]:
                    email_data[key] = value

    # Extract HTML body from code block
    if "```html" in content:
        body_start = content.find("```html") + 7
        body_end = content.find("```", body_start)
        email_data["body"] = content[body_start:body_end].strip()
    else:
        # Fallback: extract from Email Body section
        if "## Email Body" in content:
            body_start = content.find("## Email Body") + len("## Email Body")
            email_data["body"] = content[body_start:].strip()

    return email_data


def create_message(to, subject, body):
    """Create Gmail API message."""
    message = MIMEText(body, "html", "utf-8")
    message["to"] = to
    message["from"] = "me"
    message["subject"] = subject

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    return {"raw": raw_message}


def send_email(service, to, subject, body):
    """Send email via Gmail API."""
    try:
        message = create_message(to, subject, body)
        sent_message = (
            service.users().messages().send(userId="me", body=message).execute()
        )
        return {"success": True, "id": sent_message["id"]}
    except HttpError as error:
        return {"success": False, "error": str(error)}


def move_to_done(source_path):
    """Move processed file to Done folder."""
    import shutil

    timestamp = source_path.stem.split("_")[-1] if "_" in source_path.stem else ""
    dest_name = f"email_sent_{source_path.name}"
    dest_path = DONE_DIR / dest_name

    try:
        shutil.move(str(source_path), str(dest_path))
        print(f"📁 File moved to: {dest_path.name}")
        return dest_path
    except Exception as e:
        print(f"⚠️  Could not move file: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def main():
    print("")
    print("=" * 60)
    print("  📧 Direct Email Sender")
    print("  AI Employee Vault")
    print("=" * 60)
    print("")

    # Get Gmail service
    service = get_gmail_service()
    if not service:
        print("\n❌ Cannot proceed without Gmail authentication")
        sys.exit(1)

    # Find approved draft files
    approved_files = list(APPROVED_DIR.glob("email_draft_*.md"))

    if not approved_files:
        print("📭 No email drafts found in Approved folder")
        print(f"   Looking in: {APPROVED_DIR}")
        sys.exit(0)

    print(f"📋 Found {len(approved_files)} draft(s) to send:\n")

    for draft_file in approved_files:
        print(f"Processing: {draft_file.name}")
        print("-" * 40)

        # Parse draft
        email_data = parse_draft_file(draft_file)

        print(f"   To:      {email_data['to']}")
        print(f"   Subject: {email_data['subject']}")

        # Send email
        result = send_email(
            service, email_data["to"], email_data["subject"], email_data["body"]
        )

        if result["success"]:
            print(f"   ✅ SENT! Message ID: {result['id']}")

            # Move to Done
            move_to_done(draft_file)

            # Log success
            log_file = LOGS_DIR / f"email_sent_{email_data['to'].split('@')[0]}.log"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{__import__('datetime').datetime.now().isoformat()}] ")
                f.write(f"Sent to {email_data['to']} - ID: {result['id']}\n")
        else:
            print(f"   ❌ FAILED: {result['error']}")

        print("")

    print("=" * 60)
    print("  Email sending complete!")
    print("=" * 60)
    print("")

    # Summary
    print("📊 Summary:")
    print(f"   Processed: {len(approved_files)}")
    print(f"   Check Gmail Sent folder to verify")
    print("")


if __name__ == "__main__":
    main()
