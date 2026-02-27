#!/usr/bin/env python3
"""
LinkedIn Watcher - AI Employee Lead Monitor

Monitors LinkedIn for new messages and notifications related to
business leads, sales opportunities, and project inquiries.

Python 3.13+ | Uses Playwright | Checks every 60 seconds
Persistent session stored in /session/linkedin

Keywords: sales, client, project, lead, opportunity, hire

┌─────────────────────────────────────────────────────────────────────────────┐
│ PREREQUISITES                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ # Install Playwright                                                       │
│ pip install playwright                                                     │
│ playwright install chromium                                                │
│                                                                            │
│ # Install PM2 (Node.js required)                                           │
│ npm install -g pm2                                                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ PM2 SETUP                                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ # Start with PM2                                                           │
│ pm2 start linkedin_watcher.py --name "linkedin-watcher" --interpreter python3  #
│                                                                            │
│ # View logs                                                                │
│ pm2 logs linkedin-watcher                                                  │
│                                                                            │
│ # Monitor status                                                           │
│ pm2 status                                                                 │
│                                                                            │
│ # Stop                                                                     │
│ pm2 stop linkedin-watcher                                                  │
│                                                                            │
│ # Restart after login                                                      │
│ pm2 restart linkedin-watcher                                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ FIRST-TIME SETUP                                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Run manually first:                                                     │
│    python watchers/linkedin_watcher.py                                     │
│                                                                            │
│ 2. A browser window will open with LinkedIn login page                     │
│ 3. Log in with your LinkedIn credentials                                   │
│ 4. Complete any 2FA if required                                            │
│ 5. Session will be saved to session/linkedin                               │
│ 6. Subsequent runs will use saved session                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ TESTING                                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Have someone send you a LinkedIn message with:                          │
│    - "Interested in your services for a new project"                       │
│    - Include keywords: sales, client, project, opportunity                 │
│                                                                            │
│ 2. Or engage with a post that might trigger a notification                 │
│                                                                            │
│ 3. Run the script manually first to login:                                 │
│    python watchers/linkedin_watcher.py                                     │
│                                                                            │
│ 4. After login, wait for the check interval (60s)                          │
│                                                                            │
│ 5. Check Needs_Action folder for new .md file                              │
│                                                                            │
│ 6. Verify the YAML frontmatter is correct                                  │
└─────────────────────────────────────────────────────────────────────────────┘
"""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Final, Optional

from playwright.sync_api import Page, Playwright, sync_playwright

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

VAULT_ROOT: Final[Path] = Path(__file__).parent.parent.resolve()
NEEDS_ACTION_DIR: Final[Path] = VAULT_ROOT / "Needs_Action"
LOGS_DIR: Final[Path] = VAULT_ROOT / "Logs"
SESSION_PATH: Final[Path] = VAULT_ROOT / "session" / "linkedin"

# Monitoring configuration
CHECK_INTERVAL: Final[float] = 60.0  # seconds
KEYWORDS: Final[list[str]] = ["sales", "client", "project", "lead", "opportunity", "hire"]
BUSINESS_KEYWORDS: Final[list[str]] = ["partnership", "collaboration", "proposal", "contract"]

# LinkedIn URLs
LINKEDIN_URL: Final[str] = "https://www.linkedin.com"
LINKEDIN_MESSAGING_URL: Final[str] = "https://www.linkedin.com/messaging"
LINKEDIN_NOTIFICATIONS_URL: Final[str] = "https://www.linkedin.com/notifications"

# Selectors (may need updates if LinkedIn changes UI)
NOTIFICATION_BADGE_SELECTOR: Final[str] = ".notification-badge, [aria-label*='notification']"
MESSAGE_ITEM_SELECTOR: Final[str] = "div.msg-overlay-list-item, li.msg-s-message-list-item"
NOTIFICATION_ITEM_SELECTOR: Final[str] = ".notification-item, div.update-components-text"

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# ─────────────────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────────────────


