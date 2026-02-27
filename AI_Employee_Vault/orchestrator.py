#!/usr/bin/env python3
"""
Orchestrator - AI Employee Central Control System

Continuously monitors and coordinates all AI Employee subsystems including
task processing, health monitoring, and system logging.

Python 3.13+ | Production-Ready | Runs Continuously
"""

import logging
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

VAULT_ROOT: Final[Path] = Path(__file__).parent.resolve()
NEEDS_ACTION_DIR: Final[Path] = VAULT_ROOT / "Needs_Action"
LOGS_DIR: Final[Path] = VAULT_ROOT / "Logs"

SCRIPTS_DIR: Final[Path] = Path(__file__).parent.resolve()
TASK_PROCESSOR_SCRIPT: Final[Path] = SCRIPTS_DIR / "task_processor.py"
VAULT_WATCHER_SCRIPT: Final[Path] = SCRIPTS_DIR / "vault_watcher.py"

CHECK_INTERVAL: Final[float] = 10.0  # seconds
HEALTH_LOG_INTERVAL: Final[int] = 6  # log health every 6 checks (1 minute)
MAX_CONSECUTIVE_ERRORS: Final[int] = 5
ERROR_COOLDOWN: Final[float] = 30.0  # seconds before retry after max errors

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SystemHealth:
    """Represents current system health status."""

    status: str
    uptime_seconds: float
    tasks_processed: int
    consecutive_errors: int
    last_check: datetime
    last_task_run: Optional[datetime]
    subsystems: dict[str, str]


# ─────────────────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────────────────


def setup_logging() -> logging.Logger:
    """Configure logging with both file and console handlers."""
    logger = logging.getLogger("orchestrator")
    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    # File handler
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"orchestrator_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# ─────────────────────────────────────────────────────────────────────────────
# Health Monitor
# ─────────────────────────────────────────────────────────────────────────────


class HealthMonitor:
    """Monitors and logs system health."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.start_time = datetime.now()
        self.tasks_processed = 0
        self.consecutive_errors = 0
        self.last_task_run: Optional[datetime] = None
        self.health_log_count = 0

    def get_health(self) -> SystemHealth:
        """Get current system health status."""
        uptime = (datetime.now() - self.start_time).total_seconds()

        # Determine subsystem status
        subsystems = {
            "orchestrator": "🟢 operational",
            "task_processor": "🟢 operational" if self.consecutive_errors < MAX_CONSECUTIVE_ERRORS else "🔴 degraded",
            "vault_watcher": self._check_watcher_status(),
            "filesystem": self._check_filesystem_status(),
        }

        # Overall status
        if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            status = "🔴 degraded"
        elif any("🔴" in s for s in subsystems.values()):
            status = "🟡 warning"
        else:
            status = "🟢 operational"

        return SystemHealth(
            status=status,
            uptime_seconds=uptime,
            tasks_processed=self.tasks_processed,
            consecutive_errors=self.consecutive_errors,
            last_check=datetime.now(),
            last_task_run=self.last_task_run,
            subsystems=subsystems,
        )

    def record_task_completed(self) -> None:
        """Record a successfully completed task."""
        self.tasks_processed += 1
        self.last_task_run = datetime.now()
        self.consecutive_errors = 0

    def record_error(self) -> None:
        """Record an error occurrence."""
        self.consecutive_errors += 1

    def log_health(self) -> None:
        """Log current health status."""
        health = self.get_health()
        uptime_str = self._format_uptime(health.uptime_seconds)

        self.logger.info(
            f"HEALTH | Status: {health.status} | "
            f"Uptime: {uptime_str} | Tasks: {health.tasks_processed} | "
            f"Errors: {health.consecutive_errors}"
        )

        # Write to health log file
        self._write_health_log(health)

        self.health_log_count += 1

    def _write_health_log(self, health: SystemHealth) -> None:
        """Write health status to dedicated log file."""
        health_log = LOGS_DIR / "system_health.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        uptime_str = self._format_uptime(health.uptime_seconds)

        subsystems_md = "\n".join(
            f"- **{name}**: {status}" for name, status in health.subsystems.items()
        )

        entry = f"""
## [{timestamp}] Health Check

| Metric | Value |
|--------|-------|
| Status | {health.status} |
| Uptime | {uptime_str} |
| Tasks Processed | {health.tasks_processed} |
| Consecutive Errors | {health.consecutive_errors} |
| Last Task Run | {health.last_task_run.strftime('%Y-%m-%d %H:%M:%S') if health.last_task_run else 'Never'} |

### Subsystems

{subsystems_md}

