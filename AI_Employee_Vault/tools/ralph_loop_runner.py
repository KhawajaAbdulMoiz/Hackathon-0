#!/usr/bin/env python3
"""
Ralph Loop Runner - Claude Reasoning Loop for Silver Tier

Implements persistent reasoning loop pattern for autonomous task processing.
Iterates until all tasks complete or max iterations reached.

Pattern: Ralph Wiggum (Persistent Reasoning Loop)
- Continuous analysis → Planning → Execution → Verification
- Completion promise: TASK_COMPLETE
- Handles multi-step workflows with HITL checkpoints

Usage:
    python tools/ralph_loop_runner.py "Process Needs_Action" --max-iterations 10
    python tools/ralph_loop_runner.py "Analyze sales leads" --max-iterations 5
"""

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Final, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

VAULT_ROOT: Final[Path] = Path(__file__).parent.parent.resolve()
NEEDS_ACTION_DIR: Final[Path] = VAULT_ROOT / "Needs_Action"
PLANS_DIR: Final[Path] = VAULT_ROOT / "Plans"
DONE_DIR: Final[Path] = VAULT_ROOT / "Done"
PENDING_APPROVAL_DIR: Final[Path] = VAULT_ROOT / "Pending_Approval"
LOGS_DIR: Final[Path] = VAULT_ROOT / "Logs"
TOOLS_DIR: Final[Path] = VAULT_ROOT / "tools"

DEFAULT_MAX_ITERATIONS: Final[int] = 10
COMPLETION_PROMISE: Final[str] = "TASK_COMPLETE"
LOOP_PROMPT_TEMPLATE: Final[str] = """
Process all files in /Needs_Action, analyze with Task Analyzer, create detailed Plan.md in /Plans with steps, checkboxes, priorities.

Current iteration: {iteration}/{max_iterations}
Files in Needs_Action: {file_count}
Files in Plans: {plans_count}
Files in Done: {done_count}

For each task:
1. Analyze the task requirements
2. Create a detailed plan with numbered steps
3. Add checkboxes for each step: - [ ] Step description
4. Assign priorities: P0 (Critical), P1 (High), P2 (Normal), P3 (Low)
5. Identify if HITL approval is needed

Multi-step workflow example:
- sales lead → draft post → HITL → Pending_Approval
- invoice → verify amount → schedule payment → Done

When a task is fully processed, move it to /Done.
When HITL is required, move to /Pending_Approval.

{COMPLETION_PROMISE} when all tasks are processed or no more actions possible.
"""

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# ─────────────────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────────────────


def setup_logging() -> logging.Logger:
    """Configure logging with both file and console handlers."""
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
# Enums & Data Classes
# ─────────────────────────────────────────────────────────────────────────────


class LoopStatus(Enum):
    """Status of the reasoning loop."""

    RUNNING = auto()
    COMPLETED = auto()
    MAX_ITERATIONS = auto()
    NO_TASKS = auto()
    ERROR = auto()


@dataclass
class LoopMetrics:
    """Metrics for the loop execution."""

    iteration: int = 0
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    tasks_processed: int = 0
    plans_created: int = 0
    files_moved_to_done: int = 0
    files_moved_to_approval: int = 0
    completion_promise_found: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        """Calculate loop duration."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()


@dataclass
class VaultState:
    """Current state of the vault."""

    needs_action_count: int = 0
    plans_count: int = 0
    done_count: int = 0
    pending_approval_count: int = 0
    needs_action_files: list[Path] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Vault State Manager
# ─────────────────────────────────────────────────────────────────────────────


class VaultStateManager:
    """Manages vault state tracking."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def get_state(self) -> VaultState:
        """Get current vault state."""
        state = VaultState()

        try:
            state.needs_action_files = list(NEEDS_ACTION_DIR.glob("*.md"))
            state.needs_action_count = len(state.needs_action_files)
            state.plans_count = len(list(PLANS_DIR.glob("*.md")))
            state.done_count = len(list(DONE_DIR.glob("*.md")))
            state.pending_approval_count = len(list(PENDING_APPROVAL_DIR.glob("*.md")))
        except Exception as e:
            self.logger.error(f"Error getting vault state: {e}")

        return state

    def has_pending_tasks(self) -> bool:
        """Check if there are pending tasks."""
        try:
            return len(list(NEEDS_ACTION_DIR.glob("*.md"))) > 0
        except Exception:
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Task Analyzer
# ─────────────────────────────────────────────────────────────────────────────


