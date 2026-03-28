#!/usr/bin/env python3
"""
Audit Logger - AI Employee Gold Tier

Comprehensive audit logging for all AI Employee actions.
Logs every action in JSON format with full traceability.

Features:
- JSON log format with structured fields
- 90-day log retention with automatic cleanup
- Weekly audit summary generation
- Integration with all skills and watchers

Log Format:
{
    "timestamp": "ISO 8601",
    "action_type": "skill_start|skill_end|watcher_check|task_process|etc",
    "actor": "skill_name|watcher_name|user",
    "target": "file_path|task_name|resource",
    "parameters": {...},
    "approval_status": "not_required|pending|approved|rejected",
    "result": "success|failure|partial",
    "duration_ms": 123,
    "error": "error message if any"
}

Usage:
    from tools.audit_logger import AuditLogger
    
    logger = AuditLogger("skill_name")
    logger.log_action("skill_start", "target", {...})
    logger.log_action("skill_end", "target", {...}, result="success")
"""

import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Final, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

VAULT_ROOT: Final[Path] = Path(__file__).parent.parent.resolve()
LOGS_DIR: Final[Path] = VAULT_ROOT / "Logs"
BRIEFINGS_DIR: Final[Path] = VAULT_ROOT / "Briefings"

# Log retention configuration
LOG_RETENTION_DAYS: Final[int] = 90

# Audit log file pattern
AUDIT_LOG_PATTERN: Final[str] = "audit_{date}.jsonl"  # JSON Lines format

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────


class ActionType(Enum):
    """Types of auditable actions."""

    # Skill lifecycle
    SKILL_START = auto()
    SKILL_END = auto()
    SKILL_ERROR = auto()

    # Watcher operations
    WATCHER_START = auto()
    WATCHER_CHECK = auto()
    WATCHER_STOP = auto()
    WATCHER_ERROR = auto()

    # Task processing
    TASK_RECEIVED = auto()
    TASK_CLASSIFIED = auto()
    TASK_PROCESSED = auto()
    TASK_COMPLETED = auto()
    TASK_FAILED = auto()

    # File operations
    FILE_CREATED = auto()
    FILE_MODIFIED = auto()
    FILE_DELETED = auto()
    FILE_MOVED = auto()

    # Approval workflow
    APPROVAL_REQUESTED = auto()
    APPROVAL_GRANTED = auto()
    APPROVAL_REJECTED = auto()

    # API/External calls
    API_CALL = auto()
    API_RESPONSE = auto()
    API_ERROR = auto()

    # System operations
    SYSTEM_START = auto()
    SYSTEM_STOP = auto()
    SYSTEM_ERROR = auto()
    CONFIG_CHANGE = auto()


class ApprovalStatus(Enum):
    """Approval status for actions."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ActionResult(Enum):
    """Result of an action."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    SKIPPED = "skipped"


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AuditEntry:
    """Represents a single audit log entry."""

    timestamp: str
    action_type: str
    actor: str
    target: str
    parameters: dict = field(default_factory=dict)
    approval_status: str = ApprovalStatus.NOT_REQUIRED.value
    result: str = ActionResult.SUCCESS.value
    duration_ms: int = 0
    error: Optional[str] = None
    session_id: str = field(default_factory=lambda: f"session_{int(time.time())}")
    hostname: str = field(default_factory=lambda: os.environ.get("COMPUTERNAME", "unknown"))

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


# ─────────────────────────────────────────────────────────────────────────────
# Audit Logger (Main Class)
# ─────────────────────────────────────────────────────────────────────────────