---
"""

        is_new = not health_log.exists()

        with open(health_log, "a", encoding="utf-8") as f:
            if is_new:
                f.write("# System Health Log\n\n")
                f.write(f"*Created: {timestamp}*\n")
            f.write(entry)

    def _format_uptime(self, seconds: float) -> str:
        """Format uptime in human-readable format."""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    def _check_watcher_status(self) -> str:
        """Check if vault watcher is running."""
        if VAULT_WATCHER_SCRIPT.exists():
            return "🟢 available"
        return "⚪ not configured"

    def _check_filesystem_status(self) -> str:
        """Check filesystem accessibility."""
        try:
            if VAULT_ROOT.exists() and VAULT_ROOT.is_dir():
                return "🟢 operational"
            return "🔴 inaccessible"
        except Exception:
            return "🔴 error"


# ─────────────────────────────────────────────────────────────────────────────
# Task Processor Runner
# ─────────────────────────────────────────────────────────────────────────────


class TaskProcessorRunner:
    """Runs the task processor script."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def has_tasks(self) -> bool:
        """Check if there are tasks to process."""
        try:
            task_files = list(NEEDS_ACTION_DIR.glob("*.md"))
            return len(task_files) > 0
        except Exception as e:
            self.logger.error(f"Error checking for tasks: {e}")
            return False

    def run_processor(self) -> bool:
        """Run the task processor script."""
        if not TASK_PROCESSOR_SCRIPT.exists():
            self.logger.error(f"Task processor script not found: {TASK_PROCESSOR_SCRIPT}")
            return False

        try:
            self.logger.info("Starting task processor...")

            result = subprocess.run(
                [sys.executable, str(TASK_PROCESSOR_SCRIPT)],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode == 0:
                self.logger.info("Task processor completed successfully")
                self._log_processor_output(result.stdout)
                return True
            else:
                self.logger.error(f"Task processor failed with code {result.returncode}")
                self.logger.error(f"stderr: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            self.logger.error("Task processor timed out (5 minutes)")
            return False
        except Exception as e:
            self.logger.exception(f"Error running task processor: {e}")
            return False

    def _log_processor_output(self, output: str) -> None:
        """Log task processor output."""
        if output.strip():
            for line in output.strip().split("\n"):
                self.logger.debug(f"Processor: {line}")


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator (Main Class)
# ─────────────────────────────────────────────────────────────────────────────


class Orchestrator:
    """Main orchestrator for AI Employee system."""

    def __init__(self) -> None:
        self.logger = setup_logging()
        self.health_monitor = HealthMonitor(self.logger)
        self.processor_runner = TaskProcessorRunner(self.logger)
        self.running = False
        self.check_count = 0

        # Ensure directories exist
        for directory in [VAULT_ROOT, NEEDS_ACTION_DIR, LOGS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        """Start the orchestrator."""
        self.running = True
        self._setup_signal_handlers()

        self.logger.info("=" * 60)
        self.logger.info("AI EMPLOYEE ORCHESTRATOR STARTING")
        self.logger.info(f"Vault Root: {VAULT_ROOT}")
        self.logger.info(f"Check Interval: {CHECK_INTERVAL}s")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  🤖 AI EMPLOYEE ORCHESTRATOR")
        print(f"  Vault: {VAULT_ROOT}")
        print(f"  Interval: {CHECK_INTERVAL}s")
        print(f"  Press Ctrl+C to stop")
        print(f"{'=' * 60}\n")

        try:
            self._run_loop()
        except Exception as e:
            self.logger.exception(f"Orchestrator crashed: {e}")
            self._shutdown()
            sys.exit(1)

    def _run_loop(self) -> None:
        """Main orchestration loop."""
        while self.running:
            try:
                self.check_count += 1

                # Check for and process tasks
                if self.processor_runner.has_tasks():
                    self.logger.info(f"Tasks detected (check #{self.check_count})")
                    success = self.processor_runner.run_processor()

                    if success:
                        self.health_monitor.record_task_completed()
                    else:
                        self.health_monitor.record_error()
                else:
                    self.logger.debug(f"No tasks (check #{self.check_count})")

                # Log health periodically
                if self.check_count % HEALTH_LOG_INTERVAL == 0:
                    self.health_monitor.log_health()

                # Check for error cooldown
                if self.health_monitor.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    self.logger.warning(
                        f"Max errors reached. Cooldown for {ERROR_COOLDOWN}s..."
                    )
                    time.sleep(ERROR_COOLDOWN)

                # Wait for next check
                time.sleep(CHECK_INTERVAL)

            except KeyboardInterrupt:
                self.logger.info("Received interrupt signal")
                break
            except Exception as e:
                self.logger.exception(f"Error in orchestration loop: {e}")
                self.health_monitor.record_error()
                time.sleep(CHECK_INTERVAL)

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _shutdown(self) -> None:
        """Perform graceful shutdown."""
        self.logger.info("=" * 60)
        self.logger.info("ORCHESTRATOR SHUTTING DOWN")

        # Final health log
        self.health_monitor.log_health()

        health = self.health_monitor.get_health()
        uptime_str = self._format_uptime(health.uptime_seconds)

        self.logger.info(f"Final Status: {health.status}")
        self.logger.info(f"Total Uptime: {uptime_str}")
        self.logger.info(f"Tasks Processed: {health.tasks_processed}")
        self.logger.info(f"Total Checks: {self.check_count}")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  🛑 ORCHESTRATOR STOPPED")
        print(f"  Uptime: {uptime_str}")
        print(f"  Tasks Processed: {health.tasks_processed}")
        print(f"{'=' * 60}\n")

    def _format_uptime(self, seconds: float) -> str:
        """Format uptime in human-readable format."""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours}h {minutes}m {secs}s"


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Main entry point."""
    orchestrator = Orchestrator()
    orchestrator.start()


if __name__ == "__main__":
    main()
