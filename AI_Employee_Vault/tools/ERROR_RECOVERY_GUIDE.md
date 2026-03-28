# 🛡️ Gold Tier Error Recovery Guide

**Version:** 1.0.0
**Effective:** 2026-03-23
**Tier:** Gold

---

## 📋 Overview

All Gold Tier watchers and skills now include comprehensive error recovery:

| Feature | Description |
|---------|-------------|
| **Exponential Backoff** | Max 3 retries, delay 1-60s |
| **Error Logging** | `/Logs/error_[component]_[date].log` |
| **Graceful Degradation** | Skip bad input, continue loop |
| **Error Reports** | `/Errors/skill_error_[date].md` |
| **Manual Action Plans** | `/Plans/manual_action_*.md` |

---

## 📁 Updated Files

### Watchers (with Error Recovery)

| File | Status | Error Log |
|------|--------|-----------|
| `Watchers/gmail_watcher.py` | ✅ Updated | `/Logs/error_gmail_watcher_[date].log` |
| `Watchers/facebook_instagram_watcher.py` | ✅ Updated | `/Logs/error_fb_ig_watcher_[date].log` |
| `Watchers/twitter_watcher.py` | ✅ Updated | `/Logs/error_twitter_watcher_[date].log` |

### Skills (with Error Recovery)

| File | Status | Error Report |
|------|--------|--------------|
| `skills/cross_domain_integrator.py` | ✅ Updated | `/Errors/skill_error_cross_domain_[date].md` |
| `skills/social_summary_generator.py` | ✅ Updated | `/Errors/skill_error_social_summary_[date].md` |
| `skills/twitter_post_generator.py` | ✅ Updated | `/Errors/skill_error_twitter_post_[date].md` |
| `skills/weekly_audit_briefer.py` | ✅ Updated | `/Errors/skill_error_weekly_audit_[date].md` |

### Core Utilities

| File | Purpose |
|------|---------|
| `tools/error_recovery.py` | Central error recovery utilities |

---

## 🔧 Error Recovery Features

### 1. Exponential Backoff Retry

```python
from tools.error_recovery import retry_with_backoff

@retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=60.0)
def api_call():
    # Network call that might fail
    pass
```

**Retry Schedule:**
- Attempt 1: Immediate
- Attempt 2: After 2s (1s × 2^1 + jitter)
- Attempt 3: After 4s (1s × 2^2 + jitter)
- Attempt 4: After 8s (1s × 2^3 + jitter)
- Max delay capped at 60s

### 2. Error Logging

All errors are logged to component-specific files:

```
/Logs/
├── error_gmail_watcher_2026-03-23.log
├── error_fb_ig_watcher_2026-03-23.log
├── error_twitter_watcher_2026-03-23.log
└── ...
```

**Log Entry Format:**
```
============================================================
[2026-03-23 10:30:45] [HIGH] gmail_watcher
============================================================
Error Type: ConnectionError
Message: Network timeout
Context: {'step': 'authenticate', 'retry': True}

Traceback:
...
============================================================
```

### 3. Graceful Degradation

When errors can't be recovered:

```python
from tools.error_recovery import GracefulDegradation

degradation = GracefulDegradation(logger)

try:
    result = mcp_server.call()
except Exception as e:
    # Degrade gracefully
    degradation.handle_failure(
        e, 
        "MCP Client", 
        "Using local processing instead"
    )
    # Continue with fallback logic
```

### 4. Manual Action Plans

When automated recovery fails:

```python
# Create manual action plan in /Plans/
plan_path = degradation.create_manual_action_plan(
    failed_operation="MCP Email Send",
    error=e,
    suggested_actions=[
        "Check MCP server status",
        "Verify credentials",
        "Manually send email",
        "Document outcome"
    ],
    priority="P1"
)
```

### 5. Error Reports

Comprehensive error reports generated to `/Errors/`:

```markdown
# 🚨 Error Report: social_summary_generator

**Generated:** 2026-03-23 10:30:45
**Total Errors:** 5
**Critical:** 0 | **High:** 1 | **Medium:** 2 | **Low:** 2

## Error Details
...

## Recovery Recommendations
- 🌐 **Network Issues:** Check internet connection
- 🔐 **Authentication:** Refresh credentials
```

---

## 🧪 Test Guide

### Test 1: Simulate Network Timeout (Watcher)

**Goal:** Verify exponential backoff retry

```bash
# 1. Temporarily disconnect network
# 2. Run watcher
cd E:\Hackathon 0\AI_Employee_Vault
python Watchers\gmail_watcher.py

# Expected behavior:
# - Retry 3 times with increasing delays
# - Log errors to /Logs/error_gmail_watcher_[date].log
# - Continue loop after max retries (graceful)
```

**Verify:**
```bash
# Check error log
type Logs\error_gmail_watcher_*.log

# Look for retry messages:
# "failed (attempt 1/3)... Retrying in 2.0s"
# "failed (attempt 2/3)... Retrying in 4.0s"
# "failed (attempt 3/3)... Retrying in 8.0s"
```

### Test 2: Simulate API Failure (Skill)

**Goal:** Verify graceful degradation

```bash
# 1. Create test file with invalid data
echo "---
type: social_media_message
platform: facebook
---

# Invalid content that will cause processing error
" > Needs_Action\test_error.md

# 2. Run skill
python skills\social_summary_generator.py

# Expected behavior:
# - Try to process file
# - Catch error
# - Log to /Errors/skill_error_*.md
# - Continue processing other files
```

