#!/usr/bin/env python3
"""
Weekly Audit Briefer - AI Employee Skill (Gold Tier)

Runs weekly to generate comprehensive CEO briefing:
- Reads /Done, /Logs, Company_Handbook.md, Business_Goals.md
- Audits tasks, revenue (from logs), bottlenecks
- Generates CEO Briefing in /Briefings/ceo_briefing_[date].md
- Uses pattern matching for subscriptions/expenses
- Integrates with scheduler for weekly run (Sunday)

Usage:
    python skills/weekly_audit_briefer.py
    # Or via Qwen CLI: @Weekly_Audit_Briefer_Generate

Schedule:
    Runs every Sunday at 9:00 AM via weekly_scheduler
"""

import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final, Optional

# Import audit logger
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from audit_logger import (
    AuditLogger,
    AuditContext,
    AuditSummaryGenerator,
    ActionType,
    ActionResult,
)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

VAULT_ROOT: Final[Path] = Path(__file__).parent.parent.resolve()
DONE_DIR: Final[Path] = VAULT_ROOT / "Done"
LOGS_DIR: Final[Path] = VAULT_ROOT / "Logs"
PLANS_DIR: Final[Path] = VAULT_ROOT / "Plans"
PENDING_APPROVAL_DIR: Final[Path] = VAULT_ROOT / "Pending_Approval"
NEEDS_ACTION_DIR: Final[Path] = VAULT_ROOT / "Needs_Action"
BRIEFINGS_DIR: Final[Path] = VAULT_ROOT / "Briefings"

HANDBOOK_FILE: Final[Path] = VAULT_ROOT / "Company_Handbook.md"
BUSINESS_GOALS_FILE: Final[Path] = VAULT_ROOT / "Business_Goals.md"

# Revenue/Expense patterns for pattern matching
REVENUE_PATTERNS: Final[list[str]] = [
    r"revenue[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)",
    r"payment\s*(?:received|collected)[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)",
    r"income[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)",
    r"sale[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)",
    r"\$([\d,]+(?:\.\d{2})?)\s*(?:received|earned|collected)",
]

EXPENSE_PATTERNS: Final[list[str]] = [
    r"expense[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)",
    r"cost[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)",
    r"payment\s*(?:sent|made)[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)",
    r"subscription[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)",
    r"spent[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)",
    r"\$([\d,]+(?:\.\d{2})?)\s*(?:spent|paid|cost)",
]

SUBSCRIPTION_PATTERNS: Final[list[str]] = [
    r"subscription[:\s]+([^\n]+)",
    r"monthly[:\s]+([^\n]+)",
    r"recurring[:\s]+([^\n]+)",
    r"service[:\s]+([^\n]+).*(?:monthly|annual|yearly)",
]

# Day for weekly run (6 = Sunday, 0 = Monday)
WEEKLY_RUN_DAY: Final[int] = 6  # Sunday

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# ─────────────────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────────────────


def setup_logging() -> logging.Logger:
    """Configure logging with both file and console handlers."""
    logger = logging.getLogger("weekly_audit_briefer")
    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    # File handler
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"weekly_audit_{datetime.now().strftime('%Y-%m-%d')}.log"
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
class FinancialSummary:
    """Financial data extracted from logs."""

    revenue: float = 0.0
    expenses: float = 0.0
    subscriptions: list[dict] = field(default_factory=list)
    transactions: list[dict] = field(default_factory=list)


@dataclass
class TaskMetrics:
    """Task completion metrics."""

    total_completed: int = 0
    this_week: int = 0
    last_week: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    avg_completion_time: str = "N/A"


@dataclass
class Bottleneck:
    """Identified bottleneck."""

    category: str
    description: str
    severity: str  # low, medium, high
    evidence: str
    suggestion: str


@dataclass
class WeeklyAudit:
    """Complete weekly audit data."""

    week_start: datetime
    week_end: datetime
    generated_at: datetime
    financial: FinancialSummary
    tasks: TaskMetrics
    bottlenecks: list[Bottleneck]
    goals_progress: dict[str, str]
    suggestions: list[str]


# ─────────────────────────────────────────────────────────────────────────────
# Data Reader
# ─────────────────────────────────────────────────────────────────────────────


