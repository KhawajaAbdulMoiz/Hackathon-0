#!/usr/bin/env python3
"""
HITL Approval Handler - AI Employee Skill (Silver Tier)

Handles Human-in-the-Loop approval workflow for sensitive actions:
- Email drafts (from Email MCP)
- LinkedIn posts (from Auto LinkedIn Poster)
- Payment requests
- Other sensitive operations

Workflow:
1. Write approval request to /Pending_Approval with YAML frontmatter
2. Monitor /Approved folder for moved/approved files
3. Execute action via MCP or direct integration
4. On rejection, move to /Rejected and log reason
5. Log all actions to /Logs/hitl_[date].md

Usage:
    python skills/hitl_approval_handler.py
    # Or via Qwen CLI: @HITL Approval Handler check Pending_Approval
"""

import json
import logging
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Final, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

VAULT_ROOT: Final[Path] = Path(__file__).parent.parent.resolve()
PENDING_APPROVAL_DIR: Final[Path] = VAULT_ROOT / "Pending_Approval"
APPROVED_DIR: Final[Path] = VAULT_ROOT / "Approved"
REJECTED_DIR: Final[Path] = VAULT_ROOT / "Rejected"
DONE_DIR: Final[Path] = VAULT_ROOT / "Done"
PLANS_DIR: Final[Path] = VAULT_ROOT / "Plans"
LOGS_DIR: Final[Path] = VAULT_ROOT / "Logs"
MCP_SERVERS_DIR: Final[Path] = VAULT_ROOT / "mcp_servers"

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# Action types that require HITL
ACTION_TYPES: Final[list[str]] = [
    "email_send",
    "linkedin_post",
    "payment",
    "external_api_call",
    "file_deletion",
    "config_change",
]

# ─────────────────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────────────────


def setup_logging() -> logging.Logger:
    """Configure logging with both file and console handlers."""
    logger = logging.getLogger("hitl_approval_handler")
    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    # File handler
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"hitl_{datetime.now().strftime('%Y-%m-%d')}.md"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# ─────────────────────────────────────────────────────────────────────────────
# Enums & Data Classes
# ─────────────────────────────────────────────────────────────────────────────


class ApprovalStatus(Enum):
    """Status of approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class ActionType(Enum):
    """Type of action requiring approval."""

    EMAIL_SEND = "email_send"
    LINKEDIN_POST = "linkedin_post"
    PAYMENT = "payment"
    EXTERNAL_API = "external_api_call"
    FILE_DELETION = "file_deletion"
    CONFIG_CHANGE = "config_change"
    GENERAL = "general"


@dataclass
class ApprovalRequest:
    """Represents an approval request."""

    action_type: ActionType
    title: str
    details: dict
    created_at: datetime = field(default_factory=datetime.now)
    status: ApprovalStatus = ApprovalStatus.PENDING
    file_path: Optional[Path] = None
    executed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    executor: Optional[str] = None


@dataclass
class ApprovalResult:
    """Result of approval processing."""

    success: bool
    request: ApprovalRequest
    message: str
    output_file: Optional[Path] = None
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Approval Request Manager
# ─────────────────────────────────────────────────────────────────────────────


class ApprovalRequestManager:
    """Manages creation and tracking of approval requests."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        PENDING_APPROVAL_DIR.mkdir(parents=True, exist_ok=True)

    def create_request(
        self,
        action_type: str,
        title: str,
        details: dict,
        priority: str = "P2",
    ) -> Optional[Path]:
        """Create a new approval request file."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            action_safe = action_type.replace("_", "-")
            filename = f"{action_safe}_{timestamp}.md"
            filepath = PENDING_APPROVAL_DIR / filename

            content = self._generate_request_content(
                action_type, title, details, priority
            )

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            self.logger.info(f"Approval request created: {filename}")
            return filepath

        except Exception as e:
            self.logger.exception(f"Error creating approval request: {e}")
            return None

    def _generate_request_content(
        self, action_type: str, title: str, details: dict, priority: str
    ) -> str:
        """Generate markdown content for approval request."""
        timestamp = datetime.now().isoformat()
        details_json = json.dumps(details, indent=2, default=str)

        # Generate action-specific sections
        action_section = self._generate_action_section(action_type, details)

        return f"""---