def setup_logging() -> logging.Logger:
    """Configure logging with both file and console handlers."""
    logger = logging.getLogger("linkedin_watcher")
    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    # File handler
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"linkedin_watcher_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# ─────────────────────────────────────────────────────────────────────────────
# LinkedIn Service
# ─────────────────────────────────────────────────────────────────────────────


class LinkedInService:
    """Handles LinkedIn interaction via Playwright."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.playwright: Optional[Playwright] = None
        self.browser = None
        self.page: Optional[Page] = None
        self.session_path = SESSION_PATH

    def start_browser(self) -> bool:
        """Start browser with persistent context."""
        try:
            self.playwright = sync_playwright().start()

            # Create persistent browser context
            self.session_path.mkdir(parents=True, exist_ok=True)

            self.browser = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.session_path),
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            self.page = self.browser.pages[0]
            self.logger.info("Browser started with persistent session")
            return True

        except Exception as e:
            self.logger.exception(f"Failed to start browser: {e}")
            return False

    def navigate_to_linkedin(self) -> bool:
        """Navigate to LinkedIn."""
        try:
            self.page.goto(LINKEDIN_URL, wait_until="networkidle", timeout=60000)
            self.logger.info("Navigated to LinkedIn")
            return True
        except Exception as e:
            self.logger.error(f"Failed to navigate: {e}")
            return False

    def is_logged_in(self) -> bool:
        """Check if LinkedIn is logged in."""
        try:
            # Check for profile icon or feed
            self.page.wait_for_selector(
                "div.profile-detail-card, nav.global-nav, #mynav", timeout=5000
            )
            return True
        except Exception:
            return False

    def wait_for_login(self, timeout: int = 180) -> bool:
        """Wait for user to log in."""
        self.logger.info("Waiting for login...")
        print("\n🔐 Log in to LinkedIn")
        print("   Complete any 2FA if required")
        print("   Session will be saved for future runs\n")

        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_logged_in():
                self.logger.info("Login successful")
                print("✅ Login successful!\n")
                return True
            time.sleep(3)

        self.logger.warning("Login timeout")
        print("❌ Login timeout. Please restart and try again.\n")
        return False

    def get_unread_notifications(self) -> list[dict]:
        """Get unread notifications with business keywords."""
        notifications = []

        try:
            # Navigate to notifications page
            self.page.goto(
                LINKEDIN_NOTIFICATIONS_URL, wait_until="networkidle", timeout=30000
            )
            time.sleep(3)  # Wait for content to load

            # Get notification items
            notification_items = self.page.query_selector_all(NOTIFICATION_ITEM_SELECTOR)

            for item in notification_items[:10]:  # Limit to first 10
                try:
                    text = item.inner_text()
                    text_lower = text.lower()

                    # Check for keywords
                    found_keywords = [k for k in KEYWORDS if k in text_lower]
                    found_business = [k for k in BUSINESS_KEYWORDS if k in text_lower]

                    if found_keywords or found_business:
                        notifications.append(
                            {
                                "type": "notification",
                                "content": text[:500],
                                "timestamp": datetime.now(),
                                "keywords": found_keywords + found_business,
                                "priority": "P1" if found_keywords else "P2",
                            }
                        )

                except Exception as e:
                    self.logger.debug(f"Error processing notification: {e}")
                    continue

            self.logger.info(f"Found {len(notifications)} relevant notifications")
            return notifications

        except Exception as e:
            self.logger.error(f"Error getting notifications: {e}")
            return []

    def get_unread_messages(self) -> list[dict]:
        """Get unread messages with business keywords."""
        messages = []

        try:
            # Navigate to messaging page
            self.page.goto(
                LINKEDIN_MESSAGING_URL, wait_until="networkidle", timeout=30000
            )
            time.sleep(3)  # Wait for content to load

            # Get message items
            message_items = self.page.query_selector_all(MESSAGE_ITEM_SELECTOR)

            for item in message_items[:10]:  # Limit to first 10
                try:
                    text = item.inner_text()
                    text_lower = text.lower()

                    # Check for unread indicator
                    is_unread = "unread" in text_lower or "new" in text_lower

                    # Check for keywords
                    found_keywords = [k for k in KEYWORDS if k in text_lower]
                    found_business = [k for k in BUSINESS_KEYWORDS if k in text_lower]

                    if (is_unread or found_keywords) and (found_keywords or found_business):
                        # Extract sender name (simplified)
                        sender = "Unknown"
                        try:
                            sender_elem = item.query_selector("h3, .msg-s-message-list-item__sender-name")
                            if sender_elem:
                                sender = sender_elem.inner_text()
                        except Exception:
                            pass

                        messages.append(
                            {
                                "type": "message",
                                "from": sender,
                                "content": text[:500],
                                "timestamp": datetime.now(),
                                "keywords": found_keywords + found_business,
                                "priority": "P1" if found_keywords else "P2",
                            }
                        )

                except Exception as e:
                    self.logger.debug(f"Error processing message: {e}")
                    continue

            self.logger.info(f"Found {len(messages)} relevant messages")
            return messages

        except Exception as e:
            self.logger.error(f"Error getting messages: {e}")
            return []

    def close(self) -> None:
        """Close browser."""
        try:
            if self.browser:
                self.browser.close()
                self.logger.debug("Browser closed")
        except Exception as e:
            self.logger.error(f"Error closing browser: {e}")

        if self.playwright:
            self.playwright.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Task File Manager
# ─────────────────────────────────────────────────────────────────────────────


class TaskFileManager:
    """Handles creation of task markdown files."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)

    def create_task_file(self, item: dict) -> Optional[Path]:
        """Create a task file from notification/message data."""
        try:
            # Generate filename
            timestamp = item["timestamp"].strftime("%Y-%m-%d_%H-%M-%S")
            item_type = item["type"]
            keywords_str = "_".join(item["keywords"][:2]) if item["keywords"] else "lead"
            filename = f"{timestamp}_linkedin_{item_type}_{keywords_str}.md"
            filepath = NEEDS_ACTION_DIR / filename

            # Handle duplicates
            counter = 1
            while filepath.exists():
                filename = f"{timestamp}_linkedin_{item_type}_{keywords_str}_{counter}.md"
                filepath = NEEDS_ACTION_DIR / filename
                counter += 1

            # Generate content
            content = self._generate_content(item)

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

    def _generate_content(self, item: dict) -> str:
        """Generate markdown content with YAML frontmatter."""
        timestamp_str = item["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        keywords_str = ", ".join(item["keywords"])
        sender = item.get("from", "N/A")

        return f"""---
type: linkededin_{item["type"]}
from: {sender}
received: {timestamp_str}
priority: {item["priority"]}
status: pending
keywords: {keywords_str}
source: LinkedIn
---

# 💼 LinkedIn {'Message' if item["type"] == "message" else 'Notification'} Task

## Details

| Field | Value |
|-------|-------|
| **Type** | {item["type"].title()} |
| **From** | {sender} |
| **Received** | {timestamp_str} |
| **Priority** | {'🟠 P1' if item["priority"] == "P1" else '🔵 P2'} |
| **Status** | 🟡 Pending |
| **Keywords** | {keywords_str} |

---

## Content

{item["content"]}

---

## Actions

- [ ] Review the {'message' if item["type"] == "message" else 'notification'}
- [ ] Identify business opportunity
- [ ] Determine response strategy
- [ ] Respond via LinkedIn
- [ ] Update CRM if applicable
- [ ] Mark as processed

---

## Lead Qualification

| Criteria | Status |
|----------|--------|
| Budget mentioned | [ ] |
| Timeline discussed | [ ] |
| Decision maker | [ ] |
| Clear need | [ ] |

---

*Created by LinkedIn Watcher • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""


# ─────────────────────────────────────────────────────────────────────────────
# LinkedIn Watcher (Main Class)
# ─────────────────────────────────────────────────────────────────────────────


class LinkedInWatcher:
    """Main LinkedIn watcher class."""

    def __init__(self) -> None:
        self.logger = setup_logging()
        self.linkedin_service = LinkedInService(self.logger)
        self.task_manager = TaskFileManager(self.logger)
        self.running = False
        self.processed_items: set[str] = set()

    def start(self) -> None:
        """Start the LinkedIn watcher."""
        self.logger.info("=" * 60)
        self.logger.info("LINKEDIN WATCHER STARTING")
        self.logger.info(f"Check Interval: {CHECK_INTERVAL}s")
        self.logger.info(f"Keywords: {', '.join(KEYWORDS)}")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  💼 LINKEDIN WATCHER")
        print(f"  Checking every {CHECK_INTERVAL}s")
        print(f"  Keywords: {', '.join(KEYWORDS)}")
        print(f"  Press Ctrl+C to stop")
        print(f"{'=' * 60}\n")

        # Start browser
        if not self.linkedin_service.start_browser():
            self.logger.error("Failed to start browser. Exiting.")
            return

        # Navigate to LinkedIn
        if not self.linkedin_service.navigate_to_linkedin():
            self.logger.error("Failed to navigate to LinkedIn. Exiting.")
            self.linkedin_service.close()
            return

        # Check/login
        if not self.linkedin_service.is_logged_in():
            if not self.linkedin_service.wait_for_login(timeout=180):
                self.linkedin_service.close()
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
        check_count = 0

        while self.running:
            try:
                check_count += 1
                self.logger.debug(f"Check #{check_count}")

                # Check notifications and messages
                self._check_notifications()
                self._check_messages()

                time.sleep(CHECK_INTERVAL)
            except Exception as e:
                self.logger.exception(f"Error in loop: {e}")
                time.sleep(CHECK_INTERVAL)

    def _check_notifications(self) -> None:
        """Check for new notifications."""
        self.logger.debug("Checking notifications...")

        notifications = self.linkedin_service.get_unread_notifications()

        new_count = 0
        for notification in notifications:
            # Create unique key for deduplication
            item_key = f"notification:{notification['content'][:50]}"

            # Skip already processed
            if item_key in self.processed_items:
                continue

            # Create task file
            filepath = self.task_manager.create_task_file(notification)
            if filepath:
                self.processed_items.add(item_key)
                new_count += 1

                print(f"\n📬 New LinkedIn notification with keywords: {', '.join(notification['keywords'])}")

        if new_count > 0:
            self.logger.info(f"Created {new_count} notification task(s)")

    def _check_messages(self) -> None:
        """Check for new messages."""
        self.logger.debug("Checking messages...")

        messages = self.linkedin_service.get_unread_messages()

        new_count = 0
        for message in messages:
            # Create unique key for deduplication
            item_key = f"message:{message['from']}:{message['content'][:50]}"

            # Skip already processed
            if item_key in self.processed_items:
                continue

            # Create task file
            filepath = self.task_manager.create_task_file(message)
            if filepath:
                self.processed_items.add(item_key)
                new_count += 1

                print(f"\n📬 New LinkedIn message from: {message['from']}")

        if new_count > 0:
            self.logger.info(f"Created {new_count} message task(s)")

    def _shutdown(self) -> None:
        """Perform graceful shutdown."""
        self.linkedin_service.close()

        self.logger.info("=" * 60)
        self.logger.info("LINKEDIN WATCHER STOPPED")
        self.logger.info(f"Total processed: {len(self.processed_items)}")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  🛑 LINKEDIN WATCHER STOPPED")
        print(f"  Processed: {len(self.processed_items)} items")
        print(f"{'=' * 60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Main entry point."""
    watcher = LinkedInWatcher()
    watcher.start()


if __name__ == "__main__":
    main()
