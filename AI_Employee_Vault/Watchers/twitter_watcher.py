#!/usr/bin/env python3
"""
Twitter (X) Watcher - AI Employee Social Media Monitor

Monitors Twitter (X) for DMs, tweets, and notifications with business keywords
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
│ pm2 start twitter_watcher.py --name "twitter-watcher" --interpreter python3│
│                                                                            │
│ # View logs                                                                │
│ pm2 logs twitter-watcher                                                   │
│                                                                            │
│ # Monitor status                                                           │
│ pm2 status                                                                 │
│                                                                            │
│ # Stop                                                                     │
│ pm2 stop twitter-watcher                                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ FIRST-TIME SETUP                                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Run the script manually first to login:                                 │
│    python watchers/twitter_watcher.py                                      │
│                                                                            │
│ 2. Login to Twitter (X) when browser opens                                 │
│ 3. Session will be saved to /Watchers/session/twitter/                     │
│ 4. Subsequent runs will use saved session                                  │
│                                                                            │
│ 5. For re-authentication, delete the session folder and re-run             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ TESTING                                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Send a test DM on Twitter (X) with:                                     │
│    - Include keywords: "sales", "client", "project"                        │
│    - Example: "Hi, interested in your sales services for my project"       │
│                                                                            │
│ 2. Or tweet/mention your account with keywords                             │
│                                                                            │
│ 3. Run the script manually first:                                          │
│    python watchers/twitter_watcher.py                                      │
│                                                                            │
│ 4. Check Needs_Action folder for new .md file                              │
│                                                                            │
│ 5. Verify the YAML frontmatter and summary are correct                     │
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
SESSION_DIR: Final[Path] = WATCHERS_DIR / "session" / "twitter"

# Monitoring configuration
CHECK_INTERVAL: Final[float] = 60.0  # seconds
KEYWORDS: Final[list[str]] = ["sales", "client", "project"]

# Platform URLs
TWITTER_URL: Final[str] = "https://twitter.com"
TWITTER_MESSAGES_URL: Final[str] = "https://twitter.com/messages"
TWITTER_NOTIFICATIONS_URL: Final[str] = "https://twitter.com/notifications"
TWITTER_HOME_URL: Final[str] = "https://twitter.com/home"

# Headless mode (set to False for first login to see browser)
HEADLESS: Final[bool] = False

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# ─────────────────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────────────────


def setup_logging() -> logging.Logger:
    """Configure logging with both file and console handlers."""
    logger = logging.getLogger("twitter_watcher")
    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    # File handler
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"twitter_watcher_{datetime.now().strftime('%Y-%m-%d')}.log"
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
class TwitterContent:
    """Represents content from Twitter (DM, tweet, or notification)."""

    content_type: str  # dm, tweet, notification
    content_id: str
    sender: str
    sender_handle: str
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
# Twitter Monitor
# ─────────────────────────────────────────────────────────────────────────────


class TwitterMonitor:
    """Monitors Twitter (X) for DMs, tweets, and notifications."""

    def __init__(self, logger: logging.Logger, session_manager: SessionManager) -> None:
        self.logger = logger
        self.session_manager = session_manager
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.error_recovery = ErrorRecoveryManager("twitter_watcher", logger)

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

    def check_dms(self) -> list[TwitterContent]:
        """Check Twitter Direct Messages with error recovery."""
        contents = []

        try:
            if not self.page:
                return contents

            self.logger.info("Checking Twitter DMs...")

            # Navigate to messages
            self.page.goto(TWITTER_MESSAGES_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            # Check if logged in
            if not self._is_logged_in():
                self.logger.warning("Not logged into Twitter")
                return contents

            # Save session
            self.session_manager.save_session(self.browser)

            # Extract DMs
            contents = self._extract_dms()
            self.error_recovery.record_success()

        except Exception as e:
            self.error_recovery.record_error(e, ErrorSeverity.MEDIUM, {"step": "check_dms"})
            self.logger.error(f"Error checking Twitter DMs: {e}")
            # Graceful degradation - return empty list and continue

        return contents

    def check_notifications(self) -> list[TwitterContent]:
        """Check Twitter notifications (mentions, replies) with error recovery."""
        contents = []

        try:
            if not self.page:
                return contents

            self.logger.info("Checking Twitter notifications...")

            # Navigate to notifications
            self.page.goto(TWITTER_NOTIFICATIONS_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            if not self._is_logged_in():
                self.logger.warning("Not logged into Twitter")
                return contents

            # Extract notifications
            contents = self._extract_notifications()
            self.error_recovery.record_success()

        except Exception as e:
            self.error_recovery.record_error(e, ErrorSeverity.MEDIUM, {"step": "check_notifications"})
            self.logger.error(f"Error checking Twitter notifications: {e}")
            # Graceful degradation - return empty list and continue

        return contents

    def check_home_timeline(self) -> list[TwitterContent]:
        """Check home timeline for mentions."""
        contents = []

        try:
            if not self.page:
                return contents

            self.logger.info("Checking Twitter timeline...")

            # Navigate to home
            self.page.goto(TWITTER_HOME_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            if not self._is_logged_in():
                self.logger.warning("Not logged into Twitter")
                return contents

            # Extract timeline
            contents = self._extract_timeline()

        except Exception as e:
            self.logger.error(f"Error checking Twitter timeline: {e}")

        return contents

    def _is_logged_in(self) -> bool:
        """Check if logged into Twitter."""
        try:
            url = self.page.url
            if "login" in url.lower() or "i/flow/login" in url:
                return False
            return True
        except Exception:
            return False

    def _extract_dms(self) -> list[TwitterContent]:
        """Extract direct messages."""
        contents = []

        try:
            # Try to find message elements (selectors may need adjustment based on Twitter updates)
            message_selectors = [
                "[data-testid='messageEntry']",
                "[class*='message']",
                "article[role='article']",
            ]

            for selector in message_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    for elem in elements[-10:]:  # Last 10 messages
                        try:
                            content = elem.inner_text(timeout=1000)
                            if content and len(content) > 5:
                                twitter_content = self._create_twitter_content(
                                    content_type="dm",
                                    content=content,
                                    sender="Twitter User",
                                )
                                if twitter_content:
                                    contents.append(twitter_content)
                        except Exception:
                            continue
                    if contents:
                        break
                except Exception:
                    continue

        except Exception as e:
            self.logger.debug(f"Error extracting DMs: {e}")

        return contents

    def _extract_notifications(self) -> list[TwitterContent]:
        """Extract notifications (mentions, replies)."""
        contents = []

        try:
            # Try to find notification elements
            notification_selectors = [
                "[data-testid='notification']",
                "article[role='article']",
                "[class*='notification']",
            ]

            for selector in notification_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    for elem in elements[-10:]:
                        try:
                            content = elem.inner_text(timeout=1000)
                            if content and len(content) > 5:
                                # Check if it's a mention or reply
                                if "@" in content or "mentioned" in content.lower():
                                    twitter_content = self._create_twitter_content(
                                        content_type="notification",
                                        content=content,
                                        sender="Twitter User",
                                    )
                                    if twitter_content:
                                        contents.append(twitter_content)
                        except Exception:
                            continue
                    if contents:
                        break
                except Exception:
                    continue

        except Exception as e:
            self.logger.debug(f"Error extracting notifications: {e}")

        return contents

    def _extract_timeline(self) -> list[TwitterContent]:
        """Extract timeline tweets (looking for mentions)."""
        contents = []

        try:
            # Try to find tweet elements
            tweet_selectors = [
                "article[role='article']",
                "[data-testid='tweet']",
            ]

            for selector in tweet_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    for elem in elements[:20]:  # Check first 20 tweets
                        try:
                            content = elem.inner_text(timeout=1000)
                            if content and len(content) > 5:
                                # Check if it's a mention
                                if "@" in content:
                                    twitter_content = self._create_twitter_content(
                                        content_type="tweet",
                                        content=content,
                                        sender="Twitter User",
                                    )
                                    if twitter_content:
                                        contents.append(twitter_content)
                        except Exception:
                            continue
                    if contents:
                        break
                except Exception:
                    continue

        except Exception as e:
            self.logger.debug(f"Error extracting timeline: {e}")

        return contents

    def _create_twitter_content(
        self, content_type: str, content: str, sender: str
    ) -> Optional[TwitterContent]:
        """Create a TwitterContent if keywords are found."""
        content_lower = content.lower()

        # Find matching keywords
        keywords_found = [k for k in KEYWORDS if k in content_lower]

        if not keywords_found:
            return None

        # Determine priority
        priority = self._determine_priority(content_lower, keywords_found)

        # Generate URL based on content type
        if content_type == "dm":
            url = TWITTER_MESSAGES_URL
        elif content_type == "notification":
            url = TWITTER_NOTIFICATIONS_URL
        else:
            url = TWITTER_HOME_URL

        return TwitterContent(
            content_type=content_type,
            content_id=f"twitter_{content_type}_{int(datetime.now().timestamp())}",
            sender=sender,
            sender_handle="@twitteruser",
            content=content[:500],  # Limit content length
            timestamp=datetime.now(),
            keywords_found=keywords_found,
            priority=priority,
            url=url,
        )

    def _determine_priority(self, content: str, keywords: list[str]) -> str:
        """Determine content priority."""
        urgent_indicators = ["urgent", "asap", "immediately", "need", "help"]

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

    def create_task_file(self, content: TwitterContent) -> Optional[Path]:
        """Create a task file from Twitter content."""
        try:
            # Generate filename
            timestamp = content.timestamp.strftime("%Y-%m-%d_%H-%M-%S")
            content_type = content.content_type
            keywords_str = "_".join(content.keywords_found)
            filename = f"{timestamp}_twitter_{content_type}_{keywords_str}.md"
            filepath = NEEDS_ACTION_DIR / filename

            # Handle duplicates
            counter = 1
            while filepath.exists():
                filename = f"{timestamp}_twitter_{content_type}_{keywords_str}_{counter}.md"
                filepath = NEEDS_ACTION_DIR / filename
                counter += 1

            # Generate content
            task_content = self._generate_content(content)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(task_content)

            self.logger.info(f"Created task file: {filename}")
            return filepath

        except Exception as e:
            self.logger.exception(f"Error creating task file: {e}")
            return None

    def _generate_content(self, content: TwitterContent) -> str:
        """Generate markdown content with YAML frontmatter."""
        timestamp_str = content.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        keywords_str = ", ".join(content.keywords_found)

        # Generate summary
        summary = self._generate_summary(content)

        # Determine emoji based on content type
        type_emoji = {"dm": "💬", "tweet": "🐦", "notification": "🔔"}.get(
            content.content_type, "📱"
        )

        return f"""---