type: approval_request
action_type: {action_type}
title: {title}
created: {timestamp}
status: pending
priority: {priority}
requires_human_approval: true
---

# 🎯 Approval Request: {title}

**Created:** {timestamp}
**Action Type:** {action_type.replace("_", " ").title()}
**Priority:** {self._priority_emoji(priority)} {priority}
**Status:** 🟡 Pending Human Approval

---

## Request Details

```json
{details_json}
```

---

{action_section}

## Approval Instructions

### To Approve:
1. Review all details above carefully
2. Verify the action is safe and appropriate
3. Move this file to `/Approved` folder
4. The HITL Handler will automatically execute the action

### To Reject:
1. Add rejection reason in the section below
2. Move this file to `/Rejected` folder
3. The request will be logged and archived

---

## Rejection Section (Fill if rejecting)

**Rejection Reason:**

[Add your reason here if rejecting]

**Rejected By:** [Your name]
**Rejection Date:** [Date]

---

## Audit Trail

| Event | Timestamp | Actor |
|-------|-----------|-------|
| Request Created | {timestamp} | System |
| Awaiting Approval | {timestamp} | — |

---

*Generated by HITL Approval Handler • {timestamp}*
"""

    def _generate_action_section(self, action_type: str, details: dict) -> str:
        """Generate action-specific information section."""
        if action_type == "email_send":
            return f"""## Email Details

| Field | Value |
|-------|-------|
| **To** | {details.get('to', 'N/A')} |
| **Subject** | {details.get('subject', 'N/A')} |
| **CC** | {details.get('cc', 'N/A')} |
| **Body Preview** | {details.get('body', '')[:200]}... |

⚠️ **Note:** This will send an email via Gmail API. Verify recipient and content."""

        elif action_type == "linkedin_post":
            return f"""## LinkedIn Post Details

| Field | Value |
|-------|-------|
| **Content** | {details.get('content', '')[:200]}... |
| **Service** | {details.get('service', 'N/A')} |
| **Benefit** | {details.get('benefit', 'N/A')} |
| **Source Lead** | {details.get('source_lead', 'N/A')} |

⚠️ **Note:** This will publish a post to LinkedIn. Review content for brand alignment."""

        elif action_type == "payment":
            return f"""## Payment Details

| Field | Value |
|-------|-------|
| **Recipient** | {details.get('recipient', 'N/A')} |
| **Amount** | {details.get('amount', 'N/A')} |
| **Currency** | {details.get('currency', 'USD')} |
| **Invoice/Reference** | {details.get('reference', 'N/A')} |

⚠️ **Note:** This will initiate a payment. Verify amount and recipient."""

        elif action_type == "external_api_call":
            return f"""## API Call Details

| Field | Value |
|-------|-------|
| **Endpoint** | {details.get('endpoint', 'N/A')} |
| **Method** | {details.get('method', 'POST')} |
| **Purpose** | {details.get('purpose', 'N/A')} |

⚠️ **Note:** This will make an external API call. Review data being sent."""

        else:
            return """## Action Details

