#!/usr/bin/env python3
"""
Twitter Post Generator - AI Employee Skill (Gold Tier)

Processes Twitter (X) content from Needs_Action folder:
- Generates detailed post/message summaries
- Drafts tweet responses for sales leads
- Saves drafts to /Plans/twitter_draft_[date].md
- Requires HITL approval before posting/sending

Usage:
    python skills/twitter_post_generator.py
    # Or via Qwen CLI: @Twitter_Post_Generator_process_Twitter

Keywords: twitter, tweet, response, social
"""

import json
import logging
import os
import re
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
NEEDS_ACTION_DIR: Final[Path] = VAULT_ROOT / "Needs_Action"
PLANS_DIR: Final[Path] = VAULT_ROOT / "Plans"
PENDING_APPROVAL_DIR: Final[Path] = VAULT_ROOT / "Pending_Approval"
LOGS_DIR: Final[Path] = VAULT_ROOT / "Logs"

# Twitter-specific response templates (280 character limit aware)
RESPONSE_TEMPLATES: Final[dict[str, str]] = {
    "sales": """Hi {sender}! 👋 Thanks for your interest in our sales services!

We'd love to help with {topic}. Our team delivers tailored solutions for businesses like yours.

Could you share more about:
• Your requirements
• Timeline
• Budget range

Let's connect! 🚀

#BusinessGrowth #Sales""",

    "client": """Hello {sender}! 👋

Thanks for reaching out about {topic}! We're here to help.

To better assist you:
• What challenges are you facing?
• What's your ideal outcome?
• Any deadlines?

We're committed to excellence! 💼

#ClientSuccess #Support""",

    "project": """Hi {sender}! 👋

Excited about your {topic} project! Here's how we can help:

1️⃣ Initial consultation
2️⃣ Custom solution design
3️⃣ Implementation
4️⃣ Post-delivery support

Available for a call this week? 📞

#ProjectManagement #Collaboration""",

    "general": """Hello {sender}! 👋

Thanks for your message about {topic}!

We've received your inquiry and will get back to you shortly. 📬

For urgent matters, feel free to DM us!

#CustomerService #HereToHelp""",

    "tweet_reply": """@{sender} Great point about {topic}! 💡

We'd love to contribute to this conversation. Our team specializes in delivering solutions that make a difference.

Let's connect! 🤝

#Engagement #Community""",
}

# Default values
DEFAULT_COMPANY: Final[str] = "Our Team"
DEFAULT_SENDER: Final[str] = "Valued Contact"
DEFAULT_HANDLE: Final[str] = "@user"

# Tweet character limit
MAX_TWEET_LENGTH: Final[int] = 280

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# ─────────────────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────────────────


def setup_logging() -> logging.Logger:
    """Configure logging with both file and console handlers."""
    logger = logging.getLogger("twitter_post_generator")
    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    # File handler
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"twitter_post_gen_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# ─────────────────────────────────────────────────────────────────────────────
# Enums & Data Classes
# ─────────────────────────────────────────────────────────────────────────────


class LeadType(Enum):
    """Type of Twitter lead."""

    SALES = "sales"
    CLIENT = "client"
    PROJECT = "project"
    GENERAL = "general"
    TWEET_REPLY = "tweet_reply"


@dataclass
class TwitterMessage:
    """Represents a Twitter message to process."""

    file_path: Path
    content_type: str
    sender: str
    sender_handle: str
    content: str
    keywords: list[str]
    priority: str
    received: datetime
    url: str


@dataclass
class MessageSummary:
    """Generated summary of a Twitter message."""

    message: TwitterMessage
    summary_text: str
    sentiment: str
    lead_type: LeadType
    action_items: list[str]
    suggested_tweet: str
    suggested_dm: str
    confidence: float


@dataclass
class ProcessingResult:
    """Result of processing a message."""

    message: TwitterMessage
    summary: MessageSummary
    draft_path: Optional[Path]
    success: bool
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Message Parser
# ─────────────────────────────────────────────────────────────────────────────


