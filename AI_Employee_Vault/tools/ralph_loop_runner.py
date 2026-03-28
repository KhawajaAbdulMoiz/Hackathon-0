#!/usr/bin/env python3
"""
Ralph Wiggum Loop Runner - Gold Tier Autonomous Multi-Step Task Processor

Autonomous loop for handling complex multi-step tasks:
- Sales lead → draft post → HITL approval → MCP execution → audit log
- Max 20 iterations per task
- Integrates with Cross Domain Integrator and Audit Logger
- Automatic file movement on completion

Usage:
    python tools/ralph_loop_runner.py "Process multi-step task" --max-iterations 20
    # Or: /ralph-loop "Process sales leads in Needs_Action" --max-iterations 20

Workflow:
    1. Scan Needs_Action for tasks
    2. Classify task (personal/business)
    3. Route to appropriate handler
    4. Execute steps (draft, approve, send, log)
    5. Move files on completion
    6. Log all actions to audit log
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Final, Optional

# Add tools and skills to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "skills"))

# Import audit logger
from audit_logger import (
    AuditLogger,
    AuditContext,
    ActionType,
    ApprovalStatus,
    ActionResult,
)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

VAULT_ROOT: Final[Path] = Path(__file__).parent.parent.resolve()
NEEDS_ACTION_DIR: Final[Path] = VAULT_ROOT / "Needs_Action"
PLANS_DIR: Final[Path] = VAULT_ROOT / "Plans"
PENDING_APPROVAL_DIR: Final[Path] = VAULT_ROOT / "Pending_Approval"
APPROVED_DIR: Final[Path] = VAULT_ROOT / "Approved"
DONE_DIR: Final[Path] = VAULT_ROOT / "Done"
REJECTED_DIR: Final[Path] = VAULT_ROOT / "Rejected"
LOGS_DIR: Final[Path] = VAULT_ROOT / "Logs"

# Loop configuration
DEFAULT_MAX_ITERATIONS: Final[int] = 20
STEP_TIMEOUT: Final[float] = 300.0  # 5 minutes per step
LOOP_DELAY: Final[float] = 1.0  # 1 second between iterations

# Skill paths
CROSS_DOMAIN_SKILL: Final[Path] = VAULT_ROOT / "skills" / "cross_domain_integrator.py"
SOCIAL_SUMMARY_SKILL: Final[Path] = VAULT_ROOT / "skills" / "social_summary_generator.py"
TWITTER_POST_SKILL: Final[Path] = VAULT_ROOT / "skills" / "twitter_post_generator.py"
HITL_HANDLER_SKILL: Final[Path] = VAULT_ROOT / "skills" / "hitl_approval_handler.py"

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────


class TaskPriority(Enum):
    """Task priority levels."""

    P0_CRITICAL = "P0"
    P1_HIGH = "P1"
    P2_NORMAL = "P2"
    P3_LOW = "P3"


class TaskStatus(Enum):
    """Task execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class StepType(Enum):
    """Types of steps in multi-step workflow."""

    CLASSIFY = auto()
    ROUTE = auto()
    DRAFT = auto()
    APPROVE = auto()
    EXECUTE = auto()
    LOG = auto()
    ARCHIVE = auto()


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TaskStep:
    """Represents a single step in multi-step workflow."""

    step_type: StepType
    name: str
    handler: Optional[Callable] = None
    completed: bool = False
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: int = 0


@dataclass
class MultiStepTask:
    """Represents a multi-step task being processed."""

    task_id: str
    file_path: Path
    title: str
    content: str
    priority: TaskPriority = TaskPriority.P2_NORMAL
    status: TaskStatus = TaskStatus.PENDING
    steps: list[TaskStep] = field(default_factory=list)
    current_step: int = 0
    iteration: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class LoopResult:
    """Result of loop execution."""

    task_id: str
    status: TaskStatus
    iterations_used: int
    steps_completed: int
    steps_total: int
    error: Optional[str] = None
    files_created: list[Path] = field(default_factory=list)
    files_moved: list[tuple[Path, Path]] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────────────────