class TaskAnalyzer:
    """Analyzes tasks in Needs_Action folder."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def analyze_files(self, files: list[Path]) -> list[dict]:
        """Analyze task files and extract metadata."""
        analyses = []

        for file_path in files:
            try:
                analysis = self._analyze_file(file_path)
                if analysis:
                    analyses.append(analysis)
            except Exception as e:
                self.logger.error(f"Error analyzing {file_path}: {e}")

        return analyses

    def _analyze_file(self, file_path: Path) -> Optional[dict]:
        """Analyze a single task file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract metadata
            metadata = self._extract_metadata(content, file_path)

            # Determine task type
            task_type = self._determine_task_type(content, file_path.name)

            # Check if HITL required
            hitl_required = self._check_hitl_required(content, task_type)

            # Estimate complexity
            complexity = self._estimate_complexity(content)

            return {
                "file_path": str(file_path),
                "file_name": file_path.name,
                "metadata": metadata,
                "task_type": task_type,
                "hitl_required": hitl_required,
                "complexity": complexity,
                "content_preview": content[:200],
            }

        except Exception as e:
            self.logger.error(f"Error analyzing file: {e}")
            return None

    def _extract_metadata(self, content: str, file_path: Path) -> dict:
        """Extract YAML frontmatter metadata."""
        metadata = {
            "type": "unknown",
            "priority": "P3",
            "status": "pending",
            "from": "",
            "subject": file_path.stem,
        }

        # Try to parse YAML frontmatter
        if content.startswith("---"):
            try:
                lines = content.split("\n")
                in_frontmatter = False
                for line in lines[1:]:
                    if line.strip() == "---":
                        break
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip()
            except Exception:
                pass

        return metadata

    def _determine_task_type(self, content: str, filename: str) -> str:
        """Determine task type from content."""
        content_lower = content.lower()
        filename_lower = filename.lower()

        if any(k in content_lower for k in ["sales", "client", "lead", "opportunity"]):
            return "sales_lead"
        elif any(k in content_lower for k in ["invoice", "payment", "bill"]):
            return "financial"
        elif any(k in content_lower for k in ["email", "gmail"]):
            return "email_task"
        elif any(k in content_lower for k in ["whatsapp", "message"]):
            return "message_task"
        elif any(k in content_lower for k in ["linkedin"]):
            return "linkedin_task"
        elif "email" in filename_lower:
            return "email_task"
        elif "whatsapp" in filename_lower:
            return "message_task"
        elif "linkedin" in filename_lower:
            return "linkedin_task"

        return "general"

    def _check_hitl_required(self, content: str, task_type: str) -> bool:
        """Check if Human-in-the-Loop approval is required."""
        # Tasks requiring HITL
        hitl_types = ["sales_lead", "financial"]
        hitl_keywords = ["approval", "review", "confirm", "authorize"]

        if task_type in hitl_types:
            return True

        content_lower = content.lower()
        if any(k in content_lower for k in hitl_keywords):
            return True

        return False

    def _estimate_complexity(self, content: str) -> str:
        """Estimate task complexity."""
        word_count = len(content.split())
        line_count = len(content.split("\n"))

        if word_count > 500 or line_count > 50:
            return "high"
        elif word_count > 100 or line_count > 20:
            return "medium"
        return "low"


# ─────────────────────────────────────────────────────────────────────────────
# Plan Generator
# ─────────────────────────────────────────────────────────────────────────────


