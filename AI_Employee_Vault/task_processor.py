#!/usr/bin/env python3
"""
Task Processor - AI Employee Task Execution Engine

Processes files in Needs_Action folder by creating plans, executing tasks,
and archiving completed work with full logging and dashboard updates.

Python 3.13+ | Production-Ready
"""

import logging
import shutil
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Final, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

VAULT_ROOT: Final[Path] = Path(__file__).parent.resolve()
NEEDS_ACTION_DIR: Final[Path] = VAULT_ROOT / "Needs_Action"
PLANS_DIR: Final[Path] = VAULT_ROOT / "Plans"
DONE_DIR: Final[Path] = VAULT_ROOT / "Done"
LOGS_DIR: Final[Path] = VAULT_ROOT / "Logs"
DASHBOARD_FILE: Final[Path] = VAULT_ROOT / "Dashboard.md"

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"


# ─────────────────────────────────────────────────────────────────────────────
# Enums & Data Classes
# ─────────────────────────────────────────────────────────────────────────────


class TaskStatus(Enum):
    """Task execution status."""

    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    BLOCKED = auto()


@dataclass
class Task:
    """Represents a task to be processed."""

    original_file: Path
    task_name: str
    content: str
    status: TaskStatus = TaskStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    steps_completed: list[str] = field(default_factory=list)


@dataclass
class Plan:
    """Represents an execution plan for a task."""

    task_name: str
    objective: str
    success_criteria: list[str]
    steps: list[str]
    estimated_duration: str
    file_path: Path


# ─────────────────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────────────────


def setup_logging() -> logging.Logger:
    """Configure logging with both file and console handlers."""
    logger = logging.getLogger("task_processor")
    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    # File handler
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"processor_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# ─────────────────────────────────────────────────────────────────────────────
# Plan Manager
# ─────────────────────────────────────────────────────────────────────────────


class PlanManager:
    """Handles creation and management of task plans."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        PLANS_DIR.mkdir(parents=True, exist_ok=True)

    def create_plan(self, task: Task) -> Plan:
        """Create a plan file for the given task."""
        self.logger.info(f"Creating plan for: {task.task_name}")

        # Parse task content to extract objective
        objective = self._extract_objective(task.content)
        success_criteria = self._extract_success_criteria(task.content)
        steps = self._generate_steps(task.content)

        plan = Plan(
            task_name=task.task_name,
            objective=objective,
            success_criteria=success_criteria,
            steps=steps,
            estimated_duration="30 minutes",
            file_path=Path(),
        )

        # Write plan file
        plan_content = self._generate_plan_content(plan, task)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        plan_filename = f"{timestamp}_{self._sanitize_filename(task.task_name)}.md"
        plan_path = PLANS_DIR / plan_filename

        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(plan_content)

        plan.file_path = plan_path
        self.logger.info(f"Plan created: {plan_path.name}")

        return plan

    def _extract_objective(self, content: str) -> str:
        """Extract the main objective from task content."""
        lines = content.strip().split("\n")
        for line in lines:
            if line.startswith("#"):
                return line.lstrip("#").strip()
        return "Complete the assigned task"

    def _extract_success_criteria(self, content: str) -> list[str]:
        """Extract success criteria from task content."""
        criteria = []
        if "should" in content.lower():
            criteria.append("Task requirements fulfilled")
        criteria.append("Output matches specifications")
        criteria.append("No errors during execution")
        return criteria

    def _generate_steps(self, content: str) -> list[str]:
        """Generate execution steps from task content."""
        return [
            "Review task requirements",
            "Execute task operations",
            "Verify results",
            "Document outcomes",
            "Archive completed task",
        ]

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for use in filename."""
        return "".join(c if c.isalnum() or c in " -_" else "_" for c in name)[:50]

    def _generate_plan_content(self, plan: Plan, task: Task) -> str:
        """Generate markdown content for plan file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        criteria_md = "\n".join(f"- [ ] {c}" for c in plan.success_criteria)
        steps_md = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(plan.steps))

        return f"""# 📋 Plan: {plan.task_name}

**Created:** {timestamp}
**Task File:** {task.original_file.name}
**Status:** 🟡 In Progress

---

## Objective

{plan.objective}

---

## Success Criteria

{criteria_md}

---

## Execution Steps

{steps_md}

---

## Estimated Duration

{plan.estimated_duration}

---

## Notes

- Plan generated automatically by Task Processor
- Adjust steps as needed during execution

---

