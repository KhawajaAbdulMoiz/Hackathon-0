#!/usr/bin/env python3
"""
Error Recovery Utilities - AI Employee Gold Tier

Provides reusable error handling, exponential backoff retry, and graceful degradation
for all watchers and skills.

Features:
- Exponential backoff retry (max 3 retries, 1-60s delay)
- Error logging to /Logs/error_[component]_[date].log
- Graceful degradation on failures
- Error report generation to /Errors/skill_error_[date].md

Usage:
    from tools.error_recovery import retry_with_backoff, ErrorLogger, GracefulDegradation
"""

import logging
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Final, Optional, TypeVar

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

VAULT_ROOT: Final[Path] = Path(__file__).parent.parent.resolve()
LOGS_DIR: Final[Path] = VAULT_ROOT / "Logs"
ERRORS_DIR: Final[Path] = VAULT_ROOT / "Errors"
PLANS_DIR: Final[Path] = VAULT_ROOT / "Plans"

# Retry configuration
MAX_RETRIES: Final[int] = 3
BASE_DELAY: Final[float] = 1.0  # seconds
MAX_DELAY: Final[float] = 60.0  # seconds
EXPONENTIAL_BASE: Final[int] = 2

# Error types that should trigger retry
RETRYABLE_ERRORS: Final[tuple[type, ...]] = (
    ConnectionError,
    TimeoutError,
    OSError,
    KeyboardInterrupt,
)

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# ─────────────────────────────────────────────────────────────────────────────
# Type Variables
# ─────────────────────────────────────────────────────────────────────────────

T = TypeVar("T")

# ─────────────────────────────────────────────────────────────────────────────
# Error Severity Levels
# ─────────────────────────────────────────────────────────────────────────────


class ErrorSeverity(Enum):
    """Severity levels for errors."""

    LOW = auto()  # Can be ignored, log only
    MEDIUM = auto()  # Should be handled, degrade gracefully
    HIGH = auto()  # Critical, requires immediate attention
    CRITICAL = auto()  # System failure, stop execution


# ─────────────────────────────────────────────────────────────────────────────
# Error Data Class
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ErrorRecord:
    """Represents a recorded error."""

    component: str
    error_type: str
    message: str
    traceback: str
    severity: ErrorSeverity
    timestamp: datetime = field(default_factory=datetime.now)
    context: dict = field(default_factory=dict)
    recovered: bool = False
    recovery_action: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Error Logger
# ─────────────────────────────────────────────────────────────────────────────


class ErrorLogger:
    """Handles error logging to files."""

    def __init__(self, component_name: str) -> None:
        self.component_name = component_name
        self.date_str = datetime.now().strftime("%Y-%m-%d")
        self.log_file = LOGS_DIR / f"error_{component_name}_{self.date_str}.log"
        self.error_records: list[ErrorRecord] = []

        # Ensure directories exist
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        ERRORS_DIR.mkdir(parents=True, exist_ok=True)

    def log_error(
        self,
        error: Exception,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[dict] = None,
    ) -> ErrorRecord:
        """Log an error to file and memory."""
        record = ErrorRecord(
            component=self.component_name,
            error_type=type(error).__name__,
            message=str(error),
            traceback=traceback.format_exc(),
            severity=severity,
            context=context or {},
        )

        self.error_records.append(record)
        self._write_to_log(record)

        return record

    def _write_to_log(self, record: ErrorRecord) -> None:
        """Write error record to log file."""
        timestamp = record.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        severity_str = record.severity.name

        log_entry = f"""
{'=' * 60}
[{timestamp}] [{severity_str}] {record.component}
{'=' * 60}
Error Type: {record.error_type}
Message: {record.message}
Context: {record.context}

Traceback:
{record.traceback}
{'=' * 60}

"""

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)

    def write_error_report(self) -> Optional[Path]:
        """Write comprehensive error report to /Errors/."""
        if not self.error_records:
            return None

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        report_file = ERRORS_DIR / f"skill_error_{self.component_name}_{timestamp}.md"

        content = self._generate_report_content()

        with open(report_file, "w", encoding="utf-8") as f:
            f.write(content)

        return report_file

    def _generate_report_content(self) -> str:
        """Generate markdown error report content."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Group errors by severity
        critical_errors = [r for r in self.error_records if r.severity == ErrorSeverity.CRITICAL]
        high_errors = [r for r in self.error_records if r.severity == ErrorSeverity.HIGH]
        medium_errors = [r for r in self.error_records if r.severity == ErrorSeverity.MEDIUM]
        low_errors = [r for r in self.error_records if r.severity == ErrorSeverity.LOW]

        return f"""# 🚨 Error Report: {self.component_name}