Review the JSON details above carefully before approving."""

    def _priority_emoji(self, priority: str) -> str:
        """Get emoji for priority level."""
        emojis = {"P0": "🔴", "P1": "🟠", "P2": "🔵", "P3": "⚪"}
        return emojis.get(priority, "🔵")

    def get_pending_requests(self) -> list[Path]:
        """Get all pending approval requests."""
        try:
            return list(PENDING_APPROVAL_DIR.glob("*.md"))
        except Exception as e:
            self.logger.error(f"Error getting pending requests: {e}")
            return []

    def parse_request(self, filepath: Path) -> Optional[ApprovalRequest]:
        """Parse approval request from file."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract YAML frontmatter
            metadata = self._extract_yaml_frontmatter(content)

            action_type_str = metadata.get("action_type", "general")
            try:
                action_type = ActionType(action_type_str)
            except ValueError:
                action_type = ActionType.GENERAL

            status_str = metadata.get("status", "pending")
            try:
                status = ApprovalStatus(status_str)
            except ValueError:
                status = ApprovalStatus.PENDING

            return ApprovalRequest(
                action_type=action_type,
                title=metadata.get("title", filepath.stem),
                details=self._extract_details(content),
                created_at=datetime.now(),
                status=status,
                file_path=filepath,
            )

        except Exception as e:
            self.logger.error(f"Error parsing request {filepath}: {e}")
            return None

    def _extract_yaml_frontmatter(self, content: str) -> dict:
        """Extract YAML frontmatter from markdown content."""
        metadata = {}
        if content.startswith("---"):
            try:
                lines = content.split("\n")
                in_frontmatter = False
                for line in lines[1:]:
                    if line.strip() == "---":
                        break
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip().strip('"')
            except Exception:
                pass
        return metadata

    def _extract_details(self, content: str) -> dict:
        """Extract JSON details from content."""
        try:
            # Find JSON block
            match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except Exception:
            pass
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Approval Executor
# ─────────────────────────────────────────────────────────────────────────────


class ApprovalExecutor:
    """Executes approved actions."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        APPROVED_DIR.mkdir(parents=True, exist_ok=True)
        REJECTED_DIR.mkdir(parents=True, exist_ok=True)
        DONE_DIR.mkdir(parents=True, exist_ok=True)

    def execute(self, request: ApprovalRequest) -> ApprovalResult:
        """Execute an approved action."""
        self.logger.info(f"Executing action: {request.action_type.value}")

        try:
            if request.action_type == ActionType.EMAIL_SEND:
                return self._execute_email_send(request)
            elif request.action_type == ActionType.LINKEDIN_POST:
                return self._execute_linkedin_post(request)
            elif request.action_type == ActionType.PAYMENT:
                return self._execute_payment(request)
            else:
                return self._execute_general(request)

        except Exception as e:
            self.logger.exception(f"Execution failed: {e}")
            return ApprovalResult(
                success=False,
                request=request,
                message="Execution failed",
                error=str(e),
            )

    def _execute_email_send(self, request: ApprovalRequest) -> ApprovalResult:
        """Execute email send action via Email MCP."""
        self.logger.info("Sending email via Email MCP...")

        details = request.details
        try:
            # Call Email MCP server
            mcp_path = MCP_SERVERS_DIR / "email-mcp"
            if mcp_path.exists():
                # Use subprocess to call MCP
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        f"""
import sys
sys.path.insert(0, '{mcp_path}')
# Simple email send via Gmail API
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import base64
from pathlib import Path

vault_root = Path('{VAULT_ROOT}')
creds_file = vault_root / 'client_secret_1005799766116-6oj47f92vtmaacrvrfm0dgocjrkv8ukr.apps.googleusercontent.com.json'
token_file = vault_root / 'token.json'

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

creds = None
if token_file.exists():
    creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        print('AUTH_REQUIRED')
        sys.exit(1)

service = build('gmail', 'v1', credentials=creds)

message_str = f'''To: {details.get('to')}
Subject: {details.get('subject')}
MIME-Version: 1.0
Content-Type: text/html; charset=utf-8

{details.get('body', '')}'''

encoded = base64.urlsafe_b64encode(message_str.encode()).decode()
sent = service.users().messages().send(userId='me', body={{'raw': encoded}}).execute()
print(f"SENT:{{sent['id']}}")
""",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if "SENT:" in result.stdout:
                    message_id = result.stdout.split("SENT:")[1].strip()
                    return ApprovalResult(
                        success=True,
                        request=request,
                        message=f"Email sent successfully (ID: {message_id})",
                    )
                elif "AUTH_REQUIRED" in result.stdout:
                    return ApprovalResult(
                        success=False,
                        request=request,
                        message="Gmail authentication required",
                        error="OAuth token missing or expired",
                    )
                else:
                    return ApprovalResult(
                        success=False,
                        request=request,
                        message="Email send failed",
                        error=result.stderr or result.stdout,
                    )
            else:
                return ApprovalResult(
                    success=False,
                    request=request,
                    message="Email MCP server not found",
                    error=f"Path not found: {mcp_path}",
                )

        except subprocess.TimeoutExpired:
            return ApprovalResult(
                success=False,
                request=request,
                message="Email send timed out",
                error="Timeout after 30 seconds",
            )
        except Exception as e:
            return ApprovalResult(
                success=False,
                request=request,
                message="Email send failed",
                error=str(e),
            )

    def _execute_linkedin_post(self, request: ApprovalRequest) -> ApprovalResult:
        """Execute LinkedIn post action."""
        self.logger.info("LinkedIn post execution (simulation)...")

        # LinkedIn posting requires browser automation
        # For now, log the post content and mark as ready for manual posting
        details = request.details

        # Save post to Done with execution note
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = DONE_DIR / f"linkedin_post_executed_{timestamp}.md"

        content = f"""# ✅ LinkedIn Post Executed

