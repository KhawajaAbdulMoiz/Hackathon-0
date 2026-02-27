#!/usr/bin/env python3
"""
Vault Watcher - AI Employee Inbox Monitor

Monitors the Inbox folder for new files and automatically moves them
to Needs_Action, logging all actions for audit purposes.

Python 3.13+ | Uses watchdog library
"""

import logging
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Final

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

VAULT_ROOT: Final[Path] = Path(__file__).parent.resolve()
INBOX_DIR: Final[Path] = VAULT_ROOT / "Inbox"
NEEDS_ACTION_DIR: Final[Path] = VAULT_ROOT / "Needs_Action"
LOGS_DIR: Final[Path] = VAULT_ROOT / "Logs"

POLL_INTERVAL: Final[float] = 1.0  # seconds
LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# ─────────────────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────────────────


def setup_logging() -> logging.Logger:
    """Configure logging with both file and console handlers."""
    logger = logging.getLogger("vault_watcher")
    logger.setLevel(logging.DEBUG)

    # Console handler (INFO level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    # File handler (DEBUG level)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"watcher_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# ─────────────────────────────────────────────────────────────────────────────
# Event Handler
# ─────────────────────────────────────────────────────────────────────────────


class InboxEventHandler(FileSystemEventHandler):
    """Handles file system events in the Inbox folder."""

    def __init__(self, logger: logging.Logger) -> None:
        super().__init__()
        self.logger = logger
        self.processed_files: set[str] = set()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Skip hidden files and temporary files
        if file_path.name.startswith(".") or file_path.suffix == ".tmp":
            return

        # Debounce: skip if already processed (handles rapid successive events)
        if str(file_path) in self.processed_files:
            return

        self.process_file(file_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move events (in case file is moved into Inbox)."""
        if event.is_directory:
            return

        dest_path = Path(event.dest_path)

        if dest_path.name.startswith(".") or dest_path.suffix == ".tmp":
            return

        if str(dest_path) in self.processed_files:
            return

        self.process_file(dest_path)

    def process_file(self, file_path: Path) -> None:
        """Process a new file: move to Needs_Action and log."""
        self.logger.info(f"📥 New file detected: {file_path.name}")

        try:
            # Validate file exists and is readable
            if not file_path.exists():
                self.logger.error(f"File no longer exists: {file_path}")
                return

            if not file_path.is_file():
                self.logger.warning(f"Not a file, skipping: {file_path}")
                return

            # Generate destination path
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            dest_name = f"{timestamp}_{file_path.name}"
            dest_path = NEEDS_ACTION_DIR / dest_name

            # Handle duplicate filenames
            if dest_path.exists():
                dest_name = f"{timestamp}_{file_path.stem}_{file_path.suffix}"
                dest_path = NEEDS_ACTION_DIR / dest_name

            # Move file
            shutil.move(str(file_path), str(dest_path))

            # Log action
            self.logger.info(f"✅ Moved to: {dest_path.name}")
            self._write_action_log(file_path.name, dest_path.name)

            # Mark as processed
            self.processed_files.add(str(file_path))

            # Print event summary
            print(f"\n{'─' * 60}")
            print(f"📋 TASK RECEIVED")
            print(f"   Original: {file_path.name}")
            print(f"   New:      {dest_path.name}")
            print(f"   Time:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'─' * 60}\n")

        except PermissionError as e:
            self.logger.error(f"Permission denied: {e}")
        except shutil.Error as e:
            self.logger.error(f"Shutil error: {e}")
        except OSError as e:
            self.logger.error(f"OS error: {e}")
        except Exception as e:
            self.logger.exception(f"Unexpected error processing file: {e}")

    def _write_action_log(self, original_name: str, new_name: str) -> None:
        """Write detailed action log entry."""
        log_entry = f"""
## [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Inbox → Needs_Action

**Action:** File moved from Inbox to Needs_Action
**Original File:** {original_name}
**New File:** {new_name}
**Status:** Success
**Trigger:** Watcher auto-processing
"""
        action_log_file = LOGS_DIR / "watcher_actions.md"

        # Append to existing log or create new
        if action_log_file.exists():
            with open(action_log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        else:
            with open(action_log_file, "w", encoding="utf-8") as f:
                f.write("# Watcher Action Log\n\n")
                f.write(f"*Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
                f.write(log_entry)


# ─────────────────────────────────────────────────────────────────────────────
# Vault Watcher Class
# ─────────────────────────────────────────────────────────────────────────────


class VaultWatcher:
    """Main watcher class for monitoring the AI Employee vault."""

    def __init__(self) -> None:
        self.logger = setup_logging()
        self.observer: Observer | None = None
        self.running = False

    def validate_directories(self) -> bool:
        """Ensure required directories exist."""
        required_dirs = [INBOX_DIR, NEEDS_ACTION_DIR, LOGS_DIR]

        for dir_path in required_dirs:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                self.logger.debug(f"Directory verified: {dir_path}")
            except PermissionError as e:
                self.logger.error(f"Cannot create directory {dir_path}: {e}")
                return False
            except OSError as e:
                self.logger.error(f"OS error for directory {dir_path}: {e}")
                return False

        return True

    def start(self) -> None:
        """Start the watcher."""
        if not self.validate_directories():
            self.logger.error("Failed to validate directories. Exiting.")
            sys.exit(1)

        event_handler = InboxEventHandler(self.logger)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(INBOX_DIR), recursive=False)

        try:
            self.observer.start()
            self.running = True
            self.logger.info("🟢 Vault Watcher started")
            self.logger.info(f"📁 Monitoring: {INBOX_DIR}")
            self.logger.info(f"📤 Destination: {NEEDS_ACTION_DIR}")
            self.logger.info("Press Ctrl+C to stop...")
            print(f"\n{'=' * 60}")
            print(f"👁️  VAULT WATCHER ACTIVE")
            print(f"   Watching: {INBOX_DIR}")
            print(f"   {'=' * 60}\n")

            while self.running:
                time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
            self.stop()
        except Exception as e:
            self.logger.exception(f"Watcher error: {e}")
            self.stop()
            sys.exit(1)

    def stop(self) -> None:
        """Stop the watcher gracefully."""
        self.running = False
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
            self.logger.info("🔴 Vault Watcher stopped")
            print(f"\n{'=' * 60}")
            print("Watcher stopped. Goodbye!")
            print(f"{'=' * 60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Main entry point."""
    print(f"\n{'=' * 60}")
    print("  AI EMPLOYEE VAULT WATCHER")
    print(f"  Vault Root: {VAULT_ROOT}")
    print(f"{'=' * 60}\n")

    watcher = VaultWatcher()
    watcher.start()


if __name__ == "__main__":
    main()
