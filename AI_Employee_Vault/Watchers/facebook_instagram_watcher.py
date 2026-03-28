#!/usr/bin/env python3
"""
Facebook/Instagram Watcher - AI Employee Social Media Monitor

Monitors Facebook and Instagram for messages/posts with business keywords
and creates task files in Needs_Action folder.

Python 3.13+ | Uses Playwright | Checks every 60 seconds

Keywords: sales, client, project

┌─────────────────────────────────────────────────────────────────────────────┐
│ PM2 SETUP                                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ # Install PM2 (Node.js required)                                           │
│ npm install -g pm2                                                         │
│                                                                            │
│ # Start with PM2                                                           │
│ pm2 start facebook_instagram_watcher.py --name "fb-ig-watcher" --interpreter python3
│                                                                            │
│ # View logs                                                                │
│ pm2 logs fb-ig-watcher                                                     │
│                                                                            │
│ # Monitor status                                                           │
│ pm2 status                                                                 │
│                                                                            │
│ # Stop                                                                     │
│ pm2 stop fb-ig-watcher                                                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ FIRST-TIME SETUP                                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Run the script manually first to login:                                 │
│    python watchers/facebook_instagram_watcher.py                           │
│                                                                            │
│ 2. Login to Facebook/Instagram when browser opens                          │
│ 3. Session will be saved to /Watchers/session/facebook/                    │
│ 4. Subsequent runs will use saved session                                  │
│                                                                            │
│ 5. For re-authentication, delete the session folder and re-run             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ TESTING                                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Send a test message on Facebook Messenger with:                         │
│    - Include keywords: "sales", "client", "project"                        │
│    - Example: "Hi, I'm interested in your sales services for my project"   │
│                                                                            │
│ 2. Run the script manually first:                                          │
│    python watchers/facebook_instagram_watcher.py                           │
│                                                                            │
│ 3. Check Needs_Action folder for new .md file                              │
│                                                                            │
│ 4. Verify the YAML frontmatter and summary are correct                     │
│                                                                            │
│ 5. For Instagram testing:                                                  │
│    - Send a DM with similar keywords                                       │
│    - Or check for mentions/comments on your posts                          │
└─────────────────────────────────────────────────────────────────────────────┘
"""

import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, Optional

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

# Import error recovery utilities
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from error_recovery import (
    ErrorRecoveryManager,
    ErrorSeverity,
    retry_with_backoff,
    GracefulDegradation,
)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

VAULT_ROOT: Final[Path] = Path(__file__).parent.parent.resolve()
NEEDS_ACTION_DIR: Final[Path] = VAULT_ROOT / "Needs_Action"
LOGS_DIR: Final[Path] = VAULT_ROOT / "Logs"
WATCHERS_DIR: Final[Path] = VAULT_ROOT / "Watchers"
SESSION_DIR: Final[Path] = WATCHERS_DIR / "session" / "facebook"

# Monitoring configuration
CHECK_INTERVAL: Final[float] = 60.0  # seconds
KEYWORDS: Final[list[str]] = ["sales", "client", "project"]

# Platform URLs
FACEBOOK_URL: Final[str] = "https://www.facebook.com"
FACEBOOK_MESSAGES_URL: Final[str] = "https://www.facebook.com/messages"
INSTAGRAM_URL: Final[str] = "https://www.instagram.com"
INSTAGRAM_MESSAGES_URL: Final[str] = "https://www.instagram.com/direct/inbox"

# Headless mode (set to False for first login to see browser)
HEADLESS: Final[bool] = False

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# ─────────────────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────────────────


def setup_logging() -> logging.Logger:
    """Configure logging with both file and console handlers."""
    logger = logging.getLogger("facebook_instagram_watcher")
    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    # File handler
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"fb_ig_watcher_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SocialMessage:
    """Represents a message from Facebook or Instagram."""

    platform: str
    message_id: str
    sender: str
    content: str
    timestamp: datetime
    keywords_found: list[str]
    priority: str
    url: str


# ─────────────────────────────────────────────────────────────────────────────
# Session Manager
# ─────────────────────────────────────────────────────────────────────────────


