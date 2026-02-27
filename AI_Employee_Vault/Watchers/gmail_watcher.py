#!/usr/bin/env python3
"""
Gmail Watcher - AI Employee Email Monitor

Monitors Gmail inbox for unread important emails with specific keywords
and creates task files in Needs_Action folder.

Python 3.13+ | Uses Google Gmail API | Checks every 120 seconds

Keywords: urgent, invoice, payment, sales

┌─────────────────────────────────────────────────────────────────────────────┐
│ PM2 SETUP                                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ # Install PM2 (Node.js required)                                           │
│ npm install -g pm2                                                         │
│                                                                            │
│ # Start with PM2                                                           │
│ pm2 start gmail_watcher.py --name "gmail-watcher" --interpreter python3    │
│                                                                            │
│ # View logs                                                                │
│ pm2 logs gmail-watcher                                                     │
│                                                                            │
│ # Monitor status                                                           │
│ pm2 status                                                                 │
│                                                                            │
│ # Stop                                                                     │
│ pm2 stop gmail-watcher                                                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ TESTING                                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Send a test email to your Gmail account with:                           │
│    - Subject: "URGENT: Test Invoice Payment"                               │
│    - Body: Include keywords like "urgent", "invoice", "payment"            │
│    - Mark as unread                                                        │
│                                                                            │
│ 2. Run the script manually first:                                          │
│    python watchers/gmail_watcher.py                                        │
│                                                                            │
│ 3. Check Needs_Action folder for new .md file                              │
│                                                                            │
│ 4. Verify the YAML frontmatter is correct                                  │
└─────────────────────────────────────────────────────────────────────────────┘
"""

import base64
import logging
import os
import sys
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Final, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

VAULT_ROOT: Final[Path] = Path(__file__).parent.parent.resolve()
NEEDS_ACTION_DIR: Final[Path] = VAULT_ROOT / "Needs_Action"
LOGS_DIR: Final[Path] = VAULT_ROOT / "Logs"
CREDENTIALS_FILE: Final[Path] = VAULT_ROOT / "client_secret_1005799766116-6oj47f92vtmaacrvrfm0dgocjrkv8ukr.apps.googleusercontent.com.json"
TOKEN_FILE: Final[Path] = VAULT_ROOT / "token.json"

# Gmail API Scopes
SCOPES: Final[list[str]] = ["https://www.googleapis.com/auth/gmail.readonly"]

# Monitoring configuration
CHECK_INTERVAL: Final[float] = 120.0  # seconds
KEYWORDS: Final[list[str]] = ["urgent", "invoice", "payment", "sales"]
LABEL_IDS: Final[list[str]] = ["INBOX", "IMPORTANT", "UNREAD"]

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# ─────────────────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────────────────


def setup_logging() -> logging.Logger:
    """Configure logging with both file and console handlers."""
    logger = logging.getLogger("gmail_watcher")
    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    # File handler
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"gmail_watcher_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# ─────────────────────────────────────────────────────────────────────────────
# Gmail Service
# ─────────────────────────────────────────────────────────────────────────────


