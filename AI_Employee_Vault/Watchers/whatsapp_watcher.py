#!/usr/bin/env python3
"""
WhatsApp Watcher - AI Employee Message Monitor

Monitors WhatsApp Web for unread messages with specific keywords
and creates task files in Needs_Action folder.

Python 3.13+ | Uses Playwright | Checks every 30 seconds
Persistent session stored in /session/whatsapp

Keywords: urgent, invoice, payment, sales

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
│ pm2 start whatsapp_watcher.py --name "whatsapp-watcher" --interpreter python3  #
│                                                                            │
│ # View logs                                                                │
│ pm2 logs whatsapp-watcher                                                  │
│                                                                            │
│ # Monitor status                                                           │
│ pm2 status                                                                 │
│                                                                            │
│ # Stop                                                                     │
│ pm2 stop whatsapp-watcher                                                  │
│                                                                            │
│ # Restart after QR login                                                   │
│ pm2 restart whatsapp-watcher                                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ FIRST-TIME SETUP                                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Run manually first:                                                     │
│    python watchers/whatsapp_watcher.py                                     │
│                                                                            │
│ 2. A browser window will open with QR code                                 │
│ 3. Scan QR code with WhatsApp mobile app                                   │
│ 4. Session will be saved to session/whatsapp                               │
│ 5. Subsequent runs will use saved session                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ TESTING                                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Send a test WhatsApp message to yourself or a test group with:          │
│    - "URGENT: Please review the invoice for payment"                       │
│    - Include keywords: urgent, invoice, payment, sales                     │
│                                                                            │
│ 2. Run the script manually first to login:                                 │
│    python watchers/whatsapp_watcher.py                                     │
│                                                                            │
│ 3. After login, send test message and watch for detection                  │
│                                                                            │
│ 4. Check Needs_Action folder for new .md file                              │
│                                                                            │
│ 5. Verify the YAML frontmatter is correct                                  │
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
SESSION_PATH: Final[Path] = VAULT_ROOT / "session" / "whatsapp"

# Monitoring configuration
CHECK_INTERVAL: Final[float] = 30.0  # seconds
KEYWORDS: Final[list[str]] = ["urgent", "invoice", "payment", "sales"]

# WhatsApp Web selectors (may need updates if WhatsApp changes UI)
WHATSAPP_URL: Final[str] = "https://web.whatsapp.com"
MESSAGE_SELECTOR: Final[str] = "div[data-testid='cell-frame-container']"
UNREAD_BADGE_SELECTOR: Final[str] = "span[data-testid='unread-badge']"
CHAT_TITLE_SELECTOR: Final[str] = "div[role='heading']"

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# ─────────────────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────────────────


def setup_logging() -> logging.Logger:
    """Configure logging with both file and console handlers."""
    logger = logging.getLogger("whatsapp_watcher")
    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    # File handler
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"whatsapp_watcher_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# ─────────────────────────────────────────────────────────────────────────────
# WhatsApp Service
# ─────────────────────────────────────────────────────────────────────────────


class WhatsAppService:
    """Handles WhatsApp Web interaction via Playwright."""

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

    def navigate_to_whatsapp(self) -> bool:
        """Navigate to WhatsApp Web."""
        try:
            self.page.goto(WHATSAPP_URL, wait_until="networkidle", timeout=60000)
            self.logger.info("Navigated to WhatsApp Web")
            return True
        except Exception as e:
            self.logger.error(f"Failed to navigate: {e}")
            return False

    def is_logged_in(self) -> bool:
        """Check if WhatsApp is logged in."""
        try:
            # Check for main chat list element
            self.page.wait_for_selector(CHAT_TITLE_SELECTOR, timeout=5000)
            return True
        except Exception:
            return False

    def wait_for_login(self, timeout: int = 120) -> bool:
        """Wait for user to scan QR and login."""
        self.logger.info("Waiting for QR login...")
        print("\n📱 Scan QR code with WhatsApp mobile app")
        print("   Session will be saved for future runs\n")

        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_logged_in():
                self.logger.info("Login successful")
                print("✅ Login successful!\n")
                return True
            time.sleep(2)

        self.logger.warning("Login timeout")
        print("❌ Login timeout. Please restart and scan QR code.\n")
        return False

    def get_unread_messages(self) -> list[dict]:
        """Get unread messages with keywords."""
        messages = []

        try:
            # Wait for chat list to load
            self.page.wait_for_selector(MESSAGE_SELECTOR, timeout=10000)

            # Get all chat containers
            chat_containers = self.page.query_selector_all(MESSAGE_SELECTOR)

            for container in chat_containers:
                try:
                    # Check for unread badge
                    unread_badge = container.query_selector(UNREAD_BADGE_SELECTOR)
                    if not unread_badge:
                        continue

                    # Get chat title
                    title_elem = container.query_selector(CHAT_TITLE_SELECTOR)
                    if not title_elem:
                        continue

                    title = title_elem.inner_text()
                    preview = container.inner_text()

                    # Check for keywords
                    preview_lower = preview.lower()
                    if any(keyword in preview_lower for keyword in KEYWORDS):
                        messages.append(
                            {
                                "from": title,
                                "preview": preview,
                                "timestamp": datetime.now(),
                                "keywords_found": [
                                    k for k in KEYWORDS if k in preview_lower
                                ],
                            }
                        )

                except Exception as e:
                    self.logger.debug(f"Error processing chat: {e}")
                    continue

            self.logger.info(f"Found {len(messages)} unread messages with keywords")
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

    def create_task_file(self, message: dict) -> Optional[Path]:
        """Create a task file from message data."""
        try:
            # Generate filename
            timestamp = message["timestamp"].strftime("%Y-%m-%d_%H-%M-%S")
            from_safe = self._sanitize_filename(message["from"])[:30]
            filename = f"{timestamp}_whatsapp_{from_safe}.md"
            filepath = NEEDS_ACTION_DIR / filename

            # Handle duplicates
            counter = 1
            while filepath.exists():
                filename = f"{timestamp}_whatsapp_{from_safe}_{counter}.md"
                filepath = NEEDS_ACTION_DIR / filename
                counter += 1

            # Generate content
            content = self._generate_content(message)

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

    def _generate_content(self, message: dict) -> str:
        """Generate markdown content with YAML frontmatter."""
        timestamp_str = message["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        keywords_str = ", ".join(message["keywords_found"])

        return f"""---