class SessionManager:
    """Handles browser session storage and loading."""

    def __init__(self, logger: logging.Logger, session_dir: Path) -> None:
        self.logger = logger
        self.session_dir = session_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def save_session(self, context: BrowserContext) -> bool:
        """Save browser context (cookies, localStorage)."""
        try:
            session_file = self.session_dir / "browser_session.json"

            # Save cookies
            cookies = context.cookies()
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump({"cookies": cookies}, f, indent=2)

            self.logger.info(f"Session saved to: {session_file}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save session: {e}")
            return False

    def load_session(self, context: BrowserContext) -> bool:
        """Load saved browser session."""
        try:
            session_file = self.session_dir / "browser_session.json"

            if not session_file.exists():
                self.logger.debug("No saved session found")
                return False

            with open(session_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            # Add cookies
            cookies = session_data.get("cookies", [])
            if cookies:
                context.add_cookies(cookies)
                self.logger.info(f"Loaded {len(cookies)} cookies from session")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Failed to load session: {e}")
            return False

    def clear_session(self) -> bool:
        """Clear saved session (for re-authentication)."""
        try:
            session_file = self.session_dir / "browser_session.json"
            if session_file.exists():
                session_file.unlink()
                self.logger.info("Session cleared")
            return True
        except Exception as e:
            self.logger.error(f"Failed to clear session: {e}")
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Facebook/Instagram Monitor
# ─────────────────────────────────────────────────────────────────────────────


class SocialMediaMonitor:
    """Monitors Facebook and Instagram for messages."""

    def __init__(self, logger: logging.Logger, session_manager: SessionManager) -> None:
        self.logger = logger
        self.session_manager = session_manager
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.error_recovery = ErrorRecoveryManager("fb_ig_watcher", logger)

    @retry_with_backoff(max_retries=3, base_delay=2.0, max_delay=30.0, logger=None)
    def start_browser(self) -> bool:
        """Start Playwright browser with retry support."""
        try:
            self.playwright = sync_playwright().start()

            # Launch browser
            browser = self.playwright.chromium.launch(
                headless=HEADLESS,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            # Create context with user agent
            self.browser = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720},
            )

            # Load saved session
            if self.session_manager.load_session(self.browser):
                self.logger.info("Session loaded successfully")
            else:
                self.logger.info("No saved session, will need to login")

            self.page = self.browser.new_page()
            self.logger.info("Browser started")
            self.error_recovery.record_success()
            return True

        except Exception as e:
            self.error_recovery.record_error(e, ErrorSeverity.HIGH, {"step": "start_browser"}, retry=True)
            self.logger.exception(f"Failed to start browser: {e}")
            raise  # Re-raise for retry decorator

    def stop_browser(self) -> None:
        """Stop the browser."""
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            self.logger.info("Browser stopped")
        except Exception as e:
            self.logger.error(f"Error stopping browser: {e}")

    def check_facebook_messages(self) -> list[SocialMessage]:
        """Check Facebook Messenger for new messages."""
        messages = []

        try:
            if not self.page:
                return messages

            self.logger.info("Checking Facebook messages...")

            # Navigate to messages
            self.page.goto(FACEBOOK_MESSAGES_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)  # Wait for page to load

            # Check if logged in (look for message threads)
            if not self._is_facebook_logged_in():
                self.logger.warning("Not logged into Facebook")
                return messages

            # Save session if newly logged in
            self.session_manager.save_session(self.browser)

            # Extract messages
            messages = self._extract_facebook_messages()

        except Exception as e:
            self.logger.error(f"Error checking Facebook: {e}")

        return messages

    def _is_facebook_logged_in(self) -> bool:
        """Check if logged into Facebook."""
        try:
            # Check for login indicators
            url = self.page.url
            if "login" in url.lower():
                return False

            # Check for message threads or inbox
            return True

        except Exception:
            return False

    def _extract_facebook_messages(self) -> list[SocialMessage]:
        """Extract messages from Facebook Messenger."""
        messages = []

        try:
            # Try to find message elements (selectors may need adjustment)
            message_selectors = [
                "[data-visualcompletion='css-v1']",
                ".a8c37x1j",
                "[class*='message']",
            ]

            for selector in message_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    for elem in elements[-10:]:  # Last 10 messages
                        try:
                            content = elem.inner_text(timeout=1000)
                            if content and len(content) > 5:
                                msg = self._create_social_message(
                                    platform="facebook",
                                    content=content,
                                    sender="Facebook User",
                                )
                                if msg:
                                    messages.append(msg)
                        except Exception:
                            continue
                    if messages:
                        break
                except Exception:
                    continue

        except Exception as e:
            self.logger.debug(f"Error extracting messages: {e}")

        return messages

    def check_instagram_messages(self) -> list[SocialMessage]:
        """Check Instagram Direct for new messages."""
        messages = []

        try:
            if not self.page:
                return messages

            self.logger.info("Checking Instagram messages...")

            # Navigate to Instagram
            self.page.goto(INSTAGRAM_MESSAGES_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            # Check if logged in
            if not self._is_instagram_logged_in():
                self.logger.warning("Not logged into Instagram")
                return messages

            # Save session
            self.session_manager.save_session(self.browser)

            # Extract messages
            messages = self._extract_instagram_messages()

        except Exception as e:
            self.logger.error(f"Error checking Instagram: {e}")

        return messages

    def _is_instagram_logged_in(self) -> bool:
        """Check if logged into Instagram."""
        try:
            url = self.page.url
            if "login" in url.lower() or "accounts/login" in url:
                return False
            return True
        except Exception:
            return False

    def _extract_instagram_messages(self) -> list[SocialMessage]:
        """Extract messages from Instagram Direct."""
        messages = []

        try:
            # Try to find message elements
            message_selectors = [
                "[class*='message']",
                ".x1n2onr6",
                ".x1lliihq",
            ]

            for selector in message_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    for elem in elements[-10:]:
                        try:
                            content = elem.inner_text(timeout=1000)
                            if content and len(content) > 5:
                                msg = self._create_social_message(
                                    platform="instagram",
                                    content=content,
                                    sender="Instagram User",
                                )
                                if msg:
                                    messages.append(msg)
                        except Exception:
                            continue
                    if messages:
                        break
                except Exception:
                    continue

        except Exception as e:
            self.logger.debug(f"Error extracting Instagram messages: {e}")

        return messages

    def _create_social_message(
        self, platform: str, content: str, sender: str
    ) -> Optional[SocialMessage]:
        """Create a SocialMessage if keywords are found."""
        content_lower = content.lower()

        # Find matching keywords
        keywords_found = [k for k in KEYWORDS if k in content_lower]

        if not keywords_found:
            return None

        # Determine priority
        priority = self._determine_priority(content_lower, keywords_found)

        return SocialMessage(
            platform=platform,
            message_id=f"{platform}_{int(datetime.now().timestamp())}",
            sender=sender,
            content=content[:500],  # Limit content length
            timestamp=datetime.now(),
            keywords_found=keywords_found,
            priority=priority,
            url=FACEBOOK_MESSAGES_URL if platform == "facebook" else INSTAGRAM_MESSAGES_URL,
        )

    def _determine_priority(self, content: str, keywords: list[str]) -> str:
        """Determine message priority."""
        urgent_indicators = ["urgent", "asap", "immediately", "need"]

        if any(ind in content for ind in urgent_indicators):
            return "P0"
        elif "sales" in keywords:
            return "P1"
        elif "client" in keywords or "project" in keywords:
            return "P2"
        return "P3"


# ─────────────────────────────────────────────────────────────────────────────
# Task File Manager
# ─────────────────────────────────────────────────────────────────────────────


class TaskFileManager:
    """Handles creation of task markdown files."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)

    def create_task_file(self, message: SocialMessage) -> Optional[Path]:
        """Create a task file from social media message."""
        try:
            # Generate filename
            timestamp = message.timestamp.strftime("%Y-%m-%d_%H-%M-%S")
            platform = message.platform
            keywords_str = "_".join(message.keywords_found)
            filename = f"{timestamp}_{platform}_{keywords_str}.md"
            filepath = NEEDS_ACTION_DIR / filename

            # Handle duplicates
            counter = 1
            while filepath.exists():
                filename = f"{timestamp}_{platform}_{keywords_str}_{counter}.md"
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

    def _generate_content(self, message: SocialMessage) -> str:
        """Generate markdown content with YAML frontmatter."""
        timestamp_str = message.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        keywords_str = ", ".join(message.keywords_found)

        # Generate summary
        summary = self._generate_summary(message)

        return f"""---
type: social_media_message
platform: {message.platform}
sender: {message.sender}
received: {timestamp_str}
priority: {message.priority}
status: pending
keywords: {keywords_str}
message_id: {message.message_id}
url: {message.url}
---

# {'📘' if message.platform == 'facebook' else '📷'} {message.platform.title()} Message

## Details

| Field | Value |
|-------|-------|
| **Platform** | {message.platform.title()} |
| **Sender** | {message.sender} |
| **Received** | {timestamp_str} |
| **Priority** | {message.priority} |
| **Keywords** | {keywords_str} |
| **Status** | 🟡 Pending |

---

## Message Content

{message.content}

---

## AI Summary

{summary}

---

## Suggested Actions

- [ ] Review message content
- [ ] Identify business opportunity
- [ ] Draft appropriate response
- [ ] Follow up via platform
- [ ] Mark as processed

---

## Response Draft

*Awaiting Social Summary Generator skill to draft response*

---

*Created by Facebook/Instagram Watcher • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    def _generate_summary(self, message: SocialMessage) -> str:
        """Generate a brief summary of the message."""
        content = message.content

        # Extract key information
        has_sales = "sales" in message.keywords_found
        has_client = "client" in message.keywords_found
        has_project = "project" in message.keywords_found

        summary_parts = []

        if has_sales:
            summary_parts.append("Potential sales inquiry detected")
        if has_client:
            summary_parts.append("Client-related message")
        if has_project:
            summary_parts.append("Project discussion mentioned")

        if summary_parts:
            summary = ". ".join(summary_parts) + "."
        else:
            summary = "Business-related message detected."

        # Add content preview
        first_sentence = content.split(".")[0][:100]
        summary += f" Preview: {first_sentence}..."

        return summary


# ─────────────────────────────────────────────────────────────────────────────
# Facebook/Instagram Watcher (Main Class)
# ─────────────────────────────────────────────────────────────────────────────


class FacebookInstagramWatcher:
    """Main Facebook/Instagram watcher class."""

    def __init__(self) -> None:
        self.logger = setup_logging()
        self.session_manager = SessionManager(self.logger, SESSION_DIR)
        self.monitor = SocialMediaMonitor(self.logger, self.session_manager)
        self.task_manager = TaskFileManager(self.logger)
        self.running = False
        self.processed_ids: set[str] = set()

    def start(self) -> None:
        """Start the Facebook/Instagram watcher."""
        self.logger.info("=" * 60)
        self.logger.info("FACEBOOK/INSTAGRAM WATCHER STARTING")
        self.logger.info(f"Check Interval: {CHECK_INTERVAL}s")
        self.logger.info(f"Keywords: {', '.join(KEYWORDS)}")
        self.logger.info(f"Session Dir: {SESSION_DIR}")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  📱 FACEBOOK/INSTAGRAM WATCHER")
        print(f"  Checking every {CHECK_INTERVAL}s")
        print(f"  Keywords: {', '.join(KEYWORDS)}")
        print(f"  Press Ctrl+C to stop")
        print(f"{'=' * 60}\n")

        # Start browser
        if not self.monitor.start_browser():
            self.logger.error("Failed to start browser. Exiting.")
            print("\n❌ Failed to start browser. Check Playwright installation.\n")
            print("Run: playwright install chromium\n")
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
                self.logger.info(f"Check #{check_count}")

                # Check Facebook
                fb_messages = self.monitor.check_facebook_messages()
                for msg in fb_messages:
                    if msg.message_id not in self.processed_ids:
                        self._process_message(msg)

                # Check Instagram
                ig_messages = self.monitor.check_instagram_messages()
                for msg in ig_messages:
                    if msg.message_id not in self.processed_ids:
                        self._process_message(msg)

                time.sleep(CHECK_INTERVAL)

            except Exception as e:
                self.logger.exception(f"Error in loop: {e}")
                time.sleep(CHECK_INTERVAL)

    def _process_message(self, message: SocialMessage) -> None:
        """Process a single message."""
        self.logger.info(f"Processing {message.platform} message with keywords: {message.keywords_found}")

        # Create task file
        filepath = self.task_manager.create_task_file(message)
        if filepath:
            self.processed_ids.add(message.message_id)
            print(f"\n📬 New {message.platform} message task: {filepath.name}")
            self.logger.info(f"Created task file: {filepath.name}")

    def _shutdown(self) -> None:
        """Perform graceful shutdown."""
        self.monitor.stop_browser()

        self.logger.info("=" * 60)
        self.logger.info("FACEBOOK/INSTAGRAM WATCHER STOPPED")
        self.logger.info(f"Total processed: {len(self.processed_ids)}")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  🛑 FACEBOOK/INSTAGRAM WATCHER STOPPED")
        print(f"  Processed: {len(self.processed_ids)} messages")
        print(f"{'=' * 60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Main entry point."""
    # Fix Windows console encoding
    if sys.platform == "win32":
        os.system("chcp 65001 >nul")
        sys.stdout.reconfigure(encoding="utf-8")

    watcher = FacebookInstagramWatcher()
    watcher.start()


if __name__ == "__main__":
    main()
