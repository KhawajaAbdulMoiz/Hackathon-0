#!/usr/bin/env python3
"""
Auto LinkedIn Poster - AI Employee Skill (Silver Tier)

Scans Needs_Action folder for sales/business lead messages,
drafts LinkedIn posts, and saves for human approval.

Usage:
    python skills/auto_linkedin_poster.py
    # Or via Qwen CLI: @skill auto_linkedin_poster

Keywords: sales, client, project, lead, opportunity
"""

import logging
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

VAULT_ROOT: Final[Path] = Path(__file__).parent.parent.resolve()
NEEDS_ACTION_DIR: Final[Path] = VAULT_ROOT / "Needs_Action"
PLANS_DIR: Final[Path] = VAULT_ROOT / "Plans"
PENDING_APPROVAL_DIR: Final[Path] = VAULT_ROOT / "Pending_Approval"
HANDBOOK_FILE: Final[Path] = VAULT_ROOT / "Company_Handbook.md"

KEYWORDS: Final[list[str]] = ["sales", "client", "project", "lead", "opportunity"]
POST_TEMPLATE: Final[str] = (
    "Excited to offer {service} for {benefit}! DM for more. #Business #Opportunity"
)

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# ─────────────────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────────────────


def setup_logging() -> logging.Logger:
    """Configure logging with both file and console handlers."""
    logger = logging.getLogger("auto_linkedin_poster")
    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    # File handler
    LOGS_DIR = VAULT_ROOT / "Logs"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"linkedin_poster_{datetime.now().strftime('%Y-%m-%d')}.log"
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
class LeadInfo:
    """Represents extracted lead information."""

    file_path: Path
    content: str
    keywords_found: list[str]
    service_hint: str
    benefit_hint: str
    priority: str


@dataclass
class LinkedInPost:
    """Represents a drafted LinkedIn post."""

    content: str
    service: str
    benefit: str
    source_lead: str
    timestamp: datetime
    status: str = "draft"


# ─────────────────────────────────────────────────────────────────────────────
# Handbook Reader
# ─────────────────────────────────────────────────────────────────────────────