class DataReader:
    """Reads and parses data from vault files."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def read_done_folder(self) -> list[Path]:
        """Read all files from Done folder."""
        try:
            if not DONE_DIR.exists():
                self.logger.warning("Done folder not found")
                return []

            files = list(DONE_DIR.glob("*.md"))
            self.logger.info(f"Found {len(files)} files in Done folder")
            return files

        except Exception as e:
            self.logger.error(f"Error reading Done folder: {e}")
            return []

    def read_logs(self, days_back: int = 7) -> list[str]:
        """Read log files from the past N days."""
        logs_content = []

        try:
            if not LOGS_DIR.exists():
                self.logger.warning("Logs folder not found")
                return logs_content

            cutoff_date = datetime.now() - timedelta(days=days_back)

            for log_file in LOGS_DIR.glob("*.log"):
                try:
                    modified = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if modified >= cutoff_date:
                        with open(log_file, "r", encoding="utf-8") as f:
                            logs_content.append(f.read())
                except Exception:
                    continue

            # Also read .md logs
            for log_file in LOGS_DIR.glob("*.md"):
                try:
                    modified = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if modified >= cutoff_date:
                        with open(log_file, "r", encoding="utf-8") as f:
                            logs_content.append(f.read())
                except Exception:
                    continue

            self.logger.info(f"Read {len(logs_content)} log files")
            return logs_content

        except Exception as e:
            self.logger.error(f"Error reading logs: {e}")
            return []

    def read_handbook(self) -> str:
        """Read Company Handbook."""
        try:
            if not HANDBOOK_FILE.exists():
                self.logger.warning("Company Handbook not found")
                return ""

            with open(HANDBOOK_FILE, "r", encoding="utf-8") as f:
                return f.read()

        except Exception as e:
            self.logger.error(f"Error reading handbook: {e}")
            return ""

    def read_business_goals(self) -> str:
        """Read Business Goals file."""
        try:
            if not BUSINESS_GOALS_FILE.exists():
                self.logger.warning("Business Goals not found")
                return ""

            with open(BUSINESS_GOALS_FILE, "r", encoding="utf-8") as f:
                return f.read()

        except Exception as e:
            self.logger.error(f"Error reading business goals: {e}")
            return ""

    def read_file_content(self, file_path: Path) -> str:
        """Read content of a single file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            self.logger.debug(f"Error reading {file_path}: {e}")
            return ""


# ─────────────────────────────────────────────────────────────────────────────
# Financial Analyzer
# ─────────────────────────────────────────────────────────────────────────────