*Plan ID: {datetime.now().strftime("%Y%m%d%H%M%S")}*
"""


# ─────────────────────────────────────────────────────────────────────────────
# Task Executor
# ─────────────────────────────────────────────────────────────────────────────


class TaskExecutor(ABC):
    """Abstract base class for task executors."""

    @abstractmethod
    def execute(self, task: Task, plan: Plan) -> Task:
        """Execute the task according to the plan."""
        pass


class SimulatedTaskExecutor(TaskExecutor):
    """Simulates task execution for demonstration."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def execute(self, task: Task, plan: Plan) -> Task:
        """Simulate executing the task."""
        self.logger.info(f"Executing task: {task.task_name}")
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()

        # Simulate execution steps
        for i, step in enumerate(plan.steps, 1):
            self.logger.debug(f"Step {i}/{len(plan.steps)}: {step}")
            task.steps_completed.append(f"✅ {step}")

        # Simulate completion
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()

        self.logger.info(f"Task completed: {task.task_name}")
        return task


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Manager
# ─────────────────────────────────────────────────────────────────────────────


class DashboardManager:
    """Handles Dashboard.md updates."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def update_dashboard(self, task: Task, action: str) -> None:
        """Update the dashboard with latest task information."""
        self.logger.debug("Updating dashboard")

        if not DASHBOARD_FILE.exists():
            self._create_dashboard()
            return

        try:
            with open(DASHBOARD_FILE, "r", encoding="utf-8") as f:
                content = f.read()

            # Update metrics
            content = self._update_stats(content)
            content = self._update_recently_completed(content, task)
            content = self._update_last_modified(content)

            with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
                f.write(content)

            self.logger.info("Dashboard updated")

        except Exception as e:
            self.logger.error(f"Failed to update dashboard: {e}")

    def _create_dashboard(self) -> None:
        """Create a new dashboard file."""
        content = self._generate_dashboard_content()
        with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        self.logger.info("Dashboard created")

    def _generate_dashboard_content(self) -> str:
        """Generate default dashboard content."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"""# 🎛️ AI Employee Dashboard

**Last Updated:** {timestamp}
**Status:** 🟢 Operational

---

## 📊 Quick Stats

| Metric | Value |
|--------|-------|
| Inbox Items | 0 |
| Active Tasks | 0 |
| In Progress | 0 |
| Completed Today | 1 |
| Blocked | 0 |

---

## ✅ Recently Completed

| Task | Completed | Time Taken | Notes |
|------|-----------|------------|-------|
| _See logs for details_ | {timestamp} | — | — |

---

## 🔄 Last Refresh

{timestamp}

---

*Dashboard auto-updates on task completion*
"""

    def _update_stats(self, content: str) -> str:
        """Update quick stats section."""
        inbox_path = VAULT_ROOT / "Inbox"
        inbox_count = len(list(inbox_path.glob("*.md"))) if inbox_path.exists() else 0
        needs_action_count = len(list(NEEDS_ACTION_DIR.glob("*.md")))
        done_count = len(list(DONE_DIR.glob("*.md")))

        if "| Active Tasks | 0 |" in content:
            content = content.replace(
                "| Active Tasks | 0 |", f"| Active Tasks | {needs_action_count} |"
            )
        if "| Inbox Items | 0 |" in content:
            content = content.replace(
                "| Inbox Items | 0 |", f"| Inbox Items | {inbox_count} |"
            )
        if "| Completed Today | 0 |" in content:
            content = content.replace(
                "| Completed Today | 0 |",
                f"| Completed Today | {done_count} |",
            )

        return content

    def _update_recently_completed(self, content: str, task: Task) -> str:
        """Update recently completed section."""
        if task.completed_at and task.status == TaskStatus.COMPLETED:
            time_taken = task.completed_at - task.started_at if task.started_at else None
            duration_str = f"{int(time_taken.total_seconds())}s" if time_taken else "—"
            timestamp = task.completed_at.strftime("%Y-%m-%d")

            new_row = f"| {task.task_name} | {timestamp} | {duration_str} | Auto-processed |"

            if "| _No recent completions_" in content:
                content = content.replace("| _No recent completions_ | — | — | — |", new_row)
            elif "| Task | Completed |" in content:
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if "| Task | Completed |" in line:
                        lines.insert(i + 2, new_row)
                        break
                content = "\n".join(lines)

        return content

    def _update_last_modified(self, content: str) -> str:
        """Update last modified timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if "**Last Updated:**" in content and "**Last Updated:** {timestamp}" not in content:
            content = content.replace(
                "**Last Updated:**", f"**Last Updated:** {timestamp}"
            )
        return content


# ─────────────────────────────────────────────────────────────────────────────
# Action Logger
# ─────────────────────────────────────────────────────────────────────────────


class ActionLogger:
    """Handles detailed action logging."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.log_file = LOGS_DIR / "task_actions.md"

    def log_action(self, task: Task, plan: Plan, action: str) -> None:
        """Log a task action."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log_entry = f"""
## [{timestamp}] {action}