class HandbookReader:
    """Reads Company Handbook for tone and language guidelines."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.tone_guidelines: list[str] = []

    def load_guidelines(self) -> bool:
        """Load tone guidelines from handbook."""
        try:
            if not HANDBOOK_FILE.exists():
                self.logger.warning("Company Handbook not found, using defaults")
                self._set_default_guidelines()
                return True

            with open(HANDBOOK_FILE, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract tone guidelines
            if "Tone" in content:
                tone_section = content.split("Tone")[1].split("\n\n")[0]
                self.tone_guidelines = [
                    line.strip().lstrip("-").strip()
                    for line in tone_section.split("\n")
                    if line.strip() and not line.strip().startswith("|")
                ]

            self._set_default_guidelines()
            self.logger.info(f"Loaded {len(self.tone_guidelines)} tone guidelines")
            return True

        except Exception as e:
            self.logger.error(f"Error loading handbook: {e}")
            self._set_default_guidelines()
            return True

    def _set_default_guidelines(self) -> None:
        """Set default tone guidelines."""
        self.tone_guidelines = [
            "Be professional and courteous",
            "Avoid overly salesy language",
            "Focus on value and benefits",
            "Use clear, concise language",
            "Maintain positive tone",
        ]

    def get_polite_phrasing(self) -> dict[str, str]:
        """Get recommended polite phrasings."""
        return {
            "opening": [
                "Excited to share",
                "Happy to announce",
                "Pleased to offer",
                "Delighted to present",
            ],
            "call_to_action": [
                "DM for more details",
                "Feel free to reach out",
                "Let's connect to discuss",
                "Happy to answer any questions",
            ],
            "closing": [
                "Looking forward to connecting!",
                "Here to help!",
                "Let's make it happen!",
            ],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Lead Scanner
# ─────────────────────────────────────────────────────────────────────────────


class LeadScanner:
    """Scans Needs_Action for sales/business leads."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def scan_for_leads(self) -> list[LeadInfo]:
        """Scan Needs_Action folder for lead messages."""
        leads = []

        try:
            md_files = list(NEEDS_ACTION_DIR.glob("*.md"))
            self.logger.info(f"Scanning {len(md_files)} files in Needs_Action")

            for file_path in md_files:
                lead = self._analyze_file(file_path)
                if lead:
                    leads.append(lead)

            self.logger.info(f"Found {len(leads)} potential leads")
            return leads

        except Exception as e:
            self.logger.exception(f"Error scanning for leads: {e}")
            return []

    def _analyze_file(self, file_path: Path) -> Optional[LeadInfo]:
        """Analyze a file for lead indicators."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            content_lower = content.lower()

            # Find keywords
            keywords_found = [k for k in KEYWORDS if k in content_lower]

            if not keywords_found:
                return None

            # Extract service and benefit hints
            service_hint = self._extract_service_hint(content)
            benefit_hint = self._extract_benefit_hint(content)

            # Determine priority
            priority = "P1" if "urgent" in content_lower else "P2"

            return LeadInfo(
                file_path=file_path,
                content=content,
                keywords_found=keywords_found,
                service_hint=service_hint,
                benefit_hint=benefit_hint,
                priority=priority,
            )

        except Exception as e:
            self.logger.error(f"Error analyzing file {file_path}: {e}")
            return None

    def _extract_service_hint(self, content: str) -> str:
        """Extract potential service from content."""
        # Look for common service patterns
        service_patterns = [
            r"(?:offer|provide|service|solution)[s]?\s+(?:for|in)\s+(\w+(?:\s+\w+)*)",
            r"(?:looking for|need|require)\s+(\w+(?:\s+\w+)*)",
            r"(?:expertise|specialist|expert)\s+(?:in|at)\s+(\w+(?:\s+\w+)*)",
        ]

        for pattern in service_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:50]

        return "our services"

    def _extract_benefit_hint(self, content: str) -> str:
        """Extract potential benefit from content."""
        # Look for benefit patterns
        benefit_patterns = [
            r"(?:help|assist|support)\s+(?:with|in)\s+(\w+(?:\s+\w+)*)",
            r"(?:goal|objective|target)\s+(?:is|to)\s+(\w+(?:\s+\w+)*)",
            r"(?:achieve|gain|get)\s+(\w+(?:\s+\w+)*)",
        ]

        for pattern in benefit_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:50]

        return "your business growth"


# ─────────────────────────────────────────────────────────────────────────────
# Post Drafter
# ─────────────────────────────────────────────────────────────────────────────


class PostDrafter:
    """Drafts LinkedIn posts from lead information."""

    def __init__(self, logger: logging.Logger, handbook: HandbookReader) -> None:
        self.logger = logger
        self.handbook = handbook

    def draft_post(self, lead: LeadInfo) -> LinkedInPost:
        """Draft a LinkedIn post from lead info."""
        self.logger.info(f"Drafting post for lead: {lead.file_path.name}")

        # Get polite phrasing options
        phrasing = self.handbook.get_polite_phrasing()

        # Generate post content
        service = lead.service_hint if lead.service_hint else "our services"
        benefit = lead.benefit_hint if lead.benefit_hint else "your success"

        # Create engaging post
        opening = phrasing["opening"][0]  # Could rotate based on hash
        cta = phrasing["call_to_action"][0]
        closing = phrasing["closing"][0]

        post_content = (
            f"{opening} {service} designed to help with {benefit}!\n\n"
            f"Whether you're looking for expert guidance or a reliable partner, "
            f"we're here to support your goals.\n\n"
            f"{cta}\n\n"
            f"{closing}\n\n"
            f"#{lead.keywords_found[0].title() if lead.keywords_found else 'Business'} "
            f"#ProfessionalServices #LetsConnect"
        )

        post = LinkedInPost(
            content=post_content,
            service=service,
            benefit=benefit,
            source_lead=lead.file_path.name,
            timestamp=datetime.now(),
            status="draft",
        )

        self.logger.info(f"Post drafted: {len(post_content)} characters")
        return post


# ─────────────────────────────────────────────────────────────────────────────
# File Manager
# ─────────────────────────────────────────────────────────────────────────────


class SkillFileManager:
    """Handles file operations for the skill."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

        # Ensure directories exist
        for directory in [PLANS_DIR, PENDING_APPROVAL_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

    def save_post_draft(self, post: LinkedInPost, lead: LeadInfo) -> Optional[Path]:
        """Save post draft to Plans folder."""
        try:
            timestamp = post.timestamp.strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"linkedin_post_{timestamp}.md"
            filepath = PLANS_DIR / filename

            content = self._generate_post_file_content(post, lead)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            self.logger.info(f"Saved draft to: {filepath}")
            return filepath

        except Exception as e:
            self.logger.exception(f"Error saving draft: {e}")
            return None

    def move_to_pending_approval(
        self, draft_path: Path, lead: LeadInfo
    ) -> Optional[Path]:
        """Move draft to Pending_Approval for HITL review."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"APPROVAL_REQUIRED_linkedin_post_{timestamp}.md"
            dest_path = PENDING_APPROVAL_DIR / filename

            shutil.copy2(str(draft_path), str(dest_path))

            # Append approval request to the file
            self._append_approval_request(dest_path, lead)

            self.logger.info(f"Moved to pending approval: {dest_path}")
            return dest_path

        except Exception as e:
            self.logger.exception(f"Error moving to pending: {e}")
            return None

    def _generate_post_file_content(
        self, post: LinkedInPost, lead: LeadInfo
    ) -> str:
        """Generate markdown content for post file."""
        timestamp_str = post.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        keywords_str = ", ".join(lead.keywords_found)

        return f"""---
type: linkedin_post_draft
status: {post.status}
created: {timestamp_str}
source_lead: {post.source_lead}
service: {post.service}
benefit: {post.benefit}
keywords: {keywords_str}
priority: {lead.priority}
requires_approval: true
---

# 📝 LinkedIn Post Draft

**Generated:** {timestamp_str}
**Source Lead:** {post.source_lead}
**Status:** 🟡 Draft - Pending Approval

---

## Post Content

```
{post.content}
```

---

## Lead Context

| Field | Value |
|-------|-------|
| **Keywords Found** | {keywords_str} |
| **Service Identified** | {post.service} |
| **Benefit Identified** | {post.benefit} |
| **Priority** | {lead.priority} |

---

## Approval Checklist

- [ ] Post content reviewed for accuracy
- [ ] Tone matches company guidelines
- [ ] Service/benefit alignment verified
- [ ] Ready for publication

---

## Actions

1. Review the draft above
2. Edit if necessary
3. Move to /Approved when ready to post
4. Or move to /Rejected with feedback

---

*Generated by Auto LinkedIn Poster Skill • {timestamp_str}*
"""

    def _append_approval_request(self, filepath: Path, lead: LeadInfo) -> None:
        """Append approval request section to file."""
        approval_section = f"""

---

## 🎯 HITL Approval Required

**This post requires human review before publication.**

### Why Approval is Needed
- Automated content generation may miss context
- Brand voice should be verified by human
- Compliance and accuracy check required

### Review Instructions
1. Read the post content carefully
2. Verify service and benefit claims are accurate
3. Check tone matches Company Handbook guidelines
4. Edit if needed
5. Move to `/Approved` when ready, or `/Rejected` with feedback

### Source Lead Keywords
Found keywords: {', '.join(lead.keywords_found)}

---
"""
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(approval_section)


# ─────────────────────────────────────────────────────────────────────────────
# Auto LinkedIn Poster (Main Class)
# ─────────────────────────────────────────────────────────────────────────────


class AutoLinkedInPoster:
    """Main Auto LinkedIn Poster skill class."""

    def __init__(self) -> None:
        self.logger = setup_logging()
        self.handbook = HandbookReader(self.logger)
        self.scanner = LeadScanner(self.logger)
        self.drafter: Optional[PostDrafter] = None
        self.file_manager: Optional[SkillFileManager] = None
        self.results: dict = {
            "leads_found": 0,
            "posts_drafted": 0,
            "moved_to_approval": 0,
            "files_created": [],
        }

    def run(self) -> dict:
        """Execute the Auto LinkedIn Poster skill."""
        self.logger.info("=" * 60)
        self.logger.info("AUTO LINKEDIN POSTER - STARTING")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  💼 AUTO LINKEDIN POSTER")
        print(f"  Scanning for sales/business leads...")
        print(f"{'=' * 60}\n")

        try:
            # Load handbook guidelines
            self.handbook.load_guidelines()

            # Initialize components
            self.drafter = PostDrafter(self.logger, self.handbook)
            self.file_manager = SkillFileManager(self.logger)

            # Scan for leads
            leads = self.scanner.scan_for_leads()
            self.results["leads_found"] = len(leads)

            if not leads:
                print("📭 No sales/business leads found in Needs_Action\n")
                self.logger.info("No leads found")
                return self.results

            # Process each lead
            for lead in leads:
                self._process_lead(lead)

            # Print summary
            self._print_summary()

            return self.results

        except Exception as e:
            self.logger.exception(f"Skill execution failed: {e}")
            print(f"\n❌ Skill execution failed: {e}\n")
            return self.results

    def _process_lead(self, lead: LeadInfo) -> None:
        """Process a single lead."""
        self.logger.info(f"Processing lead: {lead.file_path.name}")

        # Draft post
        post = self.drafter.draft_post(lead)
        self.results["posts_drafted"] += 1

        # Save draft to Plans
        draft_path = self.file_manager.save_post_draft(post, lead)
        if draft_path:
            self.results["files_created"].append(str(draft_path))

            # Move to Pending_Approval for HITL
            approval_path = self.file_manager.move_to_pending_approval(draft_path, lead)
            if approval_path:
                self.results["moved_to_approval"] += 1
                print(f"✅ Post drafted & moved for approval:")
                print(f"   📄 {approval_path}\n")

    def _print_summary(self) -> None:
        """Print execution summary."""
        print(f"\n{'=' * 60}")
        print("  ✅ AUTO LINKEDIN POSTER - COMPLETE")
        print(f"{'=' * 60}")
        print(f"  Leads Found:        {self.results['leads_found']}")
        print(f"  Posts Drafted:      {self.results['posts_drafted']}")
        print(f"  Moved to Approval:  {self.results['moved_to_approval']}")
        print(f"{'=' * 60}\n")

        if self.results["files_created"]:
            print("  📁 Files Created:")
            for filepath in self.results["files_created"]:
                print(f"     - {filepath}")
            print()


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Main entry point."""
    skill = AutoLinkedInPoster()
    skill.run()


if __name__ == "__main__":
    main()