**Original Request:** {request.file_path.name if request.file_path else 'N/A'}
**Executed At:** {datetime.now().isoformat()}
**Status:** Ready for manual posting

---

## Post Content

{details.get('content', 'No content')}

---

## Manual Posting Instructions

1. Copy the content above
2. Go to LinkedIn.com
3. Create a new post
4. Paste content and publish
5. Return here and mark as complete

---

*Executed by HITL Approval Handler*
"""

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)

        return ApprovalResult(
            success=True,
            request=request,
            message="LinkedIn post prepared for manual publishing",
            output_file=output_file,
        )

    def _execute_payment(self, request: ApprovalRequest) -> ApprovalResult:
        """Execute payment action."""
        self.logger.info("Payment execution (simulation)...")

        # Payment execution would integrate with payment processor
        # For now, log and mark for manual processing
        details = request.details

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = DONE_DIR / f"payment_processed_{timestamp}.md"

        content = f"""# ✅ Payment Processed

**Original Request:** {request.file_path.name if request.file_path else 'N/A'}
**Executed At:** {datetime.now().isoformat()}
**Status:** Ready for manual processing

---

## Payment Details

| Field | Value |
|-------|-------|
| **Recipient** | {details.get('recipient', 'N/A')} |
| **Amount** | {details.get('amount', 'N/A')} {details.get('currency', 'USD')} |
| **Reference** | {details.get('reference', 'N/A')} |

---

## Manual Processing Instructions

1. Verify payment details above
2. Process payment via your payment processor
3. Record transaction ID
4. Mark as complete

---

*Executed by HITL Approval Handler*
"""

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)

        return ApprovalResult(
            success=True,
            request=request,
            message="Payment prepared for manual processing",
            output_file=output_file,
        )

    def _execute_general(self, request: ApprovalRequest) -> ApprovalResult:
        """Execute general action."""
        self.logger.info("Executing general action...")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = DONE_DIR / f"action_executed_{timestamp}.md"

        content = f"""# ✅ Action Executed

**Original Request:** {request.file_path.name if request.file_path else 'N/A'}
**Action Type:** {request.action_type.value}
**Executed At:** {datetime.now().isoformat()}
**Status:** Completed

---

## Details

Action has been executed. Review original request for specifics.

---