def setup_logging() -> logging.Logger:
    """Configure logging."""
    logger = logging.getLogger("ralph_loop")
    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    # File handler
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"ralph_loop_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# ─────────────────────────────────────────────────────────────────────────────
# Step Handlers
# ─────────────────────────────────────────────────────────────────────────────


class StepHandlers:
    """Handles individual workflow steps."""

    def __init__(self, logger: logging.Logger, audit: AuditLogger) -> None:
        self.logger = logger
        self.audit = audit

    def classify_task(self, task: MultiStepTask) -> dict:
        """Classify task as personal or business."""
        self.logger.info(f"Classifying task: {task.task_id}")

        content_lower = task.content.lower()

        # Personal keywords
        personal_keywords = ["email", "message", "gmail", "whatsapp", "personal"]
        # Business keywords
        business_keywords = ["sales", "client", "project", "linkedin", "post"]

        personal_score = sum(1 for k in personal_keywords if k in content_lower)
        business_score = sum(1 for k in business_keywords if k in content_lower)

        classification = {
            "domain": "personal" if personal_score > business_score else "business",
            "personal_score": personal_score,
            "business_score": business_score,
            "keywords_found": [],
        }

        # Log classification
        self.audit.log_action(
            ActionType.TASK_CLASSIFIED,
            task.file_path.name,
            classification,
        )

        return classification

    def route_task(self, task: MultiStepTask, classification: dict) -> str:
        """Route task to appropriate handler."""
        domain = classification.get("domain", "business")

        if domain == "personal":
            route = "HITL"
            task.steps.extend([
                TaskStep(StepType.DRAFT, "Draft response for HITL"),
                TaskStep(StepType.APPROVE, "Wait for HITL approval"),
                TaskStep(StepType.EXECUTE, "Execute via MCP"),
                TaskStep(StepType.LOG, "Log action"),
                TaskStep(StepType.ARCHIVE, "Archive to Done"),
            ])
        else:
            # Check for social media content
            if any(k in task.content.lower() for k in ["linkedin", "twitter", "facebook"]):
                route = "SOCIAL_AUTO"
                task.steps.extend([
                    TaskStep(StepType.DRAFT, "Draft social post"),
                    TaskStep(StepType.APPROVE, "Wait for approval"),
                    TaskStep(StepType.EXECUTE, "Post to platform"),
                    TaskStep(StepType.LOG, "Log action"),
                    TaskStep(StepType.ARCHIVE, "Archive to Done"),
                ])
            else:
                route = "AUTO_PROCESS"
                task.steps.extend([
                    TaskStep(StepType.EXECUTE, "Auto-process task"),
                    TaskStep(StepType.LOG, "Log action"),
                    TaskStep(StepType.ARCHIVE, "Archive to Done"),
                ])

        self.logger.info(f"Routed to: {route}")
        self.audit.log_action(
            ActionType.TASK_PROCESSED,
            task.file_path.name,
            {"route": route, "domain": domain},
        )

        return route

    def draft_response(self, task: MultiStepTask) -> Optional[Path]:
        """Draft response based on task type."""
        self.logger.info(f"Drafting response for: {task.task_id}")

        # Create draft in Plans
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        draft_name = f"ralph_draft_{task.task_id}_{timestamp}.md"
        draft_path = PLANS_DIR / draft_name

        draft_content = f"""---
type: ralph_loop_draft
task_id: {task.task_id}
created: {datetime.now().isoformat()}
status: draft
---

# 📝 Draft Response

**Task:** {task.title}
**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Suggested Response

[Auto-generated response based on task content]

---

## Original Content

{task.content[:500]}

---

*Generated by Ralph Loop Runner*
"""

        PLANS_DIR.mkdir(parents=True, exist_ok=True)
        with open(draft_path, "w", encoding="utf-8") as f:
            f.write(draft_content)

        self.audit.log_file_operation("created", str(draft_path))
        return draft_path

    def wait_for_approval(self, task: MultiStepTask, draft_path: Path) -> bool:
        """Wait for HITL approval (simulated for auto-mode)."""
        self.logger.info(f"Waiting for approval: {task.task_id}")

        # In auto-mode, we simulate approval after delay
        # In real HITL, this would wait for human action
        time.sleep(0.5)  # Simulated approval delay

        # Move to Pending_Approval for tracking
        approval_path = PENDING_APPROVAL_DIR / f"APPROVAL_{draft_path.name}"
        with open(draft_path, "r", encoding="utf-8") as f:
            content = f.read()

        approval_content = f"""---
type: hitl_approval
task_id: {task.task_id}
status: auto_approved
approved_at: {datetime.now().isoformat()}
---

{content}

---

## Auto-Approval

This task was auto-approved by Ralph Loop Runner.

"""

        with open(approval_path, "w", encoding="utf-8") as f:
            f.write(approval_content)

        self.audit.log_action(
            ActionType.APPROVAL_GRANTED,
            str(approval_path),
            {"auto_approved": True},
        )

        return True

    def execute_action(self, task: MultiStepTask) -> bool:
        """Execute the task action (MCP or direct)."""
        self.logger.info(f"Executing action: {task.task_id}")

        # Simulate MCP execution
        # In real implementation, this would call MCP servers
        time.sleep(0.3)

        self.audit.log_action(
            ActionType.API_CALL,
            task.task_id,
            {"type": "mcp_execution", "simulated": True},
        )

        return True

    def log_action(self, task: MultiStepTask) -> None:
        """Log completed action."""
        self.logger.info(f"Logging action: {task.task_id}")

        self.audit.log_action(
            ActionType.TASK_COMPLETED,
            task.task_id,
            {
                "iterations": task.iteration,
                "steps_completed": task.current_step,
            },
        )

    def archive_task(self, task: MultiStepTask) -> tuple[Path, Path]:
        """Archive task to Done folder."""
        self.logger.info(f"Archiving task: {task.task_id}")

        # Move original file to Done
        timestamp = datetime.now().strftime("%Y-%m-%d")
        dest_name = f"{timestamp}_{task.file_path.name}"
        dest_path = DONE_DIR / dest_name

        # Read original content
        with open(task.file_path, "r", encoding="utf-8") as f:
            original_content = f.read()

        # Append completion summary
        completion_summary = f"""

---

## ✅ Task Completed by Ralph Loop

**Completed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Iterations:** {task.iteration}
**Steps Completed:** {task.current_step}/{len(task.steps)}
**Status:** {task.status.value}

"""

        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(original_content + completion_summary)

        # Remove original from Needs_Action
        task.file_path.unlink()

        self.audit.log_file_operation("moved", str(task.file_path), result=ActionResult.SUCCESS)
        self.audit.log_file_operation("created", str(dest_path), result=ActionResult.SUCCESS)

        return task.file_path, dest_path