**Generated:** {timestamp}
**Total Errors:** {len(self.error_records)}
**Critical:** {len(critical_errors)} | **High:** {len(high_errors)} | **Medium:** {len(medium_errors)} | **Low:** {len(low_errors)}

---

## Summary

| Severity | Count | Recovered |
|----------|-------|-----------|
| 🔴 Critical | {len(critical_errors)} | {sum(1 for r in critical_errors if r.recovered)} |
| 🟠 High | {len(high_errors)} | {sum(1 for r in high_errors if r.recovered)} |
| 🟡 Medium | {len(medium_errors)} | {sum(1 for r in medium_errors if r.recovered)} |
| 🟢 Low | {len(low_errors)} | {sum(1 for r in low_errors if r.recovered)} |

---

## Error Details

""" + self._format_error_details() + f"""

---

## Recovery Recommendations

{self._generate_recommendations()}

---

*Generated by Error Recovery System • {timestamp}*
"""

    def _format_error_details(self) -> str:
        """Format individual error details."""
        details = []

        for i, record in enumerate(self.error_records, 1):
            severity_emoji = {
                ErrorSeverity.CRITICAL: "🔴",
                ErrorSeverity.HIGH: "🟠",
                ErrorSeverity.MEDIUM: "🟡",
                ErrorSeverity.LOW: "🟢",
            }.get(record.severity, "⚪")

            recovered_str = "✅ Recovered" if record.recovered else "❌ Not Recovered"

            details.append(f"""
### Error {i}: {record.error_type} {severity_emoji}

