#!/usr/bin/env python3
"""
Cross Domain Integrator - AI Employee Skill (Gold Tier)

Integrates personal (Gmail, WhatsApp) and business (LinkedIn, Twitter, Facebook) 
communications in one unified flow.

Workflow:
1. Scan /Needs_Action for incoming items
2. Classify as personal (email/message) or business (sales/project)
3. Route personal to HITL approval handler
4. Route business to Auto LinkedIn Poster or similar
5. Create unified summary in /Logs/cross_domain_[date].md

Usage:
    python skills/cross_domain_integrator.py
    # Or via Qwen CLI: @Cross_Domain_Integrator_process_Needs_Action

Keywords: cross-domain, integration, personal, business, classification
"""

import json
import logging
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Final, Optional

# Fix Windows console encoding for Unicode
if sys.platform == "win32":
    os.system("chcp 65001 >nul")
    sys.stdout.reconfigure(encoding="utf-8")

# Import audit logger
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
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
PENDING_APPROVAL_DIR: Final[Path] = VAULT_ROOT / "Pending_Approval"
APPROVED_DIR: Final[Path] = VAULT_ROOT / "Approved"
DONE_DIR: Final[Path] = VAULT_ROOT / "Done"
PLANS_DIR: Final[Path] = VAULT_ROOT / "Plans"
LOGS_DIR: Final[Path] = VAULT_ROOT / "Logs"
SKILLS_DIR: Final[Path] = VAULT_ROOT / "skills"

# Personal domain keywords (Gmail, WhatsApp, personal messages)
PERSONAL_KEYWORDS: Final[list[str]] = [
    "email",
    "message",
    "whatsapp",
    "gmail",
    "personal",
    "family",
    "friend",
    "reply",
    "respond",
    "inbox",
    "notification",
    "chat",
    "text",
    "phone",
    "call",
]

# Business domain keywords (LinkedIn, Twitter, Facebook, sales, projects)
BUSINESS_KEYWORDS: Final[list[str]] = [
    "sales",
    "client",
    "project",
    "lead",
    "opportunity",
    "linkedin",
    "twitter",
    "facebook",
    "business",
    "marketing",
    "post",
    "announcement",
    "partnership",
    "proposal",
    "contract",
    "invoice",
    "meeting",
    "presentation",
]

# Classification thresholds
CLASSIFICATION_THRESHOLD: Final[int] = 1
DEFAULT_PRIORITY: Final[str] = "P2"

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# ─────────────────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────────────────


def setup_logging() -> logging.Logger:
    """Configure logging with both file and console handlers."""
    logger = logging.getLogger("cross_domain_integrator")
    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    # File handler
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"cross_domain_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# ─────────────────────────────────────────────────────────────────────────────
# Enums & Data Classes
# ─────────────────────────────────────────────────────────────────────────────


class DomainType(Enum):
    """Domain classification for items."""

    PERSONAL = "personal"
    BUSINESS = "business"
    UNKNOWN = "unknown"


class RoutingAction(Enum):
    """Routing action for classified items."""

    ROUTE_TO_HITL = "route_to_hitl"
    ROUTE_TO_LINKEDIN_POSTER = "route_to_linkedin_poster"
    ROUTE_TO_AUTO_PROCESS = "route_to_auto_process"
    FLAG_FOR_REVIEW = "flag_for_review"


@dataclass
class ClassifiedItem:
    """Represents a classified item from Needs_Action."""

    file_path: Path
    content: str
    domain: DomainType
    routing_action: RoutingAction
    confidence: float
    keywords_found: list[str]
    priority: str
    classification_reason: str


@dataclass
class ProcessingResult:
    """Result of processing a single item."""

    item: ClassifiedItem
    success: bool
    destination_path: Optional[Path]
    message: str
    error: Optional[str] = None


@dataclass
class CrossDomainSummary:
    """Summary of cross-domain processing."""

    timestamp: datetime
    total_items: int
    personal_count: int
    business_count: int
    unknown_count: int
    routed_to_hitl: int
    routed_to_linkedin: int
    routed_to_auto: int
    items: list[ProcessingResult] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Task Analyzer (Classification Engine)
# ─────────────────────────────────────────────────────────────────────────────