class PlanGenerator:
    """Generates detailed plans for tasks."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def generate_plan(self, task_analysis: dict) -> Optional[Path]:
        """Generate a detailed plan for a task."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            task_name = Path(task_analysis["file_name"]).stem
            plan_filename = f"plan_{timestamp}_{task_name}.md"
            plan_path = PLANS_DIR / plan_filename

            content = self._generate_plan_content(task_analysis, timestamp)

            with open(plan_path, "w", encoding="utf-8") as f:
                f.write(content)

            self.logger.info(f"Plan created: {plan_path.name}")
            return plan_path

        except Exception as e:
            self.logger.exception(f"Error generating plan: {e}")
            return None

    def _generate_plan_content(self, task: dict, timestamp: str) -> str:
        """Generate plan markdown content."""
        task_type = task["task_type"]
        hitl = task["hitl_required"]
        complexity = task["complexity"]

        # Generate steps based on task type
        steps = self._generate_steps(task_type, hitl, complexity)

        # Generate checkboxes
        checkboxes = "\n".join(f"- [ ] {step}" for step in steps)

        # Priority mapping
        priority_emoji = {"P0": "🔴", "P1": "🟠", "P2": "🔵", "P3": "⚪"}
        priority = task["metadata"].get("priority", "P2")
        priority_display = f"{priority_emoji.get(priority, '🔵')} {priority}"

        return f"""# 📋 Plan: {task["file_name"]}

**Created:** {timestamp}
**Task Type:** {task_type.replace("_", " ").title()}
**Priority:** {priority_display}
**Complexity:** {complexity.title()}
**HITL Required:** {"✅ Yes" if hitl else "❌ No"}
**Status:** 🟡 In Progress

---

## Task Analysis

| Attribute | Value |
|-----------|-------|
| **Source File** | {task["file_name"]} |
| **Task Type** | {task_type} |
| **Priority** | {priority} |
| **Complexity** | {complexity} |
| **HITL Required** | {hitl} |

---

## Execution Steps

{checkboxes}

---

## Multi-Step Workflow

""" + self._generate_workflow_diagram(task_type, hitl) + f"""

---

## Notes

- Plan generated by Ralph Loop Runner
- Update checkboxes as steps complete
- Move to Pending_Approval if HITL required
- Move to Done when all steps complete

---

*Generated: {timestamp} • Ralph Loop Pattern*
"""

    def _generate_steps(
        self, task_type: str, hitl: bool, complexity: str
    ) -> list[str]:
        """Generate execution steps based on task type."""
        base_steps = [
            "Review task requirements and metadata",
            "Analyze content for key information",
            "Execute primary task action",
            "Verify results against success criteria",
        ]

        # Add type-specific steps
        if task_type == "sales_lead":
            type_steps = [
                "Extract lead information (service, benefit, contact)",
                "Draft LinkedIn post or response",
                "Qualify lead (budget, timeline, decision maker)",
            ]
            if hitl:
                type_steps.append("Move to Pending_Approval for HITL review")
        elif task_type == "financial":
            type_steps = [
                "Extract invoice/payment details",
                "Verify amount and due date",
                "Schedule or process payment",
            ]
            if hitl:
                type_steps.append("Move to Pending_Approval for authorization")
        elif task_type == "email_task":
            type_steps = [
                "Parse email sender and subject",
                "Determine required response",
                "Draft and send response",
            ]
        elif task_type == "message_task":
            type_steps = [
                "Parse message content",
                "Identify sender and intent",
                "Craft appropriate response",
            ]
        elif task_type == "linkedin_task":
            type_steps = [
                "Extract lead/notification details",
                "Assess business opportunity",
                "Prepare response or post draft",
            ]
        else:
            type_steps = ["Execute task-specific actions"]

        # Add completion steps
        completion_steps = [
            "Document outcomes and actions taken",
            "Move task file to Done folder",
        ]

        return base_steps + type_steps + completion_steps

    def _generate_workflow_diagram(self, task_type: str, hitl: bool) -> str:
        """Generate ASCII workflow diagram."""
        if hitl:
            return """```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Needs_Action │ ──► │    Plans/    │ ──► │ Pending_     │
│   (Input)    │     │  (Process)   │     │ Approval/    │
└──────────────┘     └──────────────┘     └──────────────┘
                                                  │
                                                  ▼
┌──────────────┐                          ┌──────────────┐
│    Done/     │ ◄─────────────────────── │   Approved   │
│  (Complete)  │     (After HITL)         │  (Manual)    │
└──────────────┘                          └──────────────┘
```"""
        else:
            return """```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Needs_Action │ ──► │    Plans/    │ ──► │    Done/     │
│   (Input)    │     │  (Process)   │     │  (Complete)  │
└──────────────┘     └──────────────┘     └──────────────┘
```"""