type: twitter_content
platform: twitter
content_type: {content.content_type}
sender: {content.sender}
sender_handle: {content.sender_handle}
received: {timestamp_str}
priority: {content.priority}
status: pending
keywords: {keywords_str}
content_id: {content.content_id}
url: {content.url}
---

# {type_emoji} Twitter ({type_emoji.title()})

## Details

| Field | Value |
|-------|-------|
| **Platform** | Twitter (X) |
| **Type** | {content.content_type.title()} |
| **Sender** | {content.sender} ({content.sender_handle}) |
| **Received** | {timestamp_str} |
| **Priority** | {content.priority} |
| **Keywords** | {keywords_str} |
| **Status** | 🟡 Pending |

---

## Content

{content.content}

---

## AI Summary

{summary}

---

## Suggested Actions

- [ ] Review content
- [ ] Identify business opportunity
- [ ] Draft appropriate response
- [ ] Follow up via Twitter
- [ ] Mark as processed

---

## Response Draft

*Awaiting Twitter Post Generator skill to draft response*

---

*Created by Twitter Watcher • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    def _generate_summary(self, content: TwitterContent) -> str:
        """Generate a brief summary of the content."""
        content_text = content.content

        # Extract key information
        has_sales = "sales" in content.keywords_found
        has_client = "client" in content.keywords_found
        has_project = "project" in content.keywords_found

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
            summary = "Business-related content detected."

        # Add content preview
        first_sentence = content_text.split(".")[0][:100]
        summary += f" Preview: {first_sentence}..."

        return summary