class GmailService:
    """Handles Gmail API authentication and operations."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.service: Optional[build] = None
        self.creds: Optional[Credentials] = None

    def authenticate(self) -> bool:
        """Authenticate with Gmail API."""
        try:
            # Load existing credentials
            if TOKEN_FILE.exists():
                self.creds = Credentials.from_authorized_user_file(
                    str(TOKEN_FILE), SCOPES
                )
                self.logger.debug("Loaded existing credentials")

            # Refresh or obtain new credentials
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.logger.info("Refreshing expired credentials")
                    self.creds.refresh(Request())
                else:
                    self.logger.info("Starting OAuth flow")
                    if not CREDENTIALS_FILE.exists():
                        self.logger.error(
                            f"Credentials file not found: {CREDENTIALS_FILE}"
                        )
                        return False

                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(CREDENTIALS_FILE), SCOPES
                    )
                    self.creds = flow.run_local_server(port=0, open_browser=False)

                # Save credentials
                with open(TOKEN_FILE, "w", encoding="utf-8") as token:
                    token.write(self.creds.to_json())
                self.logger.info("Credentials saved")

            # Build service
            self.service = build("gmail", "v1", credentials=self.creds)
            self.logger.info("Gmail service initialized")
            return True

        except Exception as e:
            self.logger.exception(f"Authentication failed: {e}")
            return False

    def get_unread_emails(self, max_results: int = 10) -> list[dict]:
        """Fetch unread important emails."""
        if not self.service:
            self.logger.error("Gmail service not initialized")
            return []

        try:
            # Build query for unread, important emails with keywords
            keyword_query = " OR ".join(KEYWORDS)
            query = f"is:unread is:important ({keyword_query})"

            results = (
                self.service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )

            messages = results.get("messages", [])
            self.logger.info(f"Found {len(messages)} matching emails")

            emails = []
            for msg in messages:
                email_data = self._get_email_details(msg["id"])
                if email_data:
                    emails.append(email_data)

            return emails

        except HttpError as error:
            self.logger.error(f"Gmail API error: {error}")
            return []
        except Exception as e:
            self.logger.exception(f"Error fetching emails: {e}")
            return []

    def _get_email_details(self, message_id: str) -> Optional[dict]:
        """Get detailed email information."""
        try:
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            headers = message["payload"]["headers"]
            email_data = {
                "id": message_id,
                "from": self._get_header(headers, "From"),
                "to": self._get_header(headers, "To"),
                "subject": self._get_header(headers, "Subject"),
                "date": self._get_header(headers, "Date"),
                "body": "",
            }

            # Extract body
            email_data["body"] = self._extract_body(message["payload"])

            # Parse received datetime
            try:
                email_data["received"] = parsedate_to_datetime(email_data["date"])
            except Exception:
                email_data["received"] = datetime.now()

            # Determine priority
            email_data["priority"] = self._determine_priority(email_data["subject"])

            return email_data

        except Exception as e:
            self.logger.error(f"Error getting email details: {e}")
            return None

    def _get_header(self, headers: list, name: str) -> str:
        """Extract header value by name."""
        for header in headers:
            if header["name"].lower() == name.lower():
                return header["value"]
        return ""

    def _extract_body(self, payload: dict) -> str:
        """Extract email body from payload."""
        body = ""

        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain" and "data" in part["body"]:
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode(
                        "utf-8", errors="ignore"
                    )
                    break
        elif "body" in payload and "data" in payload["body"]:
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode(
                "utf-8", errors="ignore"
            )

        return body[:2000]  # Limit body length

    def _determine_priority(self, subject: str) -> str:
        """Determine email priority based on subject."""
        subject_lower = subject.lower()
        if "urgent" in subject_lower or "critical" in subject_lower:
            return "P0"
        elif "invoice" in subject_lower or "payment" in subject_lower:
            return "P1"
        elif "sales" in subject_lower:
            return "P2"
        return "P3"

    def mark_as_read(self, message_id: str) -> bool:
        """Mark email as read."""
        try:
            (
                self.service.users()
                .messages()
                .modify(userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]})
                .execute()
            )
            self.logger.debug(f"Marked message {message_id} as read")
            return True
        except Exception as e:
            self.logger.error(f"Failed to mark as read: {e}")
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Task File Manager
# ─────────────────────────────────────────────────────────────────────────────


class TaskFileManager:
    """Handles creation of task markdown files."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)

    def create_task_file(self, email: dict) -> Optional[Path]:
        """Create a task file from email data."""
        try:
            # Generate filename
            timestamp = email["received"].strftime("%Y-%m-%d_%H-%M-%S")
            subject_safe = self._sanitize_filename(email["subject"])[:50]
            filename = f"{timestamp}_email_{subject_safe}.md"
            filepath = NEEDS_ACTION_DIR / filename

            # Handle duplicates
            counter = 1
            while filepath.exists():
                filename = f"{timestamp}_email_{subject_safe}_{counter}.md"
                filepath = NEEDS_ACTION_DIR / filename
                counter += 1

            # Generate content
            content = self._generate_content(email)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            self.logger.info(f"Created task file: {filename}")
            return filepath

        except Exception as e:
            self.logger.exception(f"Error creating task file: {e}")
            return None

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for use in filename."""
        return "".join(c if c.isalnum() or c in " -_" else "_" for c in name)

    def _generate_content(self, email: dict) -> str:
        """Generate markdown content with YAML frontmatter."""
        received_str = email["received"].strftime("%Y-%m-%d %H:%M:%S")

        return f"""---