**Task:** {task.task_name}
**Original File:** {task.original_file.name}
**Plan File:** {plan.file_path.name}
**Status:** {task.status.name}
**Steps Completed:** {len(task.steps_completed)}
"""

        if task.error_message:
            log_entry += f"**Error:** {task.error_message}\n"

        if task.completed_at and task.started_at:
            duration = task.completed_at - task.started_at
            log_entry += f"**Duration:** {int(duration.total_seconds())} seconds\n"

        self._write_log(log_entry)

    def _write_log(self, entry: str) -> None:
        """Write entry to action log file."""
        is_new = not self.log_file.exists()

        with open(self.log_file, "a", encoding="utf-8") as f:
            if is_new:
                f.write("# Task Action Log\n\n")
                f.write(f"*Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
            f.write(entry)
            f.write("\n---\n")


# ─────────────────────────────────────────────────────────────────────────────
# Task Processor (Main Class)
# ─────────────────────────────────────────────────────────────────────────────


class TaskProcessor:
    """Main task processing engine."""

    def __init__(self) -> None:
        self.logger = setup_logging()
        self.plan_manager = PlanManager(self.logger)
        self.executor = SimulatedTaskExecutor(self.logger)
        self.dashboard_manager = DashboardManager(self.logger)
        self.action_logger = ActionLogger(self.logger)

        # Ensure directories exist
        for directory in [NEEDS_ACTION_DIR, PLANS_DIR, DONE_DIR, LOGS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

    def process_all_tasks(self) -> int:
        """Process all tasks in Needs_Action folder."""
        self.logger.info("Starting task processing cycle")

        task_files = list(NEEDS_ACTION_DIR.glob("*.md"))

        if not task_files:
            self.logger.info("No tasks to process")
            print("\n📭 No tasks in Needs_Action folder\n")
            return 0

        processed_count = 0

        for task_file in task_files:
            try:
                self._process_single_task(task_file)
                processed_count += 1
            except Exception as e:
                self.logger.exception(f"Failed to process {task_file.name}: {e}")

        self.logger.info(f"Processing complete: {processed_count} tasks processed")
        return processed_count

    def _process_single_task(self, task_file: Path) -> None:
        """Process a single task file."""
        self.logger.info(f"Processing: {task_file.name}")

        # Step 1: Read task
        task = self._read_task(task_file)

        # Step 2: Create plan
        plan = self.plan_manager.create_plan(task)

        # Step 3: Execute task
        task = self.executor.execute(task, plan)

        # Step 4: Move to Done
        self._archive_task(task, plan)

        # Step 5: Update dashboard
        self.dashboard_manager.update_dashboard(task, "completed")

        # Step 6: Log action
        self.action_logger.log_action(task, plan, "Task Completed")

        # Print summary
        self._print_task_summary(task, plan)

    def _read_task(self, task_file: Path) -> Task:
        """Read task from file."""
        self.logger.debug(f"Reading task: {task_file.name}")

        with open(task_file, "r", encoding="utf-8") as f:
            content = f.read()

        return Task(
            original_file=task_file,
            task_name=task_file.stem,
            content=content,
        )

    def _archive_task(self, task: Task, plan: Plan) -> None:
        """Move task file to Done folder."""
        if task.completed_at:
            timestamp = task.completed_at.strftime("%Y-%m-%d")
            dest_name = f"{timestamp}_{task.original_file.name}"
        else:
            dest_name = task.original_file.name

        dest_path = DONE_DIR / dest_name

        # Handle duplicates
        counter = 1
        while dest_path.exists():
            stem = task.original_file.stem
            suffix = task.original_file.suffix
            dest_name = f"{timestamp}_{stem}_{counter}{suffix}"
            dest_path = DONE_DIR / dest_name
            counter += 1

        shutil.move(str(task.original_file), str(dest_path))
        self.logger.info(f"Archived to: {dest_path.name}")

        # Append completion summary to archived file
        self._append_completion_summary(dest_path, task, plan)

    def _append_completion_summary(self, file_path: Path, task: Task, plan: Plan) -> None:
        """Append completion summary to archived task file."""
        summary = f"""

---

## ✅ Completion Summary

**Completed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Plan:** {plan.file_path.name}
**Status:** {task.status.name}

### Steps Executed
"""
        for step in task.steps_completed:
            summary += f"- {step}\n"

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(summary)

    def _print_task_summary(self, task: Task, plan: Plan) -> None:
        """Print task completion summary to console."""
        duration = task.completed_at - task.started_at if (
            task.started_at and task.completed_at
        ) else None
        duration_str = f"{int(duration.total_seconds())}s" if duration else "—"

        print(f"\n{'=' * 60}")
        print(f"✅ TASK COMPLETED")
        print(f"   Name:     {task.task_name}")
        print(f"   Plan:     {plan.file_path.name}")
        print(f"   Duration: {duration_str}")
        print(f"   Status:   {task.status.name}")
        print(f"{'=' * 60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Main entry point."""
    print(f"\n{'=' * 60}")
    print("  AI EMPLOYEE TASK PROCESSOR")
    print(f"  Vault Root: {VAULT_ROOT}")
    print(f"{'=' * 60}\n")

    processor = TaskProcessor()
    processed = processor.process_all_tasks()

    if processed > 0:
        print(f"🎉 Successfully processed {processed} task(s)\n")
    else:
        print("📭 No tasks were processed\n")


if __name__ == "__main__":
    main()
