# 📊 Audit Logger - Gold Tier

**Version:** 1.0.0
**Effective:** 2026-03-23
**Tier:** Gold

---

## 📋 Overview

The Audit Logger provides comprehensive logging for all AI Employee actions with:

| Feature | Description |
|---------|-------------|
| **JSON Lines Format** | Each entry is a valid JSON object on its own line |
| **90-Day Retention** | Automatic cleanup of logs older than 90 days |
| **Weekly Summary** | Integrated into CEO weekly briefing |
| **Full Traceability** | Timestamp, actor, target, parameters, result |

---

## 📁 Files

| File | Purpose |
|------|---------|
| `tools/audit_logger.py` | Core audit logging utilities |
| `Logs/audit_[date].jsonl` | Daily audit log files |

---

## 📝 Log Format

Each audit entry contains:

```json
{
    "timestamp": "2026-03-23T20:26:32.048799",
    "action_type": "SKILL_START",
    "actor": "cross_domain_integrator",
    "target": "Needs_Action/task.md",
    "parameters": {
        "classification": "business"
    },
    "approval_status": "not_required",
    "result": "success",
    "duration_ms": 150,
    "error": null,
    "session_id": "session_1774279592",
    "hostname": "DESKTOP-AMMQCHP"
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | ISO 8601 | When the action occurred |
| `action_type` | string | Type of action (see below) |
| `actor` | string | Skill/watcher/user that performed action |
| `target` | string | File/task/resource being acted upon |
| `parameters` | object | Additional context/parameters |
| `approval_status` | string | not_required/pending/approved/rejected |
| `result` | string | success/failure/partial/skipped |
| `duration_ms` | integer | How long the action took (milliseconds) |
| `error` | string/null | Error message if failed |
| `session_id` | string | Unique session identifier |
| `hostname` | string | Machine where action occurred |

---

## 🔧 Action Types

### Skill Lifecycle
- `SKILL_START` - Skill execution started
- `SKILL_END` - Skill execution completed
- `SKILL_ERROR` - Skill encountered error

### Watcher Operations
- `WATCHER_START` - Watcher started
- `WATCHER_CHECK` - Watcher checked for new items
- `WATCHER_STOP` - Watcher stopped
- `WATCHER_ERROR` - Watcher encountered error

### Task Processing
- `TASK_RECEIVED` - Task received for processing
- `TASK_CLASSIFIED` - Task classified
- `TASK_PROCESSED` - Task processed
- `TASK_COMPLETED` - Task completed successfully
- `TASK_FAILED` - Task processing failed

### File Operations
- `FILE_CREATED` - File created
- `FILE_MODIFIED` - File modified
- `FILE_DELETED` - File deleted
- `FILE_MOVED` - File moved

### Approval Workflow
- `APPROVAL_REQUESTED` - Approval requested
- `APPROVAL_GRANTED` - Approval granted
- `APPROVAL_REJECTED` - Approval rejected

### API/External
- `API_CALL` - External API called
- `API_RESPONSE` - API response received
- `API_ERROR` - API call failed

### System
- `SYSTEM_START` - System started
- `SYSTEM_STOP` - System stopped
- `SYSTEM_ERROR` - System error
- `CONFIG_CHANGE` - Configuration changed

---

## 💻 Usage

### Basic Logging

```python
from tools.audit_logger import AuditLogger, ActionType, ActionResult

# Create logger
logger = AuditLogger("my_skill")

# Log action
logger.log_action(
    ActionType.TASK_PROCESSED,
    "task.md",
    {"classification": "business"},
    result=ActionResult.SUCCESS,
)
```

### Context Manager (Automatic Start/End)

```python
from tools.audit_logger import AuditContext

with AuditContext("skill_name", "Processing task") as ctx:
    # Do work
    ctx.log_action(ActionType.TASK_PROCESSED, "task.md")
    # End is logged automatically
```

### Decorator (Automatic Logging)

```python
from tools.audit_logger import audit_skill_execution

@audit_skill_execution("my_skill")
def run_skill():
    # Skill code - automatically logged
    pass
```

### Get Summary

```python
from tools.audit_logger import AuditLogger

logger = AuditLogger("analyzer")

# Daily summary
daily = logger.get_daily_summary("2026-03-23")
print(f"Total actions: {daily['total_actions']}")

# Weekly summary
weekly = logger.get_weekly_summary()
print(f"Weekly total: {weekly['total_actions']}")
```

### Cleanup Old Logs

```python
# Delete logs older than 90 days
deleted = logger.cleanup_old_logs()
print(f"Deleted {deleted} old log files")
```

---

## 📊 Weekly Audit Summary (CEO Briefing)

The audit summary is automatically included in the CEO weekly briefing:

```markdown
## 📊 Audit Summary

**Period:** 2026-03-17 to 2026-03-23