# ─────────────────────────────────────────────────────────────────────────────
# File Mover
# ─────────────────────────────────────────────────────────────────────────────


class TaskFileMover:
    """Handles moving task files between folders."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def move_to_done(self, source_path: Path) -> Optional[Path]:
        """Move task file to Done folder."""
        return self._move_file(source_path, DONE_DIR, "done")

    def move_to_approval(self, source_path: Path) -> Optional[Path]:
        """Move task file to Pending_Approval folder."""
        return self._move_file(source_path, PENDING_APPROVAL_DIR, "approval")

    def _move_file(
        self, source_path: Path, dest_dir: Path, move_type: str
    ) -> Optional[Path]:
        """Move file to destination directory."""
        try:
            if not source_path.exists():
                self.logger.warning(f"Source file not found: {source_path}")
                return None

            dest_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d")
            dest_name = f"{timestamp}_{source_path.name}"
            dest_path = dest_dir / dest_name

            # Handle duplicates
            counter = 1
            while dest_path.exists():
                stem = source_path.stem
                suffix = source_path.suffix
                dest_name = f"{timestamp}_{stem}_{counter}{suffix}"
                dest_path = dest_dir / dest_name
                counter += 1

            shutil.move(str(source_path), str(dest_path))
            self.logger.info(f"Moved to {move_type}: {dest_path.name}")
            return dest_path

        except Exception as e:
            self.logger.error(f"Error moving file: {e}")
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Ralph Loop Runner (Main Class)
# ─────────────────────────────────────────────────────────────────────────────


class RalphLoopRunner:
    """Main Ralph Loop Runner class."""

    def __init__(self, prompt: str, max_iterations: int = DEFAULT_MAX_ITERATIONS) -> None:
        self.logger = setup_logging()
        self.prompt = prompt
        self.max_iterations = max_iterations
        self.metrics = LoopMetrics(max_iterations=max_iterations)
        self.state_manager = VaultStateManager(self.logger)
        self.analyzer = TaskAnalyzer(self.logger)
        self.plan_generator = PlanGenerator(self.logger)
        self.file_mover = TaskFileMover(self.logger)
        self.status = LoopStatus.RUNNING

    def run(self) -> LoopMetrics:
        """Execute the Ralph reasoning loop."""
        self.logger.info("=" * 60)
        self.logger.info("RALPH LOOP RUNNER - STARTING")
        self.logger.info(f"Prompt: {self.prompt}")
        self.logger.info(f"Max Iterations: {self.max_iterations}")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  🔄 RALPH LOOP RUNNER")
        print(f"  Prompt: {self.prompt}")
        print(f"  Max Iterations: {self.max_iterations}")
        print(f"  Completion Promise: {COMPLETION_PROMISE}")
        print(f"{'=' * 60}\n")

        try:
            self._run_loop()
        except Exception as e:
            self.logger.exception(f"Loop execution failed: {e}")
            self.status = LoopStatus.ERROR
        finally:
            self._finalize()

        return self.metrics

    def _run_loop(self) -> None:
        """Main loop execution."""
        while self.status == LoopStatus.RUNNING:
            self.metrics.iteration += 1

            self.logger.info(f"\n{'=' * 40}")
            self.logger.info(f"ITERATION {self.metrics.iteration}/{self.max_iterations}")
            self.logger.info(f"{'=' * 40}")

            print(f"\n🔄 Iteration {self.metrics.iteration}/{self.max_iterations}")

            # Check max iterations
            if self.metrics.iteration > self.max_iterations:
                self.logger.info("Max iterations reached")
                self.status = LoopStatus.MAX_ITERATIONS
                break

            # Get current state
            state = self.state_manager.get_state()
            self._print_state(state)

            # Check for pending tasks
            if not state.needs_action_files:
                self.logger.info("No pending tasks in Needs_Action")
                print("📭 No pending tasks in Needs_Action")
                self.status = LoopStatus.NO_TASKS
                break

            # Analyze tasks
            analyses = self.analyzer.analyze_files(state.needs_action_files)
            self.logger.info(f"Analyzed {len(analyses)} tasks")

            # Generate plans and process tasks
            for analysis in analyses:
                self._process_task(analysis)

            # Check for completion promise
            if self._check_completion_promise():
                self.logger.info("Completion promise detected")
                self.status = LoopStatus.COMPLETED
                break

            # Small delay between iterations
            time.sleep(1)

    def _process_task(self, analysis: dict) -> None:
        """Process a single task."""
        task_path = Path(analysis["file_path"])

        # Generate plan
        plan_path = self.plan_generator.generate_plan(analysis)
        if plan_path:
            self.metrics.plans_created += 1

        # Determine destination based on HITL requirement
        if analysis["hitl_required"]:
            dest_path = self.file_mover.move_to_approval(task_path)
            if dest_path:
                self.metrics.files_moved_to_approval += 1
                print(f"   📋 {analysis['file_name']} → Pending_Approval (HITL)")
        else:
            dest_path = self.file_mover.move_to_done(task_path)
            if dest_path:
                self.metrics.files_moved_to_done += 1
                self.metrics.tasks_processed += 1
                print(f"   ✅ {analysis['file_name']} → Done")

    def _check_completion_promise(self) -> bool:
        """Check if completion promise is found in recent logs."""
        # In a real implementation, this would check AI output
        # For now, we check if Needs_Action is empty
        state = self.state_manager.get_state()
        return state.needs_action_count == 0

    def _print_state(self, state: VaultState) -> None:
        """Print current vault state."""
        print(f"   📊 Vault State:")
        print(f"      Needs_Action:    {state.needs_action_count}")
        print(f"      Plans:           {state.plans_count}")
        print(f"      Done:            {state.done_count}")
        print(f"      Pending_Approval: {state.pending_approval_count}")

    def _finalize(self) -> None:
        """Finalize loop execution."""
        self.metrics.end_time = datetime.now()

        self.logger.info("=" * 60)
        self.logger.info("RALPH LOOP RUNNER - COMPLETE")
        self.logger.info(f"Final Status: {self.status.name}")
        self.logger.info(f"Total Iterations: {self.metrics.iteration}")
        self.logger.info(f"Duration: {self.metrics.duration_seconds:.2f}s")
        self.logger.info("=" * 60)

        self._print_summary()

    def _print_summary(self) -> None:
        """Print execution summary."""
        status_emoji = {
            LoopStatus.COMPLETED: "✅",
            LoopStatus.MAX_ITERATIONS: "⚠️",
            LoopStatus.NO_TASKS: "📭",
            LoopStatus.ERROR: "❌",
            LoopStatus.RUNNING: "🔄",
        }

        print(f"\n{'=' * 60}")
        print(f"  {status_emoji.get(self.status, '🔄')} RALPH LOOP COMPLETE")
        print(f"{'=' * 60}")
        print(f"  Status:             {self.status.name}")
        print(f"  Iterations:         {self.metrics.iteration}")
        print(f"  Duration:           {self.metrics.duration_seconds:.2f}s")
        print(f"  Plans Created:      {self.metrics.plans_created}")
        print(f"  Moved to Done:      {self.metrics.files_moved_to_done}")
        print(f"  Moved to Approval:  {self.metrics.files_moved_to_approval}")
        print(f"{'=' * 60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Ralph Loop Runner - Claude Reasoning Loop for Silver Tier"
    )
    parser.add_argument(
        "prompt",
        type=str,
        nargs="?",
        default="Process Needs_Action",
        help="Loop prompt/instruction",
    )
    parser.add_argument(
        "--max-iterations",
        "-m",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Maximum iterations (default: {DEFAULT_MAX_ITERATIONS})",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    runner = RalphLoopRunner(prompt=args.prompt, max_iterations=args.max_iterations)
    runner.run()


if __name__ == "__main__":
    main()