class MessageParser:
    """Parses Twitter message files."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def parse_message(self, file_path: Path) -> Optional[TwitterMessage]:
        """Parse a Twitter message file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract YAML frontmatter
            metadata = self._extract_frontmatter(content)

            # Check if it's a Twitter message
            msg_type = metadata.get("type", "")
            platform = metadata.get("platform", "")
            if msg_type != "twitter_content" or platform != "twitter":
                self.logger.debug(f"Skipping non-Twitter file: {file_path.name}")
                return None

            # Extract body content
            body = self._extract_body(content)

            return TwitterMessage(
                file_path=file_path,
                content_type=metadata.get("content_type", "unknown"),
                sender=metadata.get("sender", DEFAULT_SENDER),
                sender_handle=metadata.get("sender_handle", DEFAULT_HANDLE),
                content=body,
                keywords=self._parse_keywords(metadata.get("keywords", "")),
                priority=metadata.get("priority", "P3"),
                received=self._parse_datetime(metadata.get("received", "")),
                url=metadata.get("url", ""),
            )

        except Exception as e:
            self.logger.error(f"Error parsing {file_path.name}: {e}")
            return None

    def _extract_frontmatter(self, content: str) -> dict:
        """Extract YAML frontmatter from markdown."""
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
                        metadata[key.strip()] = value.strip().strip('"').strip("'")
            except Exception:
                pass

        return metadata

    def _extract_body(self, content: str) -> str:
        """Extract body content from markdown."""
        # Find content section
        patterns = [
            r"## Content\s*\n(.*?)(?=\n##|\n---|$)",
            r"## Tweet\s*\n(.*?)(?=\n##|\n---|$)",
            r"## Message\s*\n(.*?)(?=\n##|\n---|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1).strip()

        # Fallback: return content after frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) > 2:
                return parts[2].strip()

        return content

    def _parse_keywords(self, keywords_str: str) -> list[str]:
        """Parse keywords string to list."""
        if not keywords_str:
            return []
        return [k.strip() for k in keywords_str.split(",")]

    def _parse_datetime(self, dt_str: str) -> datetime:
        """Parse datetime string."""
        try:
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return datetime.now()


# ─────────────────────────────────────────────────────────────────────────────
# Summary Generator
# ─────────────────────────────────────────────────────────────────────────────


class SummaryGenerator:
    """Generates summaries and responses for Twitter messages."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def generate_summary(self, message: TwitterMessage) -> MessageSummary:
        """Generate comprehensive summary for a message."""
        self.logger.info(f"Generating summary for {message.file_path.name}")

        # Generate summary text
        summary_text = self._generate_summary_text(message)

        # Analyze sentiment
        sentiment = self._analyze_sentiment(message.content)

        # Determine lead type
        lead_type = self._determine_lead_type(message.keywords, message.content_type)

        # Extract action items
        action_items = self._extract_action_items(message.content, lead_type)

        # Generate suggested tweet
        suggested_tweet = self._generate_tweet(message, lead_type)

        # Generate suggested DM for longer responses
        suggested_dm = self._generate_dm(message, lead_type)

        # Calculate confidence
        confidence = self._calculate_confidence(message, lead_type)

        return MessageSummary(
            message=message,
            summary_text=summary_text,
            sentiment=sentiment,
            lead_type=lead_type,
            action_items=action_items,
            suggested_tweet=suggested_tweet,
            suggested_dm=suggested_dm,
            confidence=confidence,
        )

    def _generate_summary_text(self, message: TwitterMessage) -> str:
        """Generate a concise summary of the message."""
        content = message.content
        keywords = message.keywords

        parts = []

        # Content type context
        parts.append(f"Received via Twitter {message.content_type.title()}")

        # Keyword context
        if "sales" in keywords:
            parts.append("potential sales opportunity")
        if "client" in keywords:
            parts.append("client inquiry")
        if "project" in keywords:
            parts.append("project-related discussion")

        # Content summary
        first_sentence = content.split(".")[0][:150]
        parts.append(f"Preview: {first_sentence}...")

        # Priority
        priority_map = {"P0": "URGENT", "P1": "High", "P2": "Normal", "P3": "Low"}
        parts.append(f"Priority: {priority_map.get(message.priority, 'Normal')}")

        return ". ".join(parts) + "."

    def _analyze_sentiment(self, content: str) -> str:
        """Analyze message sentiment."""
        content_lower = content.lower()

        positive_words = [
            "great", "excellent", "love", "happy", "excited", "interested",
            "amazing", "wonderful", "fantastic", "good", "best", "thanks"
        ]
        negative_words = [
            "issue", "problem", "complaint", "unhappy", "disappointed",
            "frustrated", "angry", "bad", "worst", "terrible"
        ]

        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        return "neutral"

    def _determine_lead_type(
        self, keywords: list[str], content_type: str
    ) -> LeadType:
        """Determine the type of lead."""
        if "sales" in keywords:
            return LeadType.SALES
        elif "client" in keywords:
            return LeadType.CLIENT
        elif "project" in keywords:
            return LeadType.PROJECT
        elif content_type == "tweet":
            return LeadType.TWEET_REPLY
        return LeadType.GENERAL

    def _extract_action_items(
        self, content: str, lead_type: LeadType
    ) -> list[str]:
        """Extract action items from message."""
        actions = []

        # Common action items based on lead type
        if lead_type == LeadType.SALES:
            actions.extend([
                "Review sales inquiry details",
                "Prepare product/service information",
                "Schedule follow-up call",
                "Craft engaging tweet response",
            ])
        elif lead_type == LeadType.CLIENT:
            actions.extend([
                "Review client requirements",
                "Assess service fit",
                "Prepare initial proposal",
                "Send welcoming DM",
            ])
        elif lead_type == LeadType.PROJECT:
            actions.extend([
                "Review project scope",
                "Estimate timeline and resources",
                "Schedule discovery meeting",
                "Share portfolio/examples",
            ])
        elif lead_type == LeadType.TWEET_REPLY:
            actions.extend([
                "Review tweet context",
                "Craft relevant public reply",
                "Consider follow-up DM",
                "Engage with original tweet",
            ])
        else:
            actions.extend([
                "Review message content",
                "Determine appropriate response",
                "Follow up as needed",
            ])

        # Check for specific requests in content
        content_lower = content.lower()
        if "call" in content_lower or "meeting" in content_lower:
            actions.append("Schedule call/meeting as requested")
        if "quote" in content_lower or "price" in content_lower:
            actions.append("Prepare pricing information")
        if "urgent" in content_lower or "asap" in content_lower:
            actions.append("Prioritize for immediate response")

        return actions

    def _generate_tweet(self, message: TwitterMessage, lead_type: LeadType) -> str:
        """Generate suggested tweet response (under 280 chars)."""
        template = RESPONSE_TEMPLATES.get(
            lead_type.value, RESPONSE_TEMPLATES["general"]
        )

        # Determine topic from content
        topic = self._extract_topic(message.content)

        # Get sender handle
        handle = message.sender_handle.lstrip("@") if message.sender_handle else "user"

        tweet = template.format(
            sender=handle,
            topic=topic,
            company=DEFAULT_COMPANY,
        )

        # Ensure under character limit
        if len(tweet) > MAX_TWEET_LENGTH:
            tweet = tweet[: MAX_TWEET_LENGTH - 3] + "..."

        return tweet

    def _generate_dm(self, message: TwitterMessage, lead_type: LeadType) -> str:
        """Generate suggested DM response (longer format)."""
        template = RESPONSE_TEMPLATES.get(
            lead_type.value, RESPONSE_TEMPLATES["general"]
        )

        topic = self._extract_topic(message.content)
        sender = message.sender.split()[0] if message.sender else DEFAULT_SENDER

        return template.format(
            sender=sender,
            topic=topic,
            company=DEFAULT_COMPANY,
        )

    def _extract_topic(self, content: str) -> str:
        """Extract main topic from content."""
        # Look for common patterns
        patterns = [
            r"(?:interested in|looking for|need)\s+(\w+(?:\s+\w+){0,3})",
            r"(?:about|regarding|re:)\s*(\w+(?:\s+\w+){0,3})",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:30]

        return "our services"

    def _calculate_confidence(
        self, message: TwitterMessage, lead_type: LeadType
    ) -> float:
        """Calculate confidence score for the analysis."""
        confidence = 0.5

        # More keywords = higher confidence
        keyword_bonus = min(len(message.keywords) * 0.1, 0.3)
        confidence += keyword_bonus

        # Sales/client/project keywords = higher confidence
        if lead_type in [LeadType.SALES, LeadType.CLIENT, LeadType.PROJECT]:
            confidence += 0.1

        # Priority bonus
        if message.priority in ["P0", "P1"]:
            confidence += 0.05

        return min(confidence, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Draft Manager
# ─────────────────────────────────────────────────────────────────────────────


class DraftManager:
    """Manages creation of tweet/response drafts."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        PLANS_DIR.mkdir(parents=True, exist_ok=True)
        PENDING_APPROVAL_DIR.mkdir(parents=True, exist_ok=True)

    def save_draft(self, summary: MessageSummary) -> Optional[Path]:
        """Save response draft to Plans folder."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            content_type = summary.message.content_type
            filename = f"twitter_draft_{content_type}_{timestamp}.md"
            filepath = PLANS_DIR / filename

            content = self._generate_draft_content(summary)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            self.logger.info(f"Draft saved: {filename}")

            # Also create HITL approval request
            approval_path = self._create_approval_request(summary, filepath)

            return approval_path or filepath

        except Exception as e:
            self.logger.exception(f"Error saving draft: {e}")
            return None

    def _generate_draft_content(self, summary: MessageSummary) -> str:
        """Generate draft content."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = summary.message

        action_items_md = "\n".join(f"- [ ] {item}" for item in summary.action_items)

        # Character count for tweet
        tweet_chars = len(summary.suggested_tweet)

        return f"""---
type: twitter_response_draft
platform: twitter
content_type: {msg.content_type}
sender: {msg.sender}
sender_handle: {msg.sender_handle}
lead_type: {summary.lead_type.value}
sentiment: {summary.sentiment}
priority: {msg.priority}
created: {timestamp}
requires_approval: true
tweet_character_count: {tweet_chars}
---

# 🐦 Twitter Response Draft

**Created:** {timestamp}
**Platform:** Twitter (X)
**Content Type:** {msg.content_type.title()}
**Lead Type:** {summary.lead_type.value.title()}
**Sentiment:** {self._sentiment_emoji(summary.sentiment)} {summary.sentiment.title()}
**Confidence:** {summary.confidence:.0%}
**Tweet Length:** {tweet_chars}/{MAX_TWEET_LENGTH} characters

---

## Message Summary

{summary.summary_text}

---

## Original Content

**From:** {msg.sender} ({msg.sender_handle})
**Received:** {msg.received.strftime('%Y-%m-%d %H:%M:%S')}
**Keywords:** {', '.join(msg.keywords)}
**Type:** {msg.content_type.title()}

```
{msg.content}
```

---

## Suggested Tweet Response

```
{summary.suggested_tweet}
```

**Character Count:** {tweet_chars}/{MAX_TWEET_LENGTH}

---

## Suggested DM (Alternative)

For longer responses, consider sending a DM:

```
{summary.suggested_dm}
```

---

## Action Items

{action_items_md}

---

## HITL Approval Required

This draft requires human review before posting/sending:

1. Review the suggested tweet/DM above
2. Edit for tone, accuracy, and brand voice
3. Verify all claims and commitments
4. Post/send via Twitter
5. Move to `/Approved` when complete

---

## Approval Checklist

- [ ] Response tone matches brand voice
- [ ] Tweet is under 280 characters
- [ ] All information is accurate
- [ ] No over-promises made
- [ ] Hashtags are relevant
- [ ] Ready to post/send

---

*Generated by Twitter Post Generator • {timestamp}*
"""

    def _sentiment_emoji(self, sentiment: str) -> str:
        """Get emoji for sentiment."""
        emojis = {"positive": "😊", "negative": "😟", "neutral": "😐"}
        return emojis.get(sentiment, "😐")

    def _create_approval_request(
        self, summary: MessageSummary, draft_path: Path
    ) -> Optional[Path]:
        """Create HITL approval request."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"APPROVAL_twitter_response_{timestamp}.md"
            filepath = PENDING_APPROVAL_DIR / filename

            # Copy draft with approval header
            with open(draft_path, "r", encoding="utf-8") as f:
                draft_content = f.read()

            approval_header = f"""---
type: hitl_approval_request
action_type: twitter_response
created: {datetime.now().isoformat()}
status: pending
priority: {summary.message.priority}
---

# 🎯 Approval Required: Twitter Response

**Draft Source:** {draft_path.name}
**Platform:** Twitter (X)
**Content Type:** {summary.message.content_type.title()}
**Lead Type:** {summary.lead_type.value.title()}

---

## Review Instructions

1. Read the original content and draft response
2. Edit the response as needed for tone and accuracy
3. Ensure tweet is under 280 characters
4. Once approved, post/send via Twitter
5. Move this file to `/Approved` after posting

---

"""

            full_content = approval_header + draft_content

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(full_content)

            self.logger.info(f"Approval request created: {filename}")
            return filepath

        except Exception as e:
            self.logger.error(f"Error creating approval request: {e}")
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Summary Logger
# ─────────────────────────────────────────────────────────────────────────────


class SummaryLogger:
    """Logs processing summaries."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.log_file = LOGS_DIR / f"twitter_post_gen_{datetime.now().strftime('%Y-%m-%d')}.md"
        self._ensure_log_file()

    def _ensure_log_file(self) -> None:
        """Ensure log file exists with header."""
        if not self.log_file.exists():
            with open(self.log_file, "w", encoding="utf-8") as f:
                f.write(f"""# Twitter Post Generator Log

**Created:** {datetime.now().isoformat()}
**Date:** {datetime.now().strftime('%Y-%m-%d')}

---

## Processing Entries

""")

    def log_result(self, result: ProcessingResult) -> None:
        """Log processing result."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        status = "✅" if result.success else "❌"

        entry = f"""### [{timestamp}] {status} Processed: {result.message.file_path.name}

- **Content Type:** {result.message.content_type.title()}
- **Lead Type:** {result.summary.lead_type.value.title() if result.summary else 'N/A'}
- **Sentiment:** {result.summary.sentiment.title() if result.summary else 'N/A'}
- **Draft Saved:** {result.draft_path.name if result.draft_path else 'N/A'}
- **Tweet Length:** {len(result.summary.suggested_tweet) if result.summary else 'N/A'} chars

"""
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(entry)


# ─────────────────────────────────────────────────────────────────────────────
# Twitter Post Generator (Main Class)
# ─────────────────────────────────────────────────────────────────────────────


class TwitterPostGenerator:
    """Main Twitter Post Generator skill class."""

    def __init__(self) -> None:
        self.logger = setup_logging()
        self.parser = MessageParser(self.logger)
        self.summary_gen = SummaryGenerator(self.logger)
        self.draft_mgr = DraftManager(self.logger)
        self.result_logger = SummaryLogger(self.logger)

        # Ensure directories exist
        for directory in [NEEDS_ACTION_DIR, PLANS_DIR, PENDING_APPROVAL_DIR, LOGS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

        # Results tracking
        self.results: list[ProcessingResult] = []

    def run(self) -> list[ProcessingResult]:
        """Execute the Twitter Post Generator skill."""
        self.logger.info("=" * 60)
        self.logger.info("TWITTER POST GENERATOR - STARTING")
        self.logger.info("=" * 60)

        print(f"\n{'=' * 60}")
        print("  🐦 TWITTER POST GENERATOR")
        print(f"  Processing Twitter content...")
        print(f"{'=' * 60}\n")

        try:
            # Scan Needs_Action for Twitter content
            messages = self._scan_needs_action()

            if not messages:
                print("📭 No Twitter messages to process\n")
                self.logger.info("No Twitter messages found")
                return self.results

            # Process each message
            for msg in messages:
                self._process_message(msg)

            # Print summary
            self._print_summary()

            return self.results

        except Exception as e:
            self.logger.exception(f"Skill execution failed: {e}")
            print(f"\n❌ Skill execution failed: {e}\n")
            return self.results

    def _scan_needs_action(self) -> list[TwitterMessage]:
        """Scan Needs_Action for Twitter messages."""
        messages = []

        try:
            md_files = list(NEEDS_ACTION_DIR.glob("*.md"))
            self.logger.info(f"Scanning {len(md_files)} files in Needs_Action")

            for file_path in md_files:
                msg = self.parser.parse_message(file_path)
                if msg:
                    messages.append(msg)

            self.logger.info(f"Found {len(messages)} Twitter messages")
            return messages

        except Exception as e:
            self.logger.error(f"Error scanning: {e}")
            return []

    def _process_message(self, message: TwitterMessage) -> None:
        """Process a single message."""
        self.logger.info(f"Processing: {message.file_path.name}")

        try:
            # Generate summary
            summary = self.summary_gen.generate_summary(message)

            # Save draft
            draft_path = self.draft_mgr.save_draft(summary)

            # Create result
            result = ProcessingResult(
                message=message,
                summary=summary,
                draft_path=draft_path,
                success=True,
            )

            self.results.append(result)
            self.result_logger.log_result(result)

            # Print status
            self._print_message_status(result)

        except Exception as e:
            self.logger.exception(f"Error processing {message.file_path.name}: {e}")
            result = ProcessingResult(
                message=message,
                summary=None,
                draft_path=None,
                success=False,
                error=str(e),
            )
            self.results.append(result)

    def _print_message_status(self, result: ProcessingResult) -> None:
        """Print status for processed message."""
        emoji = "✅" if result.success else "❌"
        type_emoji = {
            "dm": "💬",
            "tweet": "🐦",
            "notification": "🔔",
        }.get(result.message.content_type, "📱")

        print(f"  {emoji} {type_emoji} {result.message.file_path.name}")
        print(f"     Lead Type: {result.summary.lead_type.value}")
        print(f"     Sentiment: {result.summary.sentiment}")
        print(f"     Tweet: {len(result.summary.suggested_tweet)} chars")
        print(f"     Draft: {result.draft_path.name if result.draft_path else 'N/A'}")
        print()

    def _print_summary(self) -> None:
        """Print execution summary."""
        successful = sum(1 for r in self.results if r.success)
        sales_leads = sum(
            1 for r in self.results
            if r.success and r.summary.lead_type == LeadType.SALES
        )

        print(f"\n{'=' * 60}")
        print("  ✅ TWITTER POST GENERATOR - COMPLETE")
        print(f"{'=' * 60}")
        print(f"  Messages Processed:  {len(self.results)}")
        print(f"  Successful:          {successful}")
        print(f"  Sales Leads:         {sales_leads}")
        print(f"\n  📁 Drafts saved to: /Plans/")
        print(f"  🎯 Approval requests in: /Pending_Approval/")
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

    skill = TwitterPostGenerator()
    skill.run()


if __name__ == "__main__":
    main()