type: email
from: {email["from"]}
subject: {email["subject"]}
received: {received_str}
priority: {email["priority"]}
status: pending
gmail_id: {email["id"]}
---

# 📧 Email Task: {email["subject"]}

## Details

| Field | Value |
|-------|-------|
| **From** | {email["from"]} |
| **Received** | {received_str} |
| **Priority** | {email["priority"]} |
| **Status** | 🟡 Pending |

---

## Body

{email["body"]}

---

## Actions

- [ ] Review email content
- [ ] Determine required response
- [ ] Execute response or delegate
- [ ] Mark email as processed

---

*Created by Gmail Watcher • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""


# ─────────────────────────────────────────────────────────────────────────────
# Gmail Watcher (Main Class)
# ─────────────────────────────────────────────────────────────────────────────


class GmailWatcher:
    """Main Gmail watcher class."""

    def __init__(self) -> None:
        self.logger = setup_logging()
        self.gmail_service = GmailService(self.logger)
        self.task_manager = TaskFileManager(self.logger)
        self.running = False
        self.processed_ids: set[str] = set()

    def start(self) -> None:
        """Start the Gmail watcher."""
        self.logger.info("=" * 60)
        self.logger.info("GMAIL WATCHER STARTING")
        self.logger.info(f"Check Interval: {CHECK_INTERVAL}s")
        self.logger.info(f"Keywords: {', '.join(KEYWORDS)}")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  📧 GMAIL WATCHER")
        print(f"  Checking every {CHECK_INTERVAL}s")
        print(f"  Keywords: {', '.join(KEYWORDS)}")
        print(f"  Press Ctrl+C to stop")
        print(f"{'=' * 60}\n")

        # Authenticate
        if not self.gmail_service.authenticate():
            self.logger.error("Failed to authenticate. Exiting.")
            print("\n❌ Authentication failed. Check credentials and try again.\n")
            return

        self.running = True

        try:
            self._run_loop()
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        except Exception as e:
            self.logger.exception(f"Watcher crashed: {e}")
        finally:
            self._shutdown()

    def _run_loop(self) -> None:
        """Main watcher loop."""
        while self.running:
            try:
                self._check_emails()
                time.sleep(CHECK_INTERVAL)
            except Exception as e:
                self.logger.exception(f"Error in loop: {e}")
                time.sleep(CHECK_INTERVAL)

    def _check_emails(self) -> None:
        """Check for new emails."""
        self.logger.debug("Checking for new emails...")

        emails = self.gmail_service.get_unread_emails(max_results=10)

        new_count = 0
        for email in emails:
            # Skip already processed
            if email["id"] in self.processed_ids:
                continue

            # Create task file
            filepath = self.task_manager.create_task_file(email)
            if filepath:
                self.processed_ids.add(email["id"])
                new_count += 1

                # Optionally mark as read
                # self.gmail_service.mark_as_read(email["id"])

                print(f"\n📬 New email task: {email['subject'][:50]}")

        if new_count > 0:
            self.logger.info(f"Created {new_count} new task(s)")
        else:
            self.logger.debug("No new emails")

    def _shutdown(self) -> None:
        """Perform graceful shutdown."""
        self.logger.info("=" * 60)
        self.logger.info("GMAIL WATCHER STOPPED")
        self.logger.info(f"Total processed: {len(self.processed_ids)}")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  🛑 GMAIL WATCHER STOPPED")
        print(f"  Processed: {len(self.processed_ids)} emails")
        print(f"{'=' * 60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Main entry point."""
    watcher = GmailWatcher()
    watcher.start()


if __name__ == "__main__":
    main()