**Verify:**
```bash
# Check error report
type Errors\skill_error_social_summary_*.md

# Check that skill didn't crash
# Other files should be processed
```

### Test 3: Simulate MCP Server Failure

**Goal:** Verify manual action plan creation

```bash
# 1. Stop any running MCP servers
# 2. Run skill that uses MCP
python skills\social_summary_generator.py

# Expected behavior:
# - Detect MCP failure
# - Create manual action plan in /Plans/
# - Log degradation action
```

**Verify:**
```bash
# Check for manual action plan
dir Plans\manual_action_*.md

# View plan content
type Plans\manual_action_*_email*.md
```

### Test 4: Verify Error Statistics

**Goal:** Check error recovery statistics

```python
# Run test script
python -c "
from tools.error_recovery import ErrorRecoveryManager, ErrorSeverity
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('test')

# Create recovery manager
recovery = ErrorRecoveryManager('test_component', logger)

# Record some errors
try:
    raise ConnectionError('Test network error')
except Exception as e:
    recovery.record_error(e, ErrorSeverity.MEDIUM, retry=True)

# Record success
recovery.record_success()

# Get stats
stats = recovery.get_stats()
print(f'Stats: {stats}')
"
```

---

## 📊 Error Severity Levels

| Severity | When to Use | Action |
|----------|-------------|--------|
| 🔴 **CRITICAL** | System failure, data loss | Stop execution, alert immediately |
| 🟠 **HIGH** | Authentication failure, API down | Retry with backoff, degrade if fails |
| 🟡 **MEDIUM** | Network timeout, temporary failure | Retry with backoff, log error |
| 🟢 **LOW** | Minor parsing error, missing optional data | Log only, continue processing |

---

## 🔧 Configuration

### Retry Settings

Edit `tools/error_recovery.py`:

```python
# Retry configuration
MAX_RETRIES: Final[int] = 3              # Maximum retry attempts
BASE_DELAY: Final[float] = 1.0           # Initial delay (seconds)
MAX_DELAY: Final[float] = 60.0           # Maximum delay (seconds)
EXPONENTIAL_BASE: Final[int] = 2         # Exponential backoff base
```

### Error Log Location

```python
LOGS_DIR: Final[Path] = VAULT_ROOT / "Logs"
ERRORS_DIR: Final[Path] = VAULT_ROOT / "Errors"

# Error log file pattern
log_file = LOGS_DIR / f"error_{component_name}_{date}.log"
```

---

## 📈 Monitoring Error Recovery

### Check Error Frequency

```bash
# Count errors in last 24 hours
Get-ChildItem Logs\error_*.log | Where-Object {
    $_.LastWriteTime -gt (Get-Date).AddHours(-24)
} | Measure-Object
```

### Review Error Reports

```bash
# List recent error reports
dir Errors\skill_error_*.md | Sort-Object LastWriteTime -Descending | Select-Object -First 5
```

### Monitor Recovery Stats

```python
from tools.error_recovery import ErrorRecoveryManager

recovery = ErrorRecoveryManager('component_name', logger)
stats = recovery.get_stats()

print(f"Success rate: {stats['success_count'] / (stats['success_count'] + stats['error_count']) * 100:.1f}%")
print(f"Recovered: {stats['recovered_count']} / {stats['error_count']} errors")
```

---

## 🐛 Troubleshooting

### Too Many Retries

**Problem:** Excessive retry attempts slowing down processing

**Solution:** Reduce max retries or increase base delay
```python
@retry_with_backoff(max_retries=2, base_delay=2.0)
```

### Errors Not Logged

**Problem:** Error logs not being created

**Solution:** Check directory permissions and imports
```bash
# Ensure directories exist
mkdir Logs Errors

# Verify import in watcher/skill
from tools.error_recovery import ErrorRecoveryManager
```

### Graceful Degradation Not Triggering

**Problem:** System crashes instead of degrading

**Solution:** Wrap code in try-except with degradation handler
```python
try:
    result = risky_operation()
except Exception as e:
    degradation.handle_failure(e, "Component", "Fallback action")
    result = fallback_operation()
```

---

## 📎 Quick Reference

```bash
# ─────────────────────────────────────────────────────────────
# ERROR LOG LOCATIONS
# ─────────────────────────────────────────────────────────────

# Watcher error logs
dir Logs\error_gmail_watcher_*.log
dir Logs\error_fb_ig_watcher_*.log
dir Logs\error_twitter_watcher_*.log

# Skill error reports
dir Errors\skill_error_*.md

# Manual action plans
dir Plans\manual_action_*.md

# ─────────────────────────────────────────────────────────────
# TESTING COMMANDS
# ─────────────────────────────────────────────────────────────

# Test error recovery utilities
python tools\error_recovery.py

# Run watcher with simulated error
# (Disconnect network, then run)
python Watchers\gmail_watcher.py

# Run skill with invalid input
echo "invalid" > Needs_Action\test.md
python skills\social_summary_generator.py

# ─────────────────────────────────────────────────────────────
# MONITORING
# ─────────────────────────────────────────────────────────────

# View recent errors
Get-ChildItem Logs\error_*.log -Recurse | 
    Sort-Object LastWriteTime -Descending | 
    Select-Object -First 5

# Count errors by severity
Select-String -Path Logs\error_*.log -Pattern "\[HIGH\]|\[MEDIUM\]|\[LOW\]" | 
    Group-Object

# Check recovery success rate
python -c "from tools.error_recovery import ErrorRecoveryManager; print(ErrorRecoveryManager('test', None).get_stats())"
```

---

*Gold Tier Error Recovery • AI Employee System*