class TaskAnalyzer:
    """Analyzes and classifies items into personal or business domains."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def classify_item(self, file_path: Path, content: str) -> ClassifiedItem:
        """Classify a single item."""
        self.logger.info(f"Classifying: {file_path.name}")

        content_lower = content.lower()

        # Find matching keywords
        personal_matches = [k for k in PERSONAL_KEYWORDS if k in content_lower]
        business_matches = [k for k in BUSINESS_KEYWORDS if k in content_lower]

        # Calculate scores
        personal_score = len(personal_matches)
        business_score = len(business_matches)

        # Determine domain
        if personal_score > business_score:
            domain = DomainType.PERSONAL
            routing = RoutingAction.ROUTE_TO_HITL
            keywords = personal_matches
            reason = f"Personal keywords detected: {', '.join(personal_matches)}"
            confidence = min(1.0, personal_score / 3.0)
        elif business_score > personal_score:
            domain = DomainType.BUSINESS
            # Check for LinkedIn/social media specific
            if any(k in content_lower for k in ["linkedin", "post", "announcement"]):
                routing = RoutingAction.ROUTE_TO_LINKEDIN_POSTER
            else:
                routing = RoutingAction.ROUTE_TO_AUTO_PROCESS
            keywords = business_matches
            reason = f"Business keywords detected: {', '.join(business_matches)}"
            confidence = min(1.0, business_score / 3.0)
        else:
            # Tie or no matches - check for explicit indicators
            domain, routing, keywords, reason, confidence = self._handle_tie_or_unknown(
                content_lower, file_path
            )

        # Determine priority
        priority = self._determine_priority(content_lower, domain)

        return ClassifiedItem(
            file_path=file_path,
            content=content,
            domain=domain,
            routing_action=routing,
            confidence=confidence,
            keywords_found=keywords,
            priority=priority,
            classification_reason=reason,
        )

    def _handle_tie_or_unknown(
        self, content_lower: str, file_path: Path
    ) -> tuple[DomainType, RoutingAction, list[str], str, float]:
        """Handle tie situations or unknown classifications."""
        # Check for explicit domain markers in content
        if "subject:" in content_lower or "to:" in content_lower:
            return (
                DomainType.PERSONAL,
                RoutingAction.ROUTE_TO_HITL,
                ["email_format"],
                "Email format detected",
                0.7,
            )
        elif "from:" in content_lower and "@" in content_lower:
            return (
                DomainType.PERSONAL,
                RoutingAction.ROUTE_TO_HITL,
                ["email_header"],
                "Email header format detected",
                0.8,
            )
        elif any(x in content_lower for x in ["http", "www.", "campaign"]):
            return (
                DomainType.BUSINESS,
                RoutingAction.ROUTE_TO_AUTO_PROCESS,
                ["web_reference"],
                "Web/campaign reference detected",
                0.6,
            )
        else:
            # Default to unknown - flag for review
            return (
                DomainType.UNKNOWN,
                RoutingAction.FLAG_FOR_REVIEW,
                [],
                "No clear domain indicators - requires manual review",
                0.3,
            )

    def _determine_priority(self, content_lower: str, domain: DomainType) -> str:
        """Determine priority based on content."""
        urgent_indicators = ["urgent", "asap", "immediately", "emergency", "critical"]
        high_indicators = ["important", "priority", "soon", "today"]

        if any(ind in content_lower for ind in urgent_indicators):
            return "P0"
        elif any(ind in content_lower for ind in high_indicators):
            return "P1"
        elif domain == DomainType.BUSINESS:
            return "P2"
        else:
            return "P3"


# ─────────────────────────────────────────────────────────────────────────────
# Domain Router
# ─────────────────────────────────────────────────────────────────────────────


class DomainRouter:
    """Routes classified items to appropriate handlers."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.hitl_handler_path: Optional[Path] = None
        self.linkedin_poster_path: Optional[Path] = None

        # Check for existing skill files
        self._locate_skills()

    def _locate_skills(self) -> None:
        """Locate existing skill files."""
        hitl_path = SKILLS_DIR / "hitl_approval_handler.py"
        linkedin_path = SKILLS_DIR / "auto_linkedin_poster.py"

        if hitl_path.exists():
            self.hitl_handler_path = hitl_path
            self.logger.info(f"HITL handler found: {hitl_path}")
        else:
            self.logger.warning("HITL handler not found")

        if linkedin_path.exists():
            self.linkedin_poster_path = linkedin_path
            self.logger.info(f"LinkedIn poster found: {linkedin_path}")
        else:
            self.logger.warning("LinkedIn poster not found")

    def route_item(self, item: ClassifiedItem) -> ProcessingResult:
        """Route a classified item to appropriate handler."""
        self.logger.info(f"Routing item: {item.file_path.name} -> {item.routing_action.value}")

        try:
            if item.routing_action == RoutingAction.ROUTE_TO_HITL:
                return self._route_to_hitl(item)
            elif item.routing_action == RoutingAction.ROUTE_TO_LINKEDIN_POSTER:
                return self._route_to_linkedin_poster(item)
            elif item.routing_action == RoutingAction.ROUTE_TO_AUTO_PROCESS:
                return self._route_to_auto_process(item)
            else:
                return self._flag_for_review(item)

        except Exception as e:
            self.logger.exception(f"Routing failed: {e}")
            return ProcessingResult(
                item=item,
                success=False,
                destination_path=None,
                message="Routing failed",
                error=str(e),
            )

    def _route_to_hitl(self, item: ClassifiedItem) -> ProcessingResult:
        """Route personal item to HITL approval handler."""
        self.logger.info(f"Routing to HITL: {item.file_path.name}")

        # Create HITL approval request
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"hitl_personal_{timestamp}_{item.file_path.stem}.md"
        dest_path = PENDING_APPROVAL_DIR / filename

        # Read original content
        with open(item.file_path, "r", encoding="utf-8") as f:
            original_content = f.read()

        # Create HITL wrapper
        hitl_content = self._create_hitl_wrapper(item, original_content)

        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(hitl_content)

        # Archive original to Done
        self._archive_original(item.file_path, "personal")

        return ProcessingResult(
            item=item,
            success=True,
            destination_path=dest_path,
            message=f"Routed to HITL: {dest_path.name}",
        )

    def _route_to_linkedin_poster(self, item: ClassifiedItem) -> ProcessingResult:
        """Route business item to Auto LinkedIn Poster."""
        self.logger.info(f"Routing to LinkedIn Poster: {item.file_path.name}")

        # Move file to a staging area for LinkedIn poster to pick up
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"linkedin_input_{timestamp}_{item.file_path.stem}.md"
        dest_path = PLANS_DIR / filename

        shutil.copy2(str(item.file_path), str(dest_path))

        # Archive original
        self._archive_original(item.file_path, "business_linkedin")

        # Optionally trigger LinkedIn poster
        if self.linkedin_poster_path:
            self._trigger_linkedin_poster()

        return ProcessingResult(
            item=item,
            success=True,
            destination_path=dest_path,
            message=f"Routed to LinkedIn Poster: {dest_path.name}",
        )

    def _route_to_auto_process(self, item: ClassifiedItem) -> ProcessingResult:
        """Route business item to auto-processing."""
        self.logger.info(f"Routing to Auto-Process: {item.file_path.name}")

        # Create processing plan
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"auto_process_{timestamp}_{item.file_path.stem}.md"
        dest_path = PLANS_DIR / filename

        # Read original content
        with open(item.file_path, "r", encoding="utf-8") as f:
            original_content = f.read()

        # Create processing plan
        plan_content = self._create_auto_process_plan(item, original_content)

        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(plan_content)

        # Archive original
        self._archive_original(item.file_path, "business_auto")

        return ProcessingResult(
            item=item,
            success=True,
            destination_path=dest_path,
            message=f"Routed to Auto-Process: {dest_path.name}",
        )

    def _flag_for_review(self, item: ClassifiedItem) -> ProcessingResult:
        """Flag unknown item for manual review."""
        self.logger.warning(f"Flagging for review: {item.file_path.name}")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"review_required_{timestamp}_{item.file_path.stem}.md"
        dest_path = PENDING_APPROVAL_DIR / filename

        # Read original content
        with open(item.file_path, "r", encoding="utf-8") as f:
            original_content = f.read()

        # Create review wrapper
        review_content = self._create_review_wrapper(item, original_content)

        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(review_content)

        # Archive original
        self._archive_original(item.file_path, "review")

        return ProcessingResult(
            item=item,
            success=True,
            destination_path=dest_path,
            message=f"Flagged for Review: {dest_path.name}",
        )

    def _create_hitl_wrapper(self, item: ClassifiedItem, original: str) -> str:
        """Create HITL wrapper for personal items."""
        timestamp = datetime.now().isoformat()

        return f"""---
type: hitl_personal_item
domain: personal
source_file: {item.file_path.name}
classified_at: {timestamp}
priority: {item.priority}
confidence: {item.confidence:.2f}
keywords: {', '.join(item.keywords_found)}
routing: hitl_approval
---

# 📧 Personal Item - HITL Review Required

**Classified:** {timestamp}
**Domain:** Personal (Email/Message)
**Priority:** {self._priority_badge(item.priority)}
**Confidence:** {item.confidence:.0%}
**Source:** {item.file_path.name}

---

## Classification Details

**Reason:** {item.classification_reason}

**Keywords Found:** {', '.join(item.keywords_found) if item.keywords_found else 'None'}

---

## Original Content

{original}

---

## Action Required

This item has been classified as **personal** and requires human review:

1. Review the content above
2. Determine appropriate action (reply, archive, delegate)
3. Execute action via Gmail/WhatsApp or appropriate channel
4. Move to `/Done` when complete

---

## Classification Metadata

| Field | Value |
|-------|-------|
| Domain | {item.domain.value} |
| Routing | {item.routing_action.value} |
| Keywords | {len(item.keywords_found)} |
| Priority | {item.priority} |

---

*Classified by Cross Domain Integrator • {timestamp}*
"""

    def _create_auto_process_plan(self, item: ClassifiedItem, original: str) -> str:
        """Create auto-processing plan for business items."""
        timestamp = datetime.now().isoformat()

        return f"""---
type: auto_process_plan
domain: business
source_file: {item.file_path.name}
created_at: {timestamp}
priority: {item.priority}
confidence: {item.confidence:.2f}
keywords: {', '.join(item.keywords_found)}
---

# 💼 Business Item - Auto Processing Plan

**Created:** {timestamp}
**Domain:** Business (Sales/Project)
**Priority:** {self._priority_badge(item.priority)}
**Source:** {item.file_path.name}

---

## Classification Details

**Reason:** {item.classification_reason}

**Keywords Found:** {', '.join(item.keywords_found) if item.keywords_found else 'None'}

---

## Original Content

{original}

---

## Processing Steps

1. ✅ **Classified** - Identified as business domain
2. 🔄 **Analyze** - Extract action items and requirements
3. 🔄 **Execute** - Perform required business actions
4. 🔄 **Document** - Log actions and outcomes
5. 🔄 **Archive** - Move to Done when complete

---

## Action Items

- [ ] Review business requirements
- [ ] Execute appropriate business action
- [ ] Document outcomes
- [ ] Archive completed work

---

*Created by Cross Domain Integrator • {timestamp}*
"""

    def _create_review_wrapper(self, item: ClassifiedItem, original: str) -> str:
        """Create review wrapper for unknown items."""
        timestamp = datetime.now().isoformat()

        return f"""---
type: manual_review_required
domain: unknown
source_file: {item.file_path.name}
flagged_at: {timestamp}
priority: {item.priority}
confidence: {item.confidence:.2f}
---

# ⚠️ Manual Review Required

**Flagged:** {timestamp}
**Domain:** Unknown/Unclear
**Priority:** {self._priority_badge(item.priority)}
**Confidence:** {item.confidence:.0%} (Low)

---

## Why Review is Needed

{item.classification_reason}

This item could not be confidently classified as personal or business.
Please review and determine appropriate routing.

---

## Original Content

{original}

---

## Review Instructions

1. Read the content carefully
2. Determine if this is personal or business related
3. Route to appropriate handler:
   - **Personal** → Move to HITL for email/message handling
   - **Business** → Move to Plans for auto-processing
4. Update this file with your decision

---

## Review Decision

**Reviewed By:** _______________

**Decision:** [ ] Personal  [ ] Business  [ ] Other

**Notes:**

_________________________________

---

*Flagged by Cross Domain Integrator • {timestamp}*
"""

    def _priority_badge(self, priority: str) -> str:
        """Get badge emoji for priority."""
        badges = {"P0": "🔴 P0 - Critical", "P1": "🟠 P1 - High", "P2": "🔵 P2 - Normal", "P3": "⚪ P3 - Low"}
        return badges.get(priority, f"🔵 {priority}")

    def _archive_original(self, source_path: Path, category: str) -> None:
        """Archive original file to Done folder."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d")
            filename = f"{timestamp}_{category}_{source_path.name}"
            dest_path = DONE_DIR / filename

            shutil.move(str(source_path), str(dest_path))
            self.logger.debug(f"Archived original to: {dest_path}")

        except Exception as e:
            self.logger.error(f"Failed to archive original: {e}")

    def _trigger_linkedin_poster(self) -> None:
        """Trigger LinkedIn poster skill."""
        if self.linkedin_poster_path:
            try:
                import subprocess

                self.logger.info("Triggering Auto LinkedIn Poster...")
                subprocess.run(
                    [sys.executable, str(self.linkedin_poster_path)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except Exception as e:
                self.logger.error(f"Failed to trigger LinkedIn poster: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Cross Domain Summary Logger
# ─────────────────────────────────────────────────────────────────────────────


class CrossDomainSummaryLogger:
    """Creates unified cross-domain processing summaries."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def create_summary(self, summary: CrossDomainSummary) -> Path:
        """Create unified cross-domain summary log."""
        timestamp = summary.timestamp.strftime("%Y-%m-%d")
        log_path = LOGS_DIR / f"cross_domain_{timestamp}.md"

        # Generate summary content
        content = self._generate_summary_content(summary)

        # Append to existing or create new
        if log_path.exists():
            # Append new entry
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("\n---\n\n")
                f.write(content)
        else:
            # Create new with header
            full_content = self._generate_full_log(content)
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(full_content)

        self.logger.info(f"Summary created: {log_path.name}")
        return log_path

    def _generate_full_log(self, entry: str) -> str:
        """Generate full log file with header."""
        return f"""# 🌐 Cross-Domain Integration Log

**Created:** {datetime.now().isoformat()}
**Description:** Unified log for personal and business domain processing

---

{entry}
"""

    def _generate_summary_content(self, summary: CrossDomainSummary) -> str:
        """Generate summary entry content."""
        timestamp = summary.timestamp.strftime("%Y-%m-%d %H:%M:%S")

        # Calculate percentages
        total = summary.total_items or 1
        personal_pct = (summary.personal_count / total) * 100
        business_pct = (summary.business_count / total) * 100

        # Build items table
        items_rows = []
        for result in summary.items:
            emoji = "✅" if result.success else "❌"
            domain_emoji = {"personal": "📧", "business": "💼", "unknown": "⚠️"}.get(
                result.item.domain.value, "❓"
            )
            items_rows.append(
                f"| {emoji} | {domain_emoji} | {result.item.file_path.name} | "
                f"{result.item.domain.value} | {result.item.routing_action.value} | "
                f"{result.message[:50]}... |"
            )

        items_table = "\n".join(items_rows) if items_rows else "| — | — | No items processed | — | — | — |"

        return f"""## Processing Run: {timestamp}

### Summary Statistics

| Metric | Value |
|--------|-------|
| **Total Items** | {summary.total_items} |
| **Personal** | {summary.personal_count} ({personal_pct:.1f}%) |
| **Business** | {summary.business_count} ({business_pct:.1f}%) |
| **Unknown** | {summary.unknown_count} |
| **Routed to HITL** | {summary.routed_to_hitl} |
| **Routed to LinkedIn** | {summary.routed_to_linkedin} |
| **Routed to Auto** | {summary.routed_to_auto} |

### Domain Distribution

- 📧 **Personal Domain:** {summary.personal_count} items
- 💼 **Business Domain:** {summary.business_count} items
- ⚠️ **Unknown/Unclear:** {summary.unknown_count} items

### Routing Actions

- 🎯 **HITL Approval:** {summary.routed_to_hitl} items
- 📱 **LinkedIn Poster:** {summary.routed_to_linkedin} items
- ⚙️ **Auto Process:** {summary.routed_to_auto} items

---

### Items Processed

| Status | Domain | File | Classification | Routing | Result |
|--------|--------|------|----------------|---------|--------|
{items_table}

---

### Detailed Results

""" + self._generate_detailed_results(summary)

    def _generate_detailed_results(self, summary: CrossDomainSummary) -> str:
        """Generate detailed results section."""
        details = []

        for i, result in enumerate(summary.items, 1):
            item = result.item
            details.append(f"""
#### Item {i}: {item.file_path.name}

| Field | Value |
|-------|-------|
| **Domain** | {item.domain.value.title()} |
| **Routing** | {item.routing_action.value} |
| **Priority** | {item.priority} |
| **Confidence** | {item.confidence:.0%} |
| **Keywords** | {', '.join(item.keywords_found) if item.keywords_found else 'None'} |
| **Status** | {'✅ Success' if result.success else '❌ Failed'} |
| **Destination** | {result.destination_path.name if result.destination_path else 'N/A'} |

**Classification Reason:** {item.classification_reason}

**Result Message:** {result.message}

{f'**Error:** {result.error}' if result.error else ''}

---
""")

        return "\n".join(details) if details else "*No items to show*\n"