type: whatsapp_message
from: {message["from"]}
received: {timestamp_str}
priority: P1
status: pending
keywords: {keywords_str}
---

# 💬 WhatsApp Message Task

## Details

| Field | Value |
|-------|-------|
| **From** | {message["from"]} |
| **Received** | {timestamp_str} |
| **Priority** | 🟠 P1 |
| **Status** | 🟡 Pending |
| **Keywords** | {keywords_str} |

---

## Message Preview

{message["preview"]}

---

## Actions

- [ ] Review message content
- [ ] Determine required response
- [ ] Respond via WhatsApp
- [ ] Mark as processed

---

*Created by WhatsApp Watcher • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""


# ─────────────────────────────────────────────────────────────────────────────
# WhatsApp Watcher (Main Class)
# ─────────────────────────────────────────────────────────────────────────────


class WhatsAppWatcher:
    """Main WhatsApp watcher class."""

    def __init__(self) -> None:
        self.logger = setup_logging()
        self.whatsapp_service = WhatsAppService(self.logger)
        self.task_manager = TaskFileManager(self.logger)
        self.running = False
        self.processed_messages: set[str] = set()

    def start(self) -> None:
        """Start the WhatsApp watcher."""
        self.logger.info("=" * 60)
        self.logger.info("WHATSAPP WATCHER STARTING")
        self.logger.info(f"Check Interval: {CHECK_INTERVAL}s")
        self.logger.info(f"Keywords: {', '.join(KEYWORDS)}")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  💬 WHATSAPP WATCHER")
        print(f"  Checking every {CHECK_INTERVAL}s")
        print(f"  Keywords: {', '.join(KEYWORDS)}")
        print(f"  Press Ctrl+C to stop")
        print(f"{'=' * 60}\n")

        # Start browser
        if not self.whatsapp_service.start_browser():
            self.logger.error("Failed to start browser. Exiting.")
            return

        # Navigate to WhatsApp
        if not self.whatsapp_service.navigate_to_whatsapp():
            self.logger.error("Failed to navigate to WhatsApp. Exiting.")
            self.whatsapp_service.close()
            return

        # Check/login
        if not self.whatsapp_service.is_logged_in():
            if not self.whatsapp_service.wait_for_login(timeout=120):
                self.whatsapp_service.close()
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
                # Refresh page periodically to get new messages
                self.whatsapp_service.page.reload(wait_until="networkidle")
                time.sleep(3)  # Wait for page to load

                self._check_messages()
                time.sleep(CHECK_INTERVAL)
            except Exception as e:
                self.logger.exception(f"Error in loop: {e}")
                time.sleep(CHECK_INTERVAL)

    def _check_messages(self) -> None:
        """Check for new messages."""
        self.logger.debug("Checking for new messages...")

        messages = self.whatsapp_service.get_unread_messages()

        new_count = 0
        for message in messages:
            # Create unique key for deduplication
            msg_key = f"{message['from']}:{message['preview'][:50]}"

            # Skip already processed
            if msg_key in self.processed_messages:
                continue

            # Create task file
            filepath = self.task_manager.create_task_file(message)
            if filepath:
                self.processed_messages.add(msg_key)
                new_count += 1

                print(f"\n📬 New WhatsApp message from: {message['from']}")

        if new_count > 0:
            self.logger.info(f"Created {new_count} new task(s)")
        else:
            self.logger.debug("No new messages")

    def _shutdown(self) -> None:
        """Perform graceful shutdown."""
        self.whatsapp_service.close()

        self.logger.info("=" * 60)
        self.logger.info("WHATSAPP WATCHER STOPPED")
        self.logger.info(f"Total processed: {len(self.processed_messages)}")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  🛑 WHATSAPP WATCHER STOPPED")
        print(f"  Processed: {len(self.processed_messages)} messages")
        print(f"{'=' * 60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Main entry point."""
    watcher = WhatsAppWatcher()
    watcher.start()


if __name__ == "__main__":
    main()