- **Component:** {record.component}
- **Time:** {record.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
- **Message:** {record.message}
- **Status:** {recovered_str}
- **Recovery Action:** {record.recovery_action or 'None'}

<details>
<summary>Full Traceback</summary>

```
{record.traceback}
```

</details>

---
""")

        return "\n".join(details)

    def _generate_recommendations(self) -> str:
        """Generate recovery recommendations."""
        recommendations = []

        # Check for common patterns
        error_types = [r.error_type for r in self.error_records]

        if "TimeoutError" in error_types or "ConnectionError" in error_types:
            recommendations.append("- 🌐 **Network Issues:** Check internet connection and API endpoints")

        if "AuthenticationError" in error_types or "Unauthorized" in error_types:
            recommendations.append("- 🔐 **Authentication:** Refresh credentials/tokens")

        if "FileNotFoundError" in error_types:
            recommendations.append("- 📁 **File Issues:** Verify file paths and permissions")

        if "MemoryError" in error_types:
            recommendations.append("- 💾 **Memory:** Reduce batch sizes or restart process")

        critical_count = sum(1 for r in self.error_records if r.severity == ErrorSeverity.CRITICAL)
        if critical_count > 0:
            recommendations.append(f"- ⚠️ **Critical:** {critical_count} critical error(s) require immediate attention")

        if not recommendations:
            recommendations.append("- ✅ No specific recommendations - errors appear transient")

        return "\n".join(recommendations)


# ─────────────────────────────────────────────────────────────────────────────
# Retry with Exponential Backoff
# ─────────────────────────────────────────────────────────────────────────────


def retry_with_backoff(
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY,
    max_delay: float = MAX_DELAY,
    exponential_base: int = EXPONENTIAL_BASE,
    retryable_errors: tuple[type, ...] = RETRYABLE_ERRORS,
    logger: Optional[logging.Logger] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        retryable_errors: Tuple of error types that should trigger retry
        logger: Optional logger for retry messages

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except retryable_errors as e:
                    last_exception = e

                    if attempt == max_retries:
                        if logger:
                            logger.error(f"{func.__name__} failed after {max_retries} retries: {e}")
                        raise

                    # Calculate delay with exponential backoff and jitter
                    delay = min(
                        base_delay * (exponential_base ** attempt) + (time.time() % 1),
                        max_delay,
                    )

                    if logger:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )

                    time.sleep(delay)

                except Exception as e:
                    # Non-retryable error - raise immediately
                    if logger:
                        logger.error(f"{func.__name__} failed with non-retryable error: {e}")
                    raise

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry loop exit")

        return wrapper

    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# Graceful Degradation
# ─────────────────────────────────────────────────────────────────────────────


class GracefulDegradation:
    """Handles graceful degradation on failures."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger
        self.degradation_actions: list[dict] = []

    def handle_failure(
        self,
        error: Exception,
        component: str,
        fallback_action: str,
        context: Optional[dict] = None,
    ) -> dict:
        """
        Handle a failure with graceful degradation.

        Args:
            error: The exception that occurred
            component: Name of the failing component
            fallback_action: Description of fallback action taken
            context: Additional context about the failure

        Returns:
            Dictionary describing the degradation action
        """
        action = {
            "component": component,
            "error": str(error),
            "fallback_action": fallback_action,
            "timestamp": datetime.now().isoformat(),
            "context": context or {},
        }

        self.degradation_actions.append(action)

        if self.logger:
            self.logger.warning(
                f"{component} degraded gracefully: {fallback_action} (error: {error})"
            )

        return action

    def create_manual_action_plan(
        self,
        failed_operation: str,
        error: Exception,
        suggested_actions: list[str],
        priority: str = "P2",
    ) -> Optional[Path]:
        """
        Create a manual action plan in /Plans/ when automated operation fails.

        Args:
            failed_operation: Description of what failed
            error: The exception that occurred
            suggested_actions: List of suggested manual actions
            priority: Priority level (P0-P3)

        Returns:
            Path to created plan file, or None if creation failed
        """
        try:
            PLANS_DIR.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"manual_action_{failed_operation.replace(' ', '_')}_{timestamp}.md"
            filepath = PLANS_DIR / filename

            content = self._generate_manual_action_plan(
                failed_operation, error, suggested_actions, priority
            )

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            if self.logger:
                self.logger.info(f"Created manual action plan: {filepath}")

            return filepath

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to create manual action plan: {e}")
            return None

    def _generate_manual_action_plan(
        self,
        failed_operation: str,
        error: Exception,
        suggested_actions: list[str],
        priority: str,
    ) -> str:
        """Generate markdown content for manual action plan."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        actions_md = "\n".join(f"- [ ] {action}" for action in suggested_actions)

        priority_badge = {
            "P0": "🔴 P0 - Critical",
            "P1": "🟠 P1 - High",
            "P2": "🔵 P2 - Normal",
            "P3": "⚪ P3 - Low",
        }.get(priority, f"🔵 {priority}")

        return f"""---
type: manual_action_plan
created: {timestamp}
priority: {priority}
status: pending
failed_operation: {failed_operation}
error_type: {type(error).__name__}
---

# ⚠️ Manual Action Required

**Created:** {timestamp}
**Priority:** {priority_badge}
**Status:** 🟡 Pending Manual Intervention

---

## Failed Operation

{failed_operation}

---

## Error Details

- **Error Type:** {type(error).__name__}
- **Error Message:** {str(error)}
- **Time:** {timestamp}

---

## Suggested Manual Actions

{actions_md}

---

## Context

This action plan was automatically generated when an automated operation failed.
The system attempted to recover gracefully but human intervention is required.

---

## Resolution

Once manual actions are complete:

1. Move this file to `/Done/`
2. Document what was done
3. Update any affected systems

---

*Generated by Graceful Degradation System • {timestamp}*
"""


# ─────────────────────────────────────────────────────────────────────────────
# Error Recovery Manager (Main Class)
# ─────────────────────────────────────────────────────────────────────────────


class ErrorRecoveryManager:
    """Centralized error recovery management for components."""

    def __init__(self, component_name: str, logger: Optional[logging.Logger] = None) -> None:
        self.component_name = component_name
        self.logger = logger
        self.error_logger = ErrorLogger(component_name)
        self.degradation = GracefulDegradation(logger)
        self.retry_count = 0
        self.success_count = 0

    def record_success(self) -> None:
        """Record a successful operation."""
        self.success_count += 1

    def record_error(
        self,
        error: Exception,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[dict] = None,
        retry: bool = False,
    ) -> ErrorRecord:
        """Record an error."""
        if retry:
            self.retry_count += 1

        record = self.error_logger.log_error(error, severity, context)
        return record

    def handle_with_degradation(
        self,
        error: Exception,
        fallback_action: str,
        context: Optional[dict] = None,
    ) -> dict:
        """Handle error with graceful degradation."""
        return self.degradation.handle_failure(error, self.component_name, fallback_action, context)

    def create_manual_action(
        self,
        failed_operation: str,
        error: Exception,
        suggested_actions: list[str],
        priority: str = "P2",
    ) -> Optional[Path]:
        """Create manual action plan for failed operation."""
        return self.degradation.create_manual_action_plan(
            failed_operation, error, suggested_actions, priority
        )

    def write_error_report(self) -> Optional[Path]:
        """Write comprehensive error report."""
        return self.error_logger.write_error_report()

    def get_stats(self) -> dict:
        """Get recovery statistics."""
        return {
            "component": self.component_name,
            "success_count": self.success_count,
            "retry_count": self.retry_count,
            "error_count": len(self.error_logger.error_records),
            "recovered_count": sum(1 for r in self.error_logger.error_records if r.recovered),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────────────────────────────────────


def safe_execute(
    func: Callable[..., T],
    *args: Any,
    default: T = None,
    logger: Optional[logging.Logger] = None,
    **kwargs: Any,
) -> Optional[T]:
    """
    Safely execute a function, returning default on error.

    Args:
        func: Function to execute
        *args: Positional arguments for function
        default: Default value to return on error
        logger: Optional logger
        **kwargs: Keyword arguments for function

    Returns:
        Function result or default value
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if logger:
            logger.debug(f"Safe execute caught error in {func.__name__}: {e}")
        return default


def is_retryable_error(error: Exception) -> bool:
    """Check if an error is retryable."""
    return isinstance(error, RETRYABLE_ERRORS)


def calculate_backoff_delay(
    attempt: int,
    base_delay: float = BASE_DELAY,
    max_delay: float = MAX_DELAY,
    exponential_base: int = EXPONENTIAL_BASE,
) -> float:
    """
    Calculate backoff delay for given attempt.

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation

    Returns:
        Delay in seconds with jitter
    """
    import random

    delay = min(base_delay * (exponential_base ** attempt), max_delay)
    jitter = random.uniform(0, delay * 0.1)  # 10% jitter
    return delay + jitter


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point (for testing)
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Test error recovery utilities."""
    print("Testing Error Recovery Utilities...")

    # Test error logger
    error_logger = ErrorLogger("test_component")
    try:
        raise ValueError("Test error")
    except Exception as e:
        record = error_logger.log_error(e, ErrorSeverity.MEDIUM, {"test": True})
        print(f"Logged error: {record.error_type} - {record.message}")

    # Test retry decorator
    @retry_with_backoff(max_retries=2, base_delay=0.1)
    def flaky_function():
        raise ConnectionError("Simulated network error")

    try:
        flaky_function()
    except ConnectionError:
        print("Retry decorator working correctly (expected failure)")

    # Test graceful degradation
    degradation = GracefulDegradation()
    try:
        raise TimeoutError("API timeout")
    except Exception as e:
        action = degradation.handle_failure(
            e, "API Client", "Using cached data instead"
        )
        print(f"Degradation action: {action['fallback_action']}")

    # Test manual action plan
    try:
        raise RuntimeError("MCP server unavailable")
    except Exception as e:
        plan_path = degradation.create_manual_action_plan(
            "MCP API Call",
            e,
            [
                "Check MCP server status",
                "Restart MCP server if needed",
                "Manually perform the operation",
                "Document outcome",
            ],
            "P1",
        )
        if plan_path:
            print(f"Manual action plan created: {plan_path}")

    print("\n✅ Error Recovery Utilities test complete!")


if __name__ == "__main__":
    # Fix Windows console encoding
    if sys.platform == "win32":
        os.system("chcp 65001 >nul")
        sys.stdout.reconfigure(encoding="utf-8")

    main()