# ─────────────────────────────────────────────────────────────────────────────
# Cross Domain Integrator (Main Class)
# ─────────────────────────────────────────────────────────────────────────────


class CrossDomainIntegrator:
    """Main Cross Domain Integrator skill class."""

    def __init__(self) -> None:
        self.logger = setup_logging()
        self.audit = AuditLogger("cross_domain_integrator", self.logger)
        self.analyzer = TaskAnalyzer(self.logger)
        self.router = DomainRouter(self.logger)
        self.summary_logger = CrossDomainSummaryLogger(self.logger)

        # Ensure directories exist
        for directory in [
            NEEDS_ACTION_DIR,
            PENDING_APPROVAL_DIR,
            APPROVED_DIR,
            DONE_DIR,
            PLANS_DIR,
            LOGS_DIR,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

        # Results tracking
        self.summary = CrossDomainSummary(
            timestamp=datetime.now(),
            total_items=0,
            personal_count=0,
            business_count=0,
            unknown_count=0,
            routed_to_hitl=0,
            routed_to_linkedin=0,
            routed_to_auto=0,
        )

    def run(self) -> CrossDomainSummary:
        """Execute the Cross Domain Integrator skill with audit logging."""
        # Use context manager for automatic start/end logging
        with AuditContext("cross_domain_integrator", "Processing Needs_Action", self.logger) as ctx:
            self.logger.info("=" * 60)
            self.logger.info("CROSS DOMAIN INTEGRATOR - STARTING")
            self.logger.info("=" * 60)

            print(f"\n{'=' * 60}")
            print("  🌐 CROSS DOMAIN INTEGRATOR")
            print(f"  Integrating Personal & Business Communications")
            print(f"{'=' * 60}\n")

            try:
                # Scan Needs_Action for items
                items = self._scan_needs_action()
                ctx.log_action(ActionType.TASK_RECEIVED, "Needs_Action", {"item_count": len(items)})
                self.summary.total_items = len(items)

                if not items:
                    print("📭 No items to process in Needs_Action\n")
                    self.logger.info("No items to process")
                    ctx.log_action(ActionType.TASK_COMPLETED, "Needs_Action", {"reason": "no_items"})
                    return self.summary

                # Process each item
                processed_count = 0
                for file_path in items:
                    self._process_item(file_path, ctx)
                    processed_count += 1

                # Create summary log
                log_path = self.summary_logger.create_summary(self.summary)
                ctx.log_action(ActionType.FILE_CREATED, str(log_path), {"type": "summary"})

                # Print summary
                self._print_summary(log_path)
                ctx.log_action(ActionType.TASK_COMPLETED, "cross_domain_integration", {"processed": processed_count})

                return self.summary

            except Exception as e:
                self.logger.exception(f"Skill execution failed: {e}")
                print(f"\n❌ Skill execution failed: {e}\n")
                ctx.log_action(ActionType.SKILL_ERROR, "cross_domain_integration", {"error": str(e)})
                raise  # Re-raise for context manager to capture

    def _scan_needs_action(self) -> list[Path]:
        """Scan Needs_Action folder for items."""
        try:
            md_files = list(NEEDS_ACTION_DIR.glob("*.md"))
            self.logger.info(f"Found {len(md_files)} items in Needs_Action")
            return md_files
        except Exception as e:
            self.logger.error(f"Error scanning Needs_Action: {e}")
            return []

    def _process_item(self, file_path: Path, ctx: Optional[AuditContext] = None) -> None:
        """Process a single item with audit logging."""
        self.logger.info(f"Processing: {file_path.name}")

        try:
            # Read content
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Classify
            classified = self.analyzer.classify_item(file_path, content)

            # Log classification
            if ctx:
                ctx.log_action(
                    ActionType.TASK_CLASSIFIED,
                    str(file_path),
                    {
                        "domain": classified.domain.value,
                        "routing": classified.routing_action.value,
                        "keywords": classified.keywords_found,
                    },
                )

            # Update summary counts
            self._update_counts(classified)

            # Route
            result = self.router.route_item(classified)

            # Log routing result
            if ctx:
                ctx.log_action(
                    ActionType.TASK_PROCESSED,
                    str(file_path),
                    {
                        "success": result.success,
                        "destination": str(result.destination_path) if result.destination_path else None,
                    },
                    result=ActionResult.SUCCESS if result.success else ActionResult.FAILURE,
                )

            # Track result
            self.summary.items.append(result)

            # Print status
            self._print_item_status(classified, result)

        except Exception as e:
            self.logger.exception(f"Error processing {file_path.name}: {e}")
            if ctx:
                ctx.log_action(ActionType.TASK_FAILED, str(file_path), {"error": str(e)})
            result = ProcessingResult(
                item=ClassifiedItem(
                    file_path=file_path,
                    content="",
                    domain=DomainType.UNKNOWN,
                    routing_action=RoutingAction.FLAG_FOR_REVIEW,
                    confidence=0.0,
                    keywords_found=[],
                    priority="P0",
                    classification_reason=f"Error: {e}",
                ),
                success=False,
                destination_path=None,
                message="Processing failed",
                error=str(e),
            )
            self.summary.items.append(result)

    def _update_counts(self, item: ClassifiedItem) -> None:
        """Update summary counts based on classification."""
        if item.domain == DomainType.PERSONAL:
            self.summary.personal_count += 1
        elif item.domain == DomainType.BUSINESS:
            self.summary.business_count += 1
        else:
            self.summary.unknown_count += 1

        if item.routing_action == RoutingAction.ROUTE_TO_HITL:
            self.summary.routed_to_hitl += 1
        elif item.routing_action == RoutingAction.ROUTE_TO_LINKEDIN_POSTER:
            self.summary.routed_to_linkedin += 1
        elif item.routing_action == RoutingAction.ROUTE_TO_AUTO_PROCESS:
            self.summary.routed_to_auto += 1

    def _print_item_status(self, item: ClassifiedItem, result: ProcessingResult) -> None:
        """Print status for processed item."""
        domain_emoji = {"personal": "📧", "business": "💼", "unknown": "⚠️"}.get(
            item.domain.value, "❓"
        )
        status_emoji = "✅" if result.success else "❌"

        print(f"  {status_emoji} {domain_emoji} {item.file_path.name}")
        print(f"     Domain: {item.domain.value} | Routing: {item.routing_action.value}")
        print(f"     Priority: {item.priority} | Confidence: {item.confidence:.0%}")
        print()

    def _print_summary(self, log_path: Path) -> None:
        """Print execution summary."""
        print(f"\n{'=' * 60}")
        print("  ✅ CROSS DOMAIN INTEGRATOR - COMPLETE")
        print(f"{'=' * 60}")
        print(f"  Total Items:        {self.summary.total_items}")
        print(f"  Personal (HITL):    {self.summary.personal_count}")
        print(f"  Business (Auto):    {self.summary.business_count}")
        print(f"  Unknown (Review):   {self.summary.unknown_count}")
        print(f"\n  📁 Log Path: {log_path}")
        print(f"{'=' * 60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Main entry point."""
    skill = CrossDomainIntegrator()
    skill.run()


if __name__ == "__main__":
    main()