class AuditLogger:
    """
    Comprehensive audit logger for AI Employee actions.
    
    Usage:
        logger = AuditLogger("skill_name")
        
        # Log start
        logger.log_start("Processing task", {"task_id": "123"})
        
        # Log end
        logger.log_end("Processing task", result="success")
        
        # Or log custom actions
        logger.log_action(ActionType.TASK_PROCESSED, "task.md", {...})
    """

    def __init__(self, actor: str, logger: Optional[logging.Logger] = None) -> None:
        """
        Initialize audit logger.
        
        Args:
            actor: Name of the actor (skill name, watcher name, user)
            logger: Optional Python logger for debug messages
        """
        self.actor = actor
        self.logger = logger
        self.session_id = f"session_{int(time.time())}"
        self.start_time: Optional[float] = None
        self.date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Ensure directories exist
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Get hostname
        self.hostname = os.environ.get("COMPUTERNAME", "unknown")

    def _get_log_file(self) -> Path:
        """Get today's audit log file path."""
        return LOGS_DIR / AUDIT_LOG_PATTERN.format(date=self.date_str)

    def _write_entry(self, entry: AuditEntry) -> None:
        """Write audit entry to log file (JSON Lines format)."""
        log_file = self._get_log_file()
        
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry.to_json() + "\n")
            
            if self.logger:
                self.logger.debug(f"Audit entry logged: {entry.action_type}")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to write audit log: {e}")
            # Don't raise - audit logging failure shouldn't break main functionality

    def log_action(
        self,
        action_type: ActionType | str,
        target: str,
        parameters: Optional[dict] = None,
        approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED,
        result: ActionResult = ActionResult.SUCCESS,
        error: Optional[str] = None,
        duration_ms: int = 0,
    ) -> AuditEntry:
        """
        Log a single audit action.
        
        Args:
            action_type: Type of action (enum or string)
            target: Target of the action (file, task, resource)
            parameters: Additional parameters/context
            approval_status: Approval status if applicable
            result: Result of the action
            error: Error message if failed
            duration_ms: Duration in milliseconds
            
        Returns:
            The created AuditEntry
        """
        if isinstance(action_type, ActionType):
            action_type_str = action_type.name
        else:
            action_type_str = str(action_type)

        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            action_type=action_type_str,
            actor=self.actor,
            target=target,
            parameters=parameters or {},
            approval_status=approval_status.value,
            result=result.value,
            duration_ms=duration_ms,
            error=error,
            session_id=self.session_id,
            hostname=self.hostname,
        )

        self._write_entry(entry)
        return entry

    def log_start(self, target: str, parameters: Optional[dict] = None) -> AuditEntry:
        """Log the start of an operation."""
        self.start_time = time.time()
        return self.log_action(
            ActionType.SKILL_START,
            target,
            parameters,
            result=ActionResult.SUCCESS,
        )

    def log_end(
        self,
        target: str,
        result: ActionResult = ActionResult.SUCCESS,
        error: Optional[str] = None,
        parameters: Optional[dict] = None,
    ) -> AuditEntry:
        """Log the end of an operation."""
        duration_ms = 0
        if self.start_time:
            duration_ms = int((time.time() - self.start_time) * 1000)
            self.start_time = None

        return self.log_action(
            ActionType.SKILL_END,
            target,
            parameters,
            result=result,
            error=error,
            duration_ms=duration_ms,
        )

    def log_error(
        self,
        target: str,
        error: str,
        parameters: Optional[dict] = None,
    ) -> AuditEntry:
        """Log an error."""
        return self.log_action(
            ActionType.SKILL_ERROR,
            target,
            parameters,
            result=ActionResult.FAILURE,
            error=error,
        )

    def log_task_processed(
        self,
        task_name: str,
        classification: str,
        result: ActionResult = ActionResult.SUCCESS,
    ) -> AuditEntry:
        """Log task processing."""
        return self.log_action(
            ActionType.TASK_PROCESSED,
            task_name,
            {"classification": classification},
            result=result,
        )

    def log_approval_request(
        self,
        target: str,
        approval_type: str,
    ) -> AuditEntry:
        """Log approval request."""
        return self.log_action(
            ActionType.APPROVAL_REQUESTED,
            target,
            {"approval_type": approval_type},
            approval_status=ApprovalStatus.PENDING,
        )

    def log_file_operation(
        self,
        operation: str,  # created, modified, deleted, moved
        file_path: str,
        result: ActionResult = ActionResult.SUCCESS,
    ) -> AuditEntry:
        """Log file operation."""
        action_map = {
            "created": ActionType.FILE_CREATED,
            "modified": ActionType.FILE_MODIFIED,
            "deleted": ActionType.FILE_DELETED,
            "moved": ActionType.FILE_MOVED,
        }
        return self.log_action(
            action_map.get(operation, ActionType.FILE_MODIFIED),
            file_path,
            {"operation": operation},
            result=result,
        )

    def cleanup_old_logs(self, retention_days: int = LOG_RETENTION_DAYS) -> int:
        """
        Clean up audit logs older than retention period.
        
        Args:
            retention_days: Number of days to retain logs
            
        Returns:
            Number of files deleted
        """
        deleted_count = 0
        cutoff_date = datetime.now() - timedelta(days=retention_days)

        try:
            for log_file in LOGS_DIR.glob("audit_*.jsonl"):
                # Extract date from filename
                try:
                    date_str = log_file.stem.replace("audit_", "")
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")
                    
                    if file_date < cutoff_date:
                        log_file.unlink()
                        deleted_count += 1
                        if self.logger:
                            self.logger.info(f"Deleted old audit log: {log_file.name}")
                except ValueError:
                    continue  # Skip files with invalid date format

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error cleaning up old logs: {e}")

        return deleted_count

    def get_daily_summary(self, date_str: Optional[str] = None) -> dict:
        """
        Get summary of audit entries for a specific date.
        
        Args:
            date_str: Date string (YYYY-MM-DD), defaults to today
            
        Returns:
            Dictionary with summary statistics
        """
        if date_str is None:
            date_str = self.date_str

        log_file = LOGS_DIR / AUDIT_LOG_PATTERN.format(date=date_str)
        
        if not log_file.exists():
            return {"error": "No audit log found", "date": date_str}

        try:
            entries = []
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))

            # Calculate summary
            summary = {
                "date": date_str,
                "total_actions": len(entries),
                "by_action_type": {},
                "by_actor": {},
                "by_result": {},
                "by_approval_status": {},
                "errors": [],
                "avg_duration_ms": 0,
            }

            durations = []
            for entry in entries:
                # Count by action type
                action = entry.get("action_type", "unknown")
                summary["by_action_type"][action] = summary["by_action_type"].get(action, 0) + 1

                # Count by actor
                actor = entry.get("actor", "unknown")
                summary["by_actor"][actor] = summary["by_actor"].get(actor, 0) + 1

                # Count by result
                result = entry.get("result", "unknown")
                summary["by_result"][result] = summary["by_result"].get(result, 0) + 1

                # Count by approval status
                approval = entry.get("approval_status", "unknown")
                summary["by_approval_status"][approval] = summary["by_approval_status"].get(approval, 0) + 1

                # Collect errors
                if entry.get("error"):
                    summary["errors"].append({
                        "timestamp": entry.get("timestamp"),
                        "actor": entry.get("actor"),
                        "action": entry.get("action_type"),
                        "error": entry.get("error"),
                    })

                # Collect durations
                if entry.get("duration_ms", 0) > 0:
                    durations.append(entry["duration_ms"])

            if durations:
                summary["avg_duration_ms"] = sum(durations) / len(durations)

            return summary

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error generating summary: {e}")
            return {"error": str(e), "date": date_str}

    def get_weekly_summary(self) -> dict:
        """
        Get summary of audit entries for the past 7 days.
        
        Returns:
            Dictionary with weekly summary statistics
        """
        weekly_summary = {
            "period": {
                "start": (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d"),
                "end": datetime.now().strftime("%Y-%m-%d"),
            },
            "daily_totals": {},
            "total_actions": 0,
            "by_action_type": {},
            "by_actor": {},
            "by_result": {},
            "total_errors": 0,
            "unique_sessions": set(),
        }

        for i in range(7):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            daily = self.get_daily_summary(date_str)
            
            if "error" not in daily:
                weekly_summary["daily_totals"][date_str] = daily["total_actions"]
                weekly_summary["total_actions"] += daily["total_actions"]

                # Aggregate action types
                for action, count in daily.get("by_action_type", {}).items():
                    weekly_summary["by_action_type"][action] = \
                        weekly_summary["by_action_type"].get(action, 0) + count

                # Aggregate actors
                for actor, count in daily.get("by_actor", {}).items():
                    weekly_summary["by_actor"][actor] = \
                        weekly_summary["by_actor"].get(actor, 0) + count

                # Aggregate results
                for result, count in daily.get("by_result", {}).items():
                    weekly_summary["by_result"][result] = \
                        weekly_summary["by_result"].get(result, 0) + count

                # Count errors
                weekly_summary["total_errors"] += len(daily.get("errors", []))

        # Convert set to list for JSON serialization
        weekly_summary["unique_sessions"] = len(weekly_summary["unique_sessions"])

        return weekly_summary


# ─────────────────────────────────────────────────────────────────────────────
# Audit Summary Generator (for CEO Briefing)
# ─────────────────────────────────────────────────────────────────────────────


class AuditSummaryGenerator:
    """Generates audit summary for CEO weekly briefing."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger
        self.audit_logger = AuditLogger("audit_summary", logger)

    def generate_briefing_section(self) -> str:
        """
        Generate audit summary section for CEO briefing.
        
        Returns:
            Markdown formatted audit summary
        """
        weekly = self.audit_logger.get_weekly_summary()

        if "error" in weekly:
            return "## 📊 Audit Summary\n\n_Audit data unavailable_\n"

        # Build summary markdown
        total_actions = weekly["total_actions"]
        total_errors = weekly["total_errors"]
        
        # Get top actors
        top_actors = sorted(
            weekly["by_actor"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        # Get action type breakdown
        action_types = weekly["by_action_type"]
        skill_actions = sum(v for k, v in action_types.items() if "SKILL" in k)
        watcher_actions = sum(v for k, v in action_types.items() if "WATCHER" in k)
        task_actions = sum(v for k, v in action_types.items() if "TASK" in k)

        # Calculate success rate
        results = weekly["by_result"]
        success_count = results.get(ActionResult.SUCCESS.value, 0)
        success_rate = (success_count / total_actions * 100) if total_actions > 0 else 0

        return f"""## 📊 Audit Summary

**Period:** {weekly['period']['start']} to {weekly['period']['end']}

### Activity Overview

| Metric | Value |
|--------|-------|
| **Total Actions** | {total_actions} |
| **Success Rate** | {success_rate:.1f}% |
| **Errors** | {total_errors} |
| **Unique Sessions** | {weekly['unique_sessions']} |

### Action Breakdown

| Category | Count |
|----------|-------|
| Skill Operations | {skill_actions} |
| Watcher Operations | {watcher_actions} |
| Task Processing | {task_actions} |

### Top Actors

| Actor | Actions |
|-------|---------|
""" + "\n".join(f"| {actor} | {count} |" for actor, count in top_actors) + f"""

### Daily Activity

""" + self._format_daily_activity(weekly["daily_totals"]) + """
"""

    def _format_daily_activity(self, daily_totals: dict[str, int]) -> str:
        """Format daily activity as markdown table."""
        if not daily_totals:
            return "_No daily activity data_\n"

        lines = ["| Date | Actions |", "|------|---------|"]
        for date in sorted(daily_totals.keys()):
            count = daily_totals[date]
            lines.append(f"| {date} | {count} |")
        
        return "\n".join(lines) + "\n"


# ─────────────────────────────────────────────────────────────────────────────
# Context Manager for Automatic Logging
# ─────────────────────────────────────────────────────────────────────────────


class AuditContext:
    """
    Context manager for automatic start/end logging.
    
    Usage:
        with AuditContext("skill_name", "Processing task") as ctx:
            # Do work
            ctx.log_action(ActionType.TASK_PROCESSED, "task.md")
    """

    def __init__(
        self,
        actor: str,
        target: str,
        parameters: Optional[dict] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.actor = actor
        self.target = target
        self.parameters = parameters or {}
        self.logger = logger
        self.audit_logger = AuditLogger(actor, logger)
        self.start_entry: Optional[AuditEntry] = None
        self.end_entry: Optional[AuditEntry] = None

    def __enter__(self) -> "AuditContext":
        self.start_entry = self.audit_logger.log_start(self.target, self.parameters)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            self.end_entry = self.audit_logger.log_end(
                self.target,
                result=ActionResult.FAILURE,
                error=str(exc_val),
            )
        else:
            self.end_entry = self.audit_logger.log_end(
                self.target,
                result=ActionResult.SUCCESS,
            )
        return False  # Don't suppress exceptions

    def log_action(
        self,
        action_type: ActionType,
        target: str,
        parameters: Optional[dict] = None,
    ) -> AuditEntry:
        """Log an action within the context."""
        return self.audit_logger.log_action(action_type, target, parameters)


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────────────────────────────────────


def audit_skill_execution(skill_name: str):
    """
    Decorator for automatic skill execution auditing.
    
    Usage:
        @audit_skill_execution("my_skill")
        def run_skill():
            # Skill code
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with AuditContext(skill_name, f"Executing {func.__name__}"):
                return func(*args, **kwargs)
        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point (for testing)
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Test audit logger functionality."""
    print("Testing Audit Logger...")
    
    # Fix Windows console encoding
    if sys.platform == "win32":
        os.system("chcp 65001 >nul")
        sys.stdout.reconfigure(encoding="utf-8")

    # Create logger
    logger = AuditLogger("test_skill")
    
    # Test basic logging
    print("\n1. Testing basic action logging...")
    entry = logger.log_action(
        ActionType.SKILL_START,
        "test_target",
        {"param1": "value1"},
    )
    print(f"   Logged: {entry.action_type} at {entry.timestamp}")
    
    # Test context manager
    print("\n2. Testing context manager...")
    with AuditContext("test_context", "test_operation") as ctx:
        ctx.log_action(ActionType.TASK_PROCESSED, "task.md")
        time.sleep(0.1)  # Simulate work
    print("   Context completed")
    
    # Test daily summary
    print("\n3. Testing daily summary...")
    summary = logger.get_daily_summary()
    print(f"   Total actions today: {summary.get('total_actions', 0)}")
    
    # Test cleanup
    print("\n4. Testing log cleanup...")
    deleted = logger.cleanup_old_logs()
    print(f"   Deleted {deleted} old log files")
    
    # Test audit summary generator
    print("\n5. Testing audit summary generator...")
    summary_gen = AuditSummaryGenerator()
    briefing_section = summary_gen.generate_briefing_section()
    print(f"   Generated {len(briefing_section)} chars of briefing content")
    
    # Show example log entry
    print("\n6. Example log entry:")
    example = AuditEntry(
        timestamp=datetime.now().isoformat(),
        action_type="SKILL_START",
        actor="cross_domain_integrator",
        target="Needs_Action/task.md",
        parameters={"classification": "business"},
        approval_status="not_required",
        result="success",
        duration_ms=150,
        session_id=logger.session_id,
        hostname=logger.hostname,
    )
    print(f"   {json.dumps(example.to_dict(), indent=2)}")
    
    print("\n✅ Audit Logger test complete!")
    print(f"\n📁 Log file: {logger._get_log_file()}")


if __name__ == "__main__":
    main()