### Activity Overview

| Metric | Value |
|--------|-------|
| **Total Actions** | 150 |
| **Success Rate** | 98.7% |
| **Errors** | 2 |
| **Unique Sessions** | 12 |

### Action Breakdown

| Category | Count |
|----------|-------|
| Skill Operations | 80 |
| Watcher Operations | 50 |
| Task Processing | 20 |

### Top Actors

| Actor | Actions |
|-------|---------|
| cross_domain_integrator | 45 |
| gmail_watcher | 30 |
| twitter_watcher | 25 |
```

---

## 🔍 Querying Audit Logs

### View Today's Logs

```bash
# Windows
type Logs\audit_%date:~0,4%-%date:~4,2%-%date:~7,2%.jsonl

# Linux/Mac
cat Logs/audit_$(date +%Y-%m-%d).jsonl
```

### Parse with Python

```python
import json
from pathlib import Path

log_file = Path("Logs/audit_2026-03-23.jsonl")

with open(log_file) as f:
    for line in f:
        entry = json.loads(line)
        print(f"{entry['timestamp']}: {entry['action_type']} by {entry['actor']}")
```

### Filter Errors

```python
import json

errors = []
with open("Logs/audit_2026-03-23.jsonl") as f:
    for line in f:
        entry = json.loads(line)
        if entry.get("error"):
            errors.append(entry)

print(f"Found {len(errors)} errors")
```

### Count by Action Type

```python
import json
from collections import Counter

counts = Counter()
with open("Logs/audit_2026-03-23.jsonl") as f:
    for line in f:
        entry = json.loads(line)
        counts[entry["action_type"]] += 1

for action, count in counts.most_common():
    print(f"{action}: {count}")
```

---

## 🧪 Test Guide

### Test 1: Basic Logging

```bash
cd E:\Hackathon 0\AI_Employee_Vault
python tools\audit_logger.py

# Expected: 4 entries logged
# Check: Logs\audit_[date].jsonl
```

### Test 2: Skill Integration

```bash
# Run a skill with audit logging
python skills\cross_domain_integrator.py

# Check audit log for entries
type Logs\audit_*.jsonl | findstr cross_domain
```

### Test 3: Weekly Summary

```python
from tools.audit_logger import AuditSummaryGenerator

gen = AuditSummaryGenerator()
summary = gen.generate_briefing_section()
print(summary)
```

### Test 4: Log Cleanup

```python
from tools.audit_logger import AuditLogger

logger = AuditLogger("test")
deleted = logger.cleanup_old_logs(retention_days=90)
print(f"Deleted {deleted} files")
```

---

## 📈 Monitoring & Alerts

### High Error Rate

```python
from tools.audit_logger import AuditLogger

logger = AuditLogger("monitor")
weekly = logger.get_weekly_summary()

error_rate = weekly["total_errors"] / weekly["total_actions"] * 100
if error_rate > 5:
    print(f"⚠️ High error rate: {error_rate:.1f}%")
```

### Unusual Activity

```python
# Check for unusual spike in actions
daily = logger.get_daily_summary()
if daily["total_actions"] > 1000:
    print("⚠️ Unusual activity spike detected")
```

---

## 🔐 Security Considerations

### What Gets Logged

✅ **Logged:**
- Action type and timestamp
- Actor (skill/watcher name)
- Target file/task
- Result (success/failure)
- Duration
- Error messages

❌ **NOT Logged:**
- File contents
- Credentials/tokens
- Personal data from messages
- API keys

### Log Access

- Logs stored in `/Logs/audit_[date].jsonl`
- Retained for 90 days
- Can be reviewed for debugging/auditing
- Should be included in backups

---

## 📎 Quick Reference

```bash
# ─────────────────────────────────────────────────────────────
# VIEW AUDIT LOGS
# ─────────────────────────────────────────────────────────────

# Today's audit log
type Logs\audit_*.jsonl

# Specific date
type Logs\audit_2026-03-23.jsonl

# Count entries
wc -l Logs\audit_*.jsonl

# ─────────────────────────────────────────────────────────────
# PYTHON USAGE
# ─────────────────────────────────────────────────────────────

# Create logger
from tools.audit_logger import AuditLogger
logger = AuditLogger("my_skill")

# Log action
logger.log_action(ActionType.TASK_PROCESSED, "task.md")

# Get summary
summary = logger.get_daily_summary()

# Cleanup old logs
logger.cleanup_old_logs()

# ─────────────────────────────────────────────────────────────
# TEST COMMANDS
# ─────────────────────────────────────────────────────────────

# Test audit logger
python tools\audit_logger.py

# Test skill with audit logging
python skills\cross_domain_integrator.py

# View audit summary in briefing
python skills\weekly_audit_briefer.py --force
```

---

*Audit Logger v1.0.0 • AI Employee Gold Tier*