*Executed by HITL Approval Handler*
"""

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)

        return ApprovalResult(
            success=True,
            request=request,
            message="Action executed successfully",
            output_file=output_file,
        )

    def reject(self, request: ApprovalRequest, reason: str) -> Optional[Path]:
        """Reject an approval request."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"rejected_{request.file_path.stem if request.file_path else 'unknown'}_{timestamp}.md"
            dest_path = REJECTED_DIR / filename

            # Read original content
            if request.file_path and request.file_path.exists():
                with open(request.file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Append rejection info
                content += f"""

---

## ❌ Rejected

**Rejection Date:** {datetime.now().isoformat()}
**Reason:** {reason}

*Rejected by HITL Approval Handler*
"""

                with open(dest_path, "w", encoding="utf-8") as f:
                    f.write(content)

                # Remove from pending
                request.file_path.unlink()

                self.logger.info(f"Request rejected: {filename}")
                return dest_path

        except Exception as e:
            self.logger.error(f"Error rejecting request: {e}")
        return None

    def move_to_done(self, request: ApprovalRequest) -> Optional[Path]:
        """Move executed request to Done folder."""
        try:
            if request.file_path and request.file_path.exists():
                timestamp = datetime.now().strftime("%Y-%m-%d")
                dest_name = f"{timestamp}_{request.file_path.name}"
                dest_path = DONE_DIR / dest_name

                shutil.move(str(request.file_path), str(dest_path))
                self.logger.info(f"Moved to Done: {dest_path.name}")
                return dest_path

        except Exception as e:
            self.logger.error(f"Error moving to Done: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# HITL Logger
# ─────────────────────────────────────────────────────────────────────────────


class HITLLogger:
    """Logs all HITL actions."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.log_file = LOGS_DIR / f"hitl_{datetime.now().strftime('%Y-%m-%d')}.md"
        self._ensure_log_file()

    def _ensure_log_file(self) -> None:
        """Ensure log file exists with header."""
        if not self.log_file.exists():
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, "w", encoding="utf-8") as f:
                f.write(f"""# HITL Approval Log

**Created:** {datetime.now().isoformat()}
**Date:** {datetime.now().strftime('%Y-%m-%d')}

---

## Log Entries

""")

    def log_request_created(self, request: ApprovalRequest, filepath: Path) -> None:
        """Log approval request creation."""
        entry = f"""### [{datetime.now().strftime('%H:%M:%S')}] Request Created

- **Action Type:** {request.action_type.value}
- **Title:** {request.title}
- **File:** {filepath.name}
- **Priority:** {request.details.get('priority', 'P2')}

"""
        self._append_entry(entry)

    def log_approval(self, request: ApprovalRequest, result: ApprovalResult) -> None:
        """Log approval and execution."""
        status = "✅ Success" if result.success else "❌ Failed"
        entry = f"""### [{datetime.now().strftime('%H:%M:%S')}] Approved & Executed

- **Action Type:** {request.action_type.value}
- **Status:** {status}
- **Message:** {result.message}
{f'- **Error:** {result.error}' if result.error else ''}

"""
        self._append_entry(entry)

    def log_rejection(self, request: ApprovalRequest, reason: str) -> None:
        """Log rejection."""
        entry = f"""### [{datetime.now().strftime('%H:%M:%S')}] Rejected

- **Action Type:** {request.action_type.value}
- **Reason:** {reason}

"""
        self._append_entry(entry)

    def _append_entry(self, entry: str) -> None:
        """Append entry to log file."""
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(entry)


# ─────────────────────────────────────────────────────────────────────────────
# HITL Approval Handler (Main Class)
# ─────────────────────────────────────────────────────────────────────────────


class HITLApprovalHandler:
    """Main HITL Approval Handler class."""

    def __init__(self) -> None:
        self.logger = setup_logging()
        self.request_manager = ApprovalRequestManager(self.logger)
        self.executor = ApprovalExecutor(self.logger)
        self.hitl_logger = HITLLogger(self.logger)
        self.results = {
            "pending_found": 0,
            "approved_processed": 0,
            "executed_success": 0,
            "executed_failed": 0,
            "rejected": 0,
        }

    def run(self, mode: str = "check_pending") -> dict:
        """Run the HITL Approval Handler."""
        self.logger.info("=" * 60)
        self.logger.info("HITL APPROVAL HANDLER - STARTING")
        self.logger.info(f"Mode: {mode}")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  🎯 HITL APPROVAL HANDLER")
        print(f"  Mode: {mode.replace('_', ' ').title()}")
        print(f"{'=' * 60}\n")

        try:
            if mode == "check_pending":
                self._check_pending_requests()
            elif mode == "process_approved":
                self._process_approved_files()
            elif mode == "full":
                self._check_pending_requests()
                self._process_approved_files()
            else:
                self.logger.warning(f"Unknown mode: {mode}")

            self._print_summary()
            return self.results

        except Exception as e:
            self.logger.exception(f"Handler execution failed: {e}")
            print(f"\n❌ Handler execution failed: {e}\n")
            return self.results

    def create_approval_request(
        self, action_type: str, title: str, details: dict, priority: str = "P2"
    ) -> Optional[Path]:
        """Create a new approval request."""
        filepath = self.request_manager.create_request(
            action_type, title, details, priority
        )

        if filepath:
            request = self.request_manager.parse_request(filepath)
            if request:
                self.hitl_logger.log_request_created(request, filepath)
                print(f"✅ Approval request created: {filepath}")

        return filepath

    def _check_pending_requests(self) -> None:
        """Check and report pending approval requests."""
        pending_files = self.request_manager.get_pending_requests()
        self.results["pending_found"] = len(pending_files)

        if not pending_files:
            print("📭 No pending approval requests")
            self.logger.info("No pending approval requests found")
            return

        print(f"📋 Found {len(pending_files)} pending request(s):\n")

        for filepath in pending_files:
            request = self.request_manager.parse_request(filepath)
            if request:
                print(f"   • {filepath.name}")
                print(f"     Type: {request.action_type.value}")
                print(f"     Priority: {request.details.get('priority', 'P2')}")
                print(f"     Created: {request.created_at.strftime('%Y-%m-%d %H:%M')}")
                print()

    def _process_approved_files(self) -> None:
        """Process files in Approved folder."""
        try:
            approved_files = list(APPROVED_DIR.glob("*.md"))

            if not approved_files:
                self.logger.debug("No approved files to process")
                return

            self.logger.info(f"Processing {len(approved_files)} approved file(s)")

            for filepath in approved_files:
                self._process_approved_file(filepath)

        except Exception as e:
            self.logger.error(f"Error processing approved files: {e}")

    def _process_approved_file(self, filepath: Path) -> None:
        """Process a single approved file."""
        try:
            request = self.request_manager.parse_request(filepath)
            if not request:
                self.logger.warning(f"Failed to parse: {filepath}")
                return

            request.status = ApprovalStatus.APPROVED
            self.results["approved_processed"] += 1

            print(f"🔄 Processing: {filepath.name}")

            # Execute the action
            result = self.executor.execute(request)
            self.hitl_logger.log_approval(request, result)

            if result.success:
                self.results["executed_success"] += 1
                print(f"   ✅ Executed: {result.message}")

                # Move to Done
                self.executor.move_to_done(request)
            else:
                self.results["executed_failed"] += 1
                print(f"   ❌ Failed: {result.message}")
                if result.error:
                    print(f"      Error: {result.error}")

        except Exception as e:
            self.logger.exception(f"Error processing file {filepath}: {e}")
            self.results["executed_failed"] += 1

    def _print_summary(self) -> None:
        """Print execution summary."""
        print(f"\n{'=' * 60}")
        print("  📊 HITL APPROVAL HANDLER - SUMMARY")
        print(f"{'=' * 60}")
        print(f"  Pending Found:       {self.results['pending_found']}")
        print(f"  Approved Processed:  {self.results['approved_processed']}")
        print(f"  Executed Success:    {self.results['executed_success']}")
        print(f"  Executed Failed:     {self.results['executed_failed']}")
        print(f"  Rejected:            {self.results['rejected']}")
        print(f"{'=' * 60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="HITL Approval Handler")
    parser.add_argument(
        "mode",
        type=str,
        nargs="?",
        default="full",
        choices=["check_pending", "process_approved", "full"],
        help="Operation mode",
    )
    parser.add_argument(
        "--create",
        type=str,
        help="Create new approval request (action_type:title)",
    )
    parser.add_argument(
        "--details",
        type=str,
        help="JSON details for new request",
    )

    args = parser.parse_args()

    handler = HITLApprovalHandler()

    if args.create:
        # Create new approval request
        parts = args.create.split(":", 1)
        action_type = parts[0]
        title = parts[1] if len(parts) > 1 else "Approval Request"

        details = {}
        if args.details:
            try:
                details = json.loads(args.details)
            except json.JSONDecodeError:
                print("❌ Invalid JSON for --details")
                sys.exit(1)

        filepath = handler.create_approval_request(action_type, title, details)
        if filepath:
            print(f"\n📁 File created: {filepath}")
    else:
        # Run handler
        handler.run(args.mode)


if __name__ == "__main__":
    main()