# ─────────────────────────────────────────────────────────────────────────────
# Twitter Watcher (Main Class)
# ─────────────────────────────────────────────────────────────────────────────


class TwitterWatcher:
    """Main Twitter (X) watcher class."""

    def __init__(self) -> None:
        self.logger = setup_logging()
        self.session_manager = SessionManager(self.logger, SESSION_DIR)
        self.monitor = TwitterMonitor(self.logger, self.session_manager)
        self.task_manager = TaskFileManager(self.logger)
        self.running = False
        self.processed_ids: set[str] = set()

    def start(self) -> None:
        """Start the Twitter (X) watcher."""
        self.logger.info("=" * 60)
        self.logger.info("TWITTER (X) WATCHER STARTING")
        self.logger.info(f"Check Interval: {CHECK_INTERVAL}s")
        self.logger.info(f"Keywords: {', '.join(KEYWORDS)}")
        self.logger.info(f"Session Dir: {SESSION_DIR}")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  🐦 TWITTER (X) WATCHER")
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

                # Check DMs
                dms = self.monitor.check_dms()
                for dm in dms:
                    if dm.content_id not in self.processed_ids:
                        self._process_content(dm)

                # Check notifications
                notifications = self.monitor.check_notifications()
                for notif in notifications:
                    if notif.content_id not in self.processed_ids:
                        self._process_content(notif)

                # Check timeline
                timeline = self.monitor.check_home_timeline()
                for tweet in timeline:
                    if tweet.content_id not in self.processed_ids:
                        self._process_content(tweet)

                time.sleep(CHECK_INTERVAL)

            except Exception as e:
                self.logger.exception(f"Error in loop: {e}")
                time.sleep(CHECK_INTERVAL)

    def _process_content(self, content: TwitterContent) -> None:
        """Process a single piece of content."""
        self.logger.info(
            f"Processing Twitter {content.content_type} with keywords: {content.keywords_found}"
        )

        # Create task file
        filepath = self.task_manager.create_task_file(content)
        if filepath:
            self.processed_ids.add(content.content_id)
            print(f"\n📬 New Twitter {content.content_type} task: {filepath.name}")
            self.logger.info(f"Created task file: {filepath.name}")

    def _shutdown(self) -> None:
        """Perform graceful shutdown."""
        self.monitor.stop_browser()

        self.logger.info("=" * 60)
        self.logger.info("TWITTER (X) WATCHER STOPPED")
        self.logger.info(f"Total processed: {len(self.processed_ids)}")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  🛑 TWITTER (X) WATCHER STOPPED")
        print(f"  Processed: {len(self.processed_ids)} items")
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

    watcher = TwitterWatcher()
    watcher.start()


if __name__ == "__main__":
    main()