class FinancialAnalyzer:
    """Analyzes financial data from logs and files."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def analyze(self, logs: list[str], done_files: list[str]) -> FinancialSummary:
        """Extract financial data from logs and files."""
        summary = FinancialSummary()

        all_content = "\n".join(logs + done_files)

        # Extract revenue
        summary.revenue = self._extract_amounts(all_content, REVENUE_PATTERNS)
        self.logger.info(f"Revenue found: ${summary.revenue:.2f}")

        # Extract expenses
        summary.expenses = self._extract_amounts(all_content, EXPENSE_PATTERNS)
        self.logger.info(f"Expenses found: ${summary.expenses:.2f}")

        # Extract subscriptions
        summary.subscriptions = self._extract_subscriptions(all_content)
        self.logger.info(f"Subscriptions found: {len(summary.subscriptions)}")

        # Calculate net
        summary.transactions.append({
            "type": "summary",
            "revenue": summary.revenue,
            "expenses": summary.expenses,
            "net": summary.revenue - summary.expenses,
        })

        return summary

    def _extract_amounts(self, content: str, patterns: list[str]) -> float:
        """Extract monetary amounts using patterns."""
        total = 0.0

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                try:
                    # Remove commas and convert to float
                    amount = float(match.replace(",", ""))
                    total += amount
                except ValueError:
                    continue

        return total

    def _extract_subscriptions(self, content: str) -> list[dict]:
        """Extract subscription information."""
        subscriptions = []

        for pattern in SUBSCRIPTION_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                sub_info = {
                    "name": match.strip()[:100],
                    "detected": True,
                }

                # Try to find amount associated with subscription
                amount_match = re.search(r"\$([\d,]+(?:\.\d{2})?)", match)
                if amount_match:
                    sub_info["amount"] = float(amount_match.group(1).replace(",", ""))

                # Check for frequency
                if any(word in match.lower() for word in ["monthly", "month"]):
                    sub_info["frequency"] = "monthly"
                elif any(word in match.lower() for word in ["annual", "yearly", "year"]):
                    sub_info["frequency"] = "yearly"
                else:
                    sub_info["frequency"] = "unknown"

                subscriptions.append(sub_info)

        return subscriptions


# ─────────────────────────────────────────────────────────────────────────────
# Task Analyzer
# ─────────────────────────────────────────────────────────────────────────────


class TaskAnalyzer:
    """Analyzes task completion metrics."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def analyze(
        self, done_files: list[Path], logs: list[str]
    ) -> TaskMetrics:
        """Analyze task completion metrics."""
        metrics = TaskMetrics()

        now = datetime.now()
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        metrics.total_completed = len(done_files)

        # Count this week vs last week
        for file_path in done_files:
            try:
                # Extract date from filename (format: YYYY-MM-DD_*)
                match = re.match(r"(\d{4}-\d{2}-\d{2})", file_path.name)
                if match:
                    file_date = datetime.strptime(match.group(1), "%Y-%m-%d")

                    if file_date >= week_ago:
                        metrics.this_week += 1
                    elif file_date >= two_weeks_ago:
                        metrics.last_week += 1

                # Extract type from filename
                if "_email_" in file_path.name.lower():
                    metrics.by_type["email"] = metrics.by_type.get("email", 0) + 1
                elif "_facebook_" in file_path.name.lower() or "_instagram_" in file_path.name.lower():
                    metrics.by_type["social"] = metrics.by_type.get("social", 0) + 1
                elif "_twitter_" in file_path.name.lower():
                    metrics.by_type["twitter"] = metrics.by_type.get("twitter", 0) + 1
                elif "_linkedin_" in file_path.name.lower():
                    metrics.by_type["linkedin"] = metrics.by_type.get("linkedin", 0) + 1
                elif "_whatsapp_" in file_path.name.lower():
                    metrics.by_type["whatsapp"] = metrics.by_type.get("whatsapp", 0) + 1
                else:
                    metrics.by_type["other"] = metrics.by_type.get("other", 0) + 1

            except Exception as e:
                self.logger.debug(f"Error analyzing file {file_path.name}: {e}")

        # Calculate average completion time from logs
        metrics.avg_completion_time = self._calculate_avg_completion(logs)

        return metrics

    def _calculate_avg_completion(self, logs: list[str]) -> str:
        """Calculate average task completion time."""
        # Look for duration patterns in logs
        duration_pattern = r"(?:duration|took|completed in)[:\s]+(\d+)\s*(?:seconds|minutes|hours)"
        total_seconds = 0
        count = 0

        for log in logs:
            matches = re.findall(duration_pattern, log, re.IGNORECASE)
            for match in matches:
                try:
                    # Assume minutes if not specified
                    total_seconds += int(match) * 60
                    count += 1
                except ValueError:
                    continue

        if count > 0:
            avg_seconds = total_seconds / count
            if avg_seconds < 60:
                return f"{int(avg_seconds)} seconds"
            elif avg_seconds < 3600:
                return f"{int(avg_seconds / 60)} minutes"
            else:
                return f"{avg_seconds / 3600:.1f} hours"

        return "N/A"


# ─────────────────────────────────────────────────────────────────────────────
# Bottleneck Detector
# ─────────────────────────────────────────────────────────────────────────────