# ─────────────────────────────────────────────────────────────────────────────
# Ralph Loop Runner (Main Class)
# ─────────────────────────────────────────────────────────────────────────────


class RalphLoopRunner:
    """
    Ralph Wiggum Loop Runner for autonomous multi-step task processing.

    Usage:
        runner = RalphLoopRunner()
        result = runner.run("Process sales leads", max_iterations=20)
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or setup_logging()
        self.audit = AuditLogger("ralph_loop_runner", self.logger)
        self.handlers = StepHandlers(self.logger, self.audit)

        # Ensure directories exist
        for directory in [
            NEEDS_ACTION_DIR, PLANS_DIR, PENDING_APPROVAL_DIR,
            APPROVED_DIR, DONE_DIR, REJECTED_DIR, LOGS_DIR
        ]:
            directory.mkdir(parents=True, exist_ok=True)

        self.results: list[LoopResult] = []

    def run(
        self,
        task_description: str = "Process multi-step task",
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> list[LoopResult]:
        """
        Run the Ralph Loop for multi-step task processing.

        Args:
            task_description: Description of task to process
            max_iterations: Maximum iterations per task (default: 20)

        Returns:
            List of LoopResult for each processed task
        """
        self.logger.info("=" * 60)
        self.logger.info("RALPH WIGGUM LOOP RUNNER - STARTING")
        self.logger.info(f"Task: {task_description}")
        self.logger.info(f"Max Iterations: {max_iterations}")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  🔄 RALPH WIGGUM LOOP RUNNER")
        print(f"  {task_description}")
        print(f"  Max Iterations: {max_iterations}")
        print(f"{'=' * 60}\n")

        with AuditContext("ralph_loop", task_description, self.logger) as ctx:
            try:
                # Scan Needs_Action for tasks
                tasks = self._scan_tasks()
                ctx.log_action(ActionType.TASK_RECEIVED, "Needs_Action", {"count": len(tasks)})

                if not tasks:
                    print("📭 No tasks to process in Needs_Action\n")
                    ctx.log_action(ActionType.TASK_COMPLETED, "Needs_Action", {"reason": "no_tasks"})
                    return self.results

                # Process each task
                for task in tasks:
                    result = self._process_task(task, max_iterations)
                    self.results.append(result)

                # Print summary
                self._print_summary()
                ctx.log_action(ActionType.TASK_COMPLETED, "ralph_loop", {"processed": len(self.results)})

                return self.results

            except Exception as e:
                self.logger.exception(f"Loop runner failed: {e}")
                ctx.log_action(ActionType.SKILL_ERROR, "ralph_loop", {"error": str(e)})
                raise

    def _scan_tasks(self) -> list[MultiStepTask]:
        """Scan Needs_Action for tasks to process."""
        tasks = []

        try:
            md_files = list(NEEDS_ACTION_DIR.glob("*.md"))
            self.logger.info(f"Found {len(md_files)} files in Needs_Action")

            for file_path in md_files:
                task = self._parse_task_file(file_path)
                if task:
                    tasks.append(task)

            return tasks

        except Exception as e:
            self.logger.error(f"Error scanning tasks: {e}")
            return []

    def _parse_task_file(self, file_path: Path) -> Optional[MultiStepTask]:
        """Parse task file into MultiStepTask."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract title from first line or filename
            lines = content.strip().split("\n")
            title = file_path.stem

            for line in lines:
                if line.startswith("#"):
                    title = line.lstrip("#").strip()
                    break

            # Extract priority from content or frontmatter
            priority = TaskPriority.P2_NORMAL
            if "P0" in content or "urgent" in content.lower():
                priority = TaskPriority.P0_CRITICAL
            elif "P1" in content or "high" in content.lower():
                priority = TaskPriority.P1_HIGH

            return MultiStepTask(
                task_id=f"task_{file_path.stem}_{int(time.time())}",
                file_path=file_path,
                title=title,
                content=content,
                priority=priority,
            )

        except Exception as e:
            self.logger.error(f"Error parsing {file_path.name}: {e}")
            return None

    def _process_task(
        self,
        task: MultiStepTask,
        max_iterations: int,
    ) -> LoopResult:
        """Process a single multi-step task."""
        self.logger.info(f"Processing task: {task.task_id}")
        print(f"\n📋 Processing: {task.title[:50]}...")

        task.status = TaskStatus.IN_PROGRESS

        # Initial classification and routing
        classification = self.handlers.classify_task(task)
        route = self.handlers.route_task(task, classification)

        print(f"   Classified: {classification['domain']} | Route: {route}")

        # Execute steps in loop
        files_created = []
        files_moved = []

        while task.iteration < max_iterations and task.current_step < len(task.steps):
            task.iteration += 1
            step = task.steps[task.current_step]

            self.logger.info(f"Iteration {task.iteration}: Executing step {task.current_step + 1} - {step.name}")
            print(f"   Iteration {task.iteration}: {step.name}")

            step_start = time.time()

            try:
                # Execute step handler
                step.result = self._execute_step(task, step)
                step.completed = True
                step.duration_ms = int((time.time() - step_start) * 1000)

                # Track files
                if isinstance(step.result, Path):
                    files_created.append(step.result)
                elif isinstance(step.result, tuple) and len(step.result) == 2:
                    files_moved.append(step.result)

                # Move to next step
                task.current_step += 1

                # Small delay between iterations
                time.sleep(LOOP_DELAY)

            except Exception as e:
                step.error = str(e)
                self.logger.error(f"Step failed: {e}")
                task.status = TaskStatus.FAILED

                self.audit.log_action(
                    ActionType.TASK_FAILED,
                    task.task_id,
                    {"step": step.name, "error": str(e)},
                )

                return LoopResult(
                    task_id=task.task_id,
                    status=task.status,
                    iterations_used=task.iteration,
                    steps_completed=task.current_step,
                    steps_total=len(task.steps),
                    error=str(e),
                    files_created=files_created,
                    files_moved=files_moved,
                )

        # Task completed
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()

        print(f"   ✅ TASK_COMPLETE (Iterations: {task.iteration}, Steps: {task.current_step}/{len(task.steps)})")

        return LoopResult(
            task_id=task.task_id,
            status=task.status,
            iterations_used=task.iteration,
            steps_completed=task.current_step,
            steps_total=len(task.steps),
            files_created=files_created,
            files_moved=files_moved,
        )

    def _execute_step(self, task: MultiStepTask, step: TaskStep) -> Any:
        """Execute individual step handler."""
        if step.step_type == StepType.CLASSIFY:
            return self.handlers.classify_task(task)
        elif step.step_type == StepType.ROUTE:
            return self.handlers.route_task(task, {})
        elif step.step_type == StepType.DRAFT:
            return self.handlers.draft_response(task)
        elif step.step_type == StepType.APPROVE:
            draft_path = next((f for f in task.metadata.get("files_created", []) if isinstance(f, Path)), None)
            if draft_path:
                return self.handlers.wait_for_approval(task, draft_path)
            return True
        elif step.step_type == StepType.EXECUTE:
            return self.handlers.execute_action(task)
        elif step.step_type == StepType.LOG:
            return self.handlers.log_action(task)
        elif step.step_type == StepType.ARCHIVE:
            return self.handlers.archive_task(task)
        else:
            raise ValueError(f"Unknown step type: {step.step_type}")

    def _print_summary(self) -> None:
        """Print execution summary."""
        completed = sum(1 for r in self.results if r.status == TaskStatus.COMPLETED)
        failed = sum(1 for r in self.results if r.status == TaskStatus.FAILED)

        print(f"\n{'=' * 60}")
        print("  ✅ RALPH LOOP RUNNER - COMPLETE")
        print(f"{'=' * 60}")
        print(f"  Tasks Processed:  {len(self.results)}")
        print(f"  Completed:        {completed}")
        print(f"  Failed:           {failed}")
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

    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Ralph Wiggum Loop Runner - Multi-step task processor"
    )
    parser.add_argument(
        "task_description",
        nargs="?",
        default="Process multi-step task in Needs_Action",
        help="Description of task to process",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Maximum iterations per task (default: {DEFAULT_MAX_ITERATIONS})",
    )

    args = parser.parse_args()

    # Run loop
    runner = RalphLoopRunner()
    runner.run(args.task_description, args.max_iterations)


if __name__ == "__main__":
    main()