class BottleneckDetector:
    """Detects bottlenecks from logs and file patterns."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def detect(
        self, logs: list[str], done_files: list[str], pending_count: int, needs_action_count: int
    ) -> list[Bottleneck]:
        """Detect potential bottlenecks."""
        bottlenecks = []
        all_content = "\n".join(logs + done_files)

        # Check for pending approval backlog
        if pending_count > 5:
            bottlenecks.append(Bottleneck(
                category="Approval Workflow",
                description=f"{pending_count} items awaiting approval",
                severity="high" if pending_count > 10 else "medium",
                evidence=f"Pending_Approval folder has {pending_count} files",
                suggestion="Review and process pending approvals daily",
            ))

        # Check for Needs_Action backlog
        if needs_action_count > 10:
            bottlenecks.append(Bottleneck(
                category="Task Processing",
                description=f"{needs_action_count} items in Needs_Action",
                severity="high" if needs_action_count > 20 else "medium",
                evidence=f"Needs_Action folder has {needs_action_count} files",
                suggestion="Process Needs_Action items more frequently",
            ))

        # Check for error patterns in logs
        error_count = all_content.lower().count("error")
        if error_count > 10:
            bottlenecks.append(Bottleneck(
                category="System Errors",
                description=f"{error_count} errors detected in logs",
                severity="medium",
                evidence=f"Log files contain {error_count} error mentions",
                suggestion="Review error logs and address recurring issues",
            ))

        # Check for timeout patterns
        timeout_count = all_content.lower().count("timeout")
        if timeout_count > 5:
            bottlenecks.append(Bottleneck(
                category="Performance",
                description=f"{timeout_count} timeout events detected",
                severity="medium",
                evidence=f"Log files contain {timeout_count} timeout mentions",
                suggestion="Consider increasing timeout values or optimizing operations",
            ))

        # Check for authentication issues
        auth_issues = all_content.lower().count("auth") + all_content.lower().count("credential")
        if auth_issues > 5:
            bottlenecks.append(Bottleneck(
                category="Authentication",
                description="Multiple authentication-related events",
                severity="low",
                evidence="Auth/credential mentions in logs",
                suggestion="Review token expiration and refresh mechanisms",
            ))

        return bottlenecks


# ─────────────────────────────────────────────────────────────────────────────
# Goals Tracker
# ─────────────────────────────────────────────────────────────────────────────


class GoalsTracker:
    """Tracks progress against business goals."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def track(self, goals_content: str, logs: list[str]) -> dict[str, str]:
        """Track progress against business goals."""
        progress = {}

        if not goals_content:
            return {"status": "No business goals file found"}

        # Extract goals from the document
        goal_patterns = [
            r"##\s*Goal[:\s]+([^\n]+)",
            r"###\s*([^\n]+)",
            r"-\s*\[([ x])\]\s*([^\n]+)",
        ]

        all_logs = "\n".join(logs)

        for pattern in goal_patterns:
            matches = re.findall(pattern, goals_content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    goal_name = match[1] if len(match) > 1 else match[0]
                    status = match[0] if len(match) > 1 and match[0] in ["x", " "] else "in_progress"
                else:
                    goal_name = match
                    status = "in_progress"

                # Check if goal is mentioned in logs (indicating progress)
                if goal_name.lower() in all_logs.lower():
                    progress[goal_name.strip()] = "🟡 In Progress"
                elif status == "x":
                    progress[goal_name.strip()] = "✅ Complete"
                else:
                    progress[goal_name.strip()] = "⚪ Pending"

        if not progress:
            progress["Overall"] = "🟢 Tracking goals from Business_Goals.md"

        return progress


# ─────────────────────────────────────────────────────────────────────────────
# Briefing Generator
# ─────────────────────────────────────────────────────────────────────────────


class BriefingGenerator:
    """Generates CEO briefing document."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.audit_summary_gen = AuditSummaryGenerator(logger)
        BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)

    def generate(self, audit: WeeklyAudit) -> Path:
        """Generate CEO briefing document."""
        timestamp = audit.generated_at.strftime("%Y-%m-%d")
        week_start = audit.week_start.strftime("%Y-%m-%d")
        week_end = audit.week_end.strftime("%Y-%m-%d")

        filename = f"ceo_briefing_{timestamp}.md"
        filepath = BRIEFINGS_DIR / filename

        content = self._generate_content(audit, week_start, week_end)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        self.logger.info(f"CEO briefing created: {filepath}")
        return filepath

    def _generate_content(self, audit: WeeklyAudit, week_start: str, week_end: str) -> str:
        """Generate briefing markdown content."""
        net_profit = audit.financial.revenue - audit.financial.expenses
        profit_margin = (
            (net_profit / audit.financial.revenue * 100)
            if audit.financial.revenue > 0
            else 0
        )

        # Build task breakdown
        task_breakdown = "\n".join(
            f"- **{k.title()}:** {v}" for k, v in audit.tasks.by_type.items()
        )

        # Build bottlenecks section
        bottlenecks_md = self._format_bottlenecks(audit.bottlenecks)

        # Build goals progress
        goals_md = "\n".join(
            f"- {goal}: {status}" for goal, status in audit.goals_progress.items()
        )

        # Build suggestions
        suggestions_md = "\n".join(f"- {s}" for s in audit.suggestions)

        # Build subscriptions table
        subscriptions_md = self._format_subscriptions(audit.financial.subscriptions)

        return f"""# 📊 CEO Weekly Briefing

**Week:** {week_start} to {week_end}
**Generated:** {audit.generated_at.strftime('%Y-%m-%d %H:%M:%S')}
**Status:** 🟢 Complete

---

## 📈 Executive Summary

| Metric | Value | Trend |
|--------|-------|-------|
| **Tasks Completed** | {audit.tasks.this_week} | {self._trend_emoji(audit.tasks.this_week, audit.tasks.last_week)} |
| **Revenue** | ${audit.financial.revenue:,.2f} | — |
| **Expenses** | ${audit.financial.expenses:,.2f} | — |
| **Net Profit** | ${net_profit:,.2f} | {profit_margin:.1f}% margin |
| **Pending Approvals** | {self._get_pending_count()} | — |

---

## 💰 Revenue Analysis

### Financial Summary

| Category | Amount |
|----------|--------|
| **Total Revenue** | ${audit.financial.revenue:,.2f} |
| **Total Expenses** | ${audit.financial.expenses:,.2f} |
| **Net Profit** | ${net_profit:,.2f} |
| **Profit Margin** | {profit_margin:.1f}% |

{subscriptions_md}

### Transactions Detected

{self._format_transactions(audit.financial.transactions)}

---

## ✅ Completed Tasks

### This Week: {audit.tasks.this_week} tasks

{task_breakdown if task_breakdown else '- No categorized tasks'}

### Last Week: {audit.tasks.last_week} tasks

**Trend:** {self._trend_text(audit.tasks.this_week, audit.tasks.last_week)}

### Average Completion Time

{audit.tasks.avg_completion_time}

---

## 🚧 Bottlenecks Identified

{bottlenecks_md if bottlenecks_md else '✅ No significant bottlenecks detected'}

---

## 🎯 Business Goals Progress

{goals_md}

---

## 💡 Suggestions & Recommendations

{suggestions_md if suggestions_md else '- Continue current operations'}

---

## 📊 System Audit Summary

{self.audit_summary_gen.generate_briefing_section()}

---

## 📋 Action Items for This Week

- [ ] Review pending approvals in Pending_Approval folder
- [ ] Process any items in Needs_Action
- [ ] Review bottleneck suggestions above
- [ ] Update Business_Goals.md with progress
- [ ] Schedule follow-up on high-severity bottlenecks
- [ ] Review audit summary for anomalies

---

## 📎 Appendix

### Data Sources

- `/Done` — {audit.tasks.total_completed} total completed tasks
- `/Logs` — System execution logs
- `Company_Handbook.md` — Operating guidelines
- `Business_Goals.md` — Strategic objectives

### Methodology

- Revenue/Expenses: Extracted via pattern matching from logs and task files
- Task counts: Based on file timestamps in Done folder
- Bottlenecks: Detected from folder sizes and log error patterns
- Goals: Tracked against Business_Goals.md

---

*Generated by Weekly Audit Briefer • AI Employee System*
"""

    def _format_bottlenecks(self, bottlenecks: list[Bottleneck]) -> str:
        """Format bottlenecks as markdown."""
        if not bottlenecks:
            return ""

        lines = []
        for i, b in enumerate(bottlenecks, 1):
            severity_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(
                b.severity, "⚪"
            )
            lines.append(f"""
#### {i}. {b.category} {severity_emoji}

- **Description:** {b.description}
- **Evidence:** {b.evidence}
- **Suggestion:** {b.suggestion}
""")

        return "\n".join(lines)

    def _format_subscriptions(self, subscriptions: list[dict]) -> str:
        """Format subscriptions as markdown table."""
        if not subscriptions:
            return "### Subscriptions\n\n_No recurring subscriptions detected_"

        lines = ["### Subscriptions", "", "| Name | Amount | Frequency |", "|------|--------|-----------|"]

        for sub in subscriptions:
            name = sub.get("name", "Unknown")[:30]
            amount = f"${sub.get('amount', 0):,.2f}" if "amount" in sub else "N/A"
            frequency = sub.get("frequency", "unknown")
            lines.append(f"| {name} | {amount} | {frequency} |")

        return "\n".join(lines)

    def _format_transactions(self, transactions: list[dict]) -> str:
        """Format transactions."""
        if not transactions:
            return "_No detailed transactions recorded_"

        lines = []
        for t in transactions:
            if t.get("type") == "summary":
                lines.append(f"- Revenue: ${t.get('revenue', 0):,.2f}")
                lines.append(f"- Expenses: ${t.get('expenses', 0):,.2f}")
                lines.append(f"- Net: ${t.get('net', 0):,.2f}")

        return "\n".join(lines) if lines else "_No transactions_"

    def _trend_emoji(self, current: int, previous: int) -> str:
        """Get trend emoji."""
        if current > previous:
            return "📈 Up"
        elif current < previous:
            return "📉 Down"
        else:
            return "➡️ Same"

    def _trend_text(self, current: int, previous: int) -> str:
        """Get trend description."""
        if previous == 0:
            return "First week of tracking"
        change = current - previous
        pct = (change / previous * 100) if previous > 0 else 0
        return f"{change:+d} tasks ({pct:+.1f}%) from last week"

    def _get_pending_count(self) -> int:
        """Get pending approval count."""
        try:
            return len(list(PENDING_APPROVAL_DIR.glob("*.md")))
        except Exception:
            return 0


# ─────────────────────────────────────────────────────────────────────────────
# Weekly Audit Briefer (Main Class)
# ─────────────────────────────────────────────────────────────────────────────


class WeeklyAuditBriefer:
    """Main Weekly Audit Briefer skill class."""

    def __init__(self) -> None:
        self.logger = setup_logging()
        self.data_reader = DataReader(self.logger)
        self.financial_analyzer = FinancialAnalyzer(self.logger)
        self.task_analyzer = TaskAnalyzer(self.logger)
        self.bottleneck_detector = BottleneckDetector(self.logger)
        self.goals_tracker = GoalsTracker(self.logger)
        self.briefing_generator = BriefingGenerator(self.logger)

        # Ensure directories exist
        for directory in [BRIEFINGS_DIR, LOGS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

    def run(self, force: bool = False) -> Optional[Path]:
        """
        Execute the Weekly Audit Briefer skill.

        Args:
            force: If True, run regardless of day of week

        Returns:
            Path to generated briefing file, or None if not run
        """
        self.logger.info("=" * 60)
        self.logger.info("WEEKLY AUDIT BRIEFER - STARTING")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  📊 WEEKLY AUDIT BRIEFER")
        print(f"  Generating CEO Weekly Briefing...")
        print(f"{'=' * 60}\n")

        # Check if it's the right day (Sunday)
        today = datetime.now()
        if not force and today.weekday() != WEEKLY_RUN_DAY:
            day_name = today.strftime("%A")
            self.logger.info(f"Not scheduled run day ({day_name}). Use force=True to run.")
            print(f"📅 Not scheduled run day ({day_name}). Use --force to run anyway.")
            return None

        try:
            # Calculate week boundaries
            week_end = today
            week_start = today - timedelta(days=6)

            # Read data
            self.logger.info("Reading data sources...")
            done_files = self.data_reader.read_done_folder()
            logs = self.data_reader.read_logs(days_back=7)
            handbook = self.data_reader.read_handbook()
            business_goals = self.data_reader.read_business_goals()

            # Read file contents for analysis
            done_contents = [
                self.data_reader.read_file_content(f) for f in done_files
            ]

            # Analyze finances
            self.logger.info("Analyzing finances...")
            financial = self.financial_analyzer.analyze(logs, done_contents)

            # Analyze tasks
            self.logger.info("Analyzing tasks...")
            tasks = self.task_analyzer.analyze(done_files, logs)

            # Detect bottlenecks
            self.logger.info("Detecting bottlenecks...")
            pending_count = len(list(PENDING_APPROVAL_DIR.glob("*.md")))
            needs_action_count = len(list(NEEDS_ACTION_DIR.glob("*.md")))
            bottlenecks = self.bottleneck_detector.detect(
                logs, done_contents, pending_count, needs_action_count
            )

            # Track goals
            self.logger.info("Tracking goals...")
            goals_progress = self.goals_tracker.track(business_goals, logs)

            # Generate suggestions
            suggestions = self._generate_suggestions(
                financial, tasks, bottlenecks, goals_progress
            )

            # Create audit object
            audit = WeeklyAudit(
                week_start=week_start,
                week_end=week_end,
                generated_at=datetime.now(),
                financial=financial,
                tasks=tasks,
                bottlenecks=bottlenecks,
                goals_progress=goals_progress,
                suggestions=suggestions,
            )

            # Generate briefing
            self.logger.info("Generating CEO briefing...")
            briefing_path = self.briefing_generator.generate(audit)

            # Print summary
            self._print_summary(audit, briefing_path)

            return briefing_path

        except Exception as e:
            self.logger.exception(f"Skill execution failed: {e}")
            print(f"\n❌ Skill execution failed: {e}\n")
            return None

    def _generate_suggestions(
        self,
        financial: FinancialSummary,
        tasks: TaskMetrics,
        bottlenecks: list[Bottleneck],
        goals_progress: dict[str, str],
    ) -> list[str]:
        """Generate suggestions based on analysis."""
        suggestions = []

        # Financial suggestions
        if financial.revenue > 0 and financial.expenses > financial.revenue:
            suggestions.append("💰 Expenses exceed revenue - review cost structure")
        if financial.subscriptions:
            suggestions.append(f"📋 Review {len(financial.subscriptions)} subscription(s) for optimization")

        # Task suggestions
        if tasks.this_week < tasks.last_week and tasks.last_week > 0:
            suggestions.append("📉 Task completion down from last week - investigate blockers")
        if tasks.this_week == 0:
            suggestions.append("⚠️ No tasks completed this week - review workflow")

        # Bottleneck suggestions
        high_severity = [b for b in bottlenecks if b.severity == "high"]
        if high_severity:
            suggestions.append(f"🔴 Address {len(high_severity)} high-severity bottleneck(s) immediately")

        # Goal suggestions
        pending_goals = [g for g, s in goals_progress.items() if "Pending" in s]
        if pending_goals:
            suggestions.append(f"🎯 {len(pending_goals)} goal(s) pending - prioritize progress")

        # Default suggestions if none generated
        if not suggestions:
            suggestions.append("✅ All systems operational - maintain current pace")
            suggestions.append("📈 Consider setting more ambitious goals")

        return suggestions

    def _print_summary(self, audit: WeeklyAudit, briefing_path: Path) -> None:
        """Print execution summary."""
        net_profit = audit.financial.revenue - audit.financial.expenses

        print(f"\n{'=' * 60}")
        print("  ✅ WEEKLY AUDIT BRIEFER - COMPLETE")
        print(f"{'=' * 60}")
        print(f"  Week:               {audit.week_start.strftime('%Y-%m-%d')} to {audit.week_end.strftime('%Y-%m-%d')}")
        print(f"  Tasks Completed:    {audit.tasks.this_week}")
        print(f"  Revenue:            ${audit.financial.revenue:,.2f}")
        print(f"  Expenses:           ${audit.financial.expenses:,.2f}")
        print(f"  Net Profit:         ${net_profit:,.2f}")
        print(f"  Bottlenecks:        {len(audit.bottlenecks)}")
        print(f"\n  📁 Briefing: {briefing_path}")
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

    # Check for force flag
    force = "--force" in sys.argv or "-f" in sys.argv

    skill = WeeklyAuditBriefer()
    result = skill.run(force=force)

    if result:
        print(f"✅ Briefing generated: {result}")
    elif not force:
        print("ℹ️  Skill not run (not scheduled day). Use --force to run anyway.")


if __name__ == "__main__":
    main()
