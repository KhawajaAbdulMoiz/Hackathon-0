# 🔄 Ralph Wiggum Loop Runner - Gold Tier

**Version:** 1.0.0
**Effective:** 2026-03-23
**Tier:** Gold

---

## 📋 Overview

The Ralph Wiggum Loop Runner is an autonomous multi-step task processor for Gold Tier AI Employee operations.

**Workflow Example:**
```
Sales Lead → Classify → Route → Draft Post → HITL Approval → MCP Execute → Log → Archive
```

### Features

| Feature | Description |
|---------|-------------|
| **Multi-Step Processing** | Handles complex workflows with multiple dependent steps |
| **Max 20 Iterations** | Configurable iteration limit per task |
| **Audit Integration** | All actions logged to `/Logs/audit_[date].jsonl` |
| **Cross Domain Integration** | Works with Cross Domain Integrator |
| **Automatic File Movement** | Moves files to Done on completion |
| **HITL Support** | Integrates with Human-in-the-Loop approval |

---

## 📁 Files

| File | Purpose |
|------|---------|
| `tools/ralph_loop_runner.py` | Main loop runner script |
| `Logs/ralph_loop_[date].log` | Loop execution logs |
| `Logs/audit_[date].jsonl` | Audit trail |

---

## 🚀 Quick Start

### Basic Command

```bash
cd E:\Hackathon 0\AI_Employee_Vault
python tools\ralph_loop_runner.py "Process multi-step task" --max-iterations 20
```

### With Custom Description

```bash
python tools\ralph_loop_runner.py "Process sales leads in Needs_Action" --max-iterations 15
```

---

## 🧪 Test Guide

### Test 1: Create Multi-Step Task File

Create a test file in `Needs_Action/`:

```markdown
---
type: sales_lead
source: facebook
priority: P1
keywords: sales, project, client
---

# Sales Lead: New Project Inquiry

Hi! I'm interested in your sales services for my upcoming project.
Budget: $50,000
Timeline: Q2 launch

This is urgent - board meeting next week.

Thanks,
John Smith
CEO, TechCorp Inc.
```

Save as: `Needs_Action/test_multistep_sales_lead.md`

### Test 2: Run Ralph Loop

```bash
cd E:\Hackathon 0\AI_Employee_Vault
python tools\ralph_loop_runner.py "Process multi-step sales lead" --max-iterations 20
```

### Expected Output

```
============================================================
  🔄 RALPH WIGGUM LOOP RUNNER
  Process multi-step sales lead
  Max Iterations: 20
============================================================

📋 Processing: 📋 Sales Lead: New Project Inquiry...
   Classified: business | Route: SOCIAL_AUTO
   Iteration 1: Draft social post
   Iteration 2: Wait for approval
   Iteration 3: Post to platform
   Iteration 4: Log action
   Iteration 5: Archive to Done
   ✅ TASK_COMPLETE (Iterations: 5, Steps: 5/5)

============================================================
  ✅ RALPH LOOP RUNNER - COMPLETE
============================================================
  Tasks Processed:  1
  Completed:        1
  Failed:           0
============================================================
```

### Test 3: Verify Files

```bash
# Check task was moved to Done
dir Done\*sales*

# Check draft was created
dir Plans\*ralph*

# Check audit log
type Logs\audit_*.jsonl | findstr ralph
```

### Test 4: Verify Audit Log

```bash
# View Ralph Loop audit entries
type Logs\audit_2026-03-23.jsonl | findstr ralph
```

**Expected entries:**
- `TASK_RECEIVED` - Task scanned from Needs_Action
- `TASK_CLASSIFIED` - Task classified as business/personal
- `TASK_PROCESSED` - Routing decision logged
- `FILE_CREATED` - Draft file created
- `API_CALL` - MCP execution (simulated)
- `TASK_COMPLETED` - Task finished
- `FILE_MOVED` - Original moved to Done
- `FILE_CREATED` - Completed file in Done

---

## 📊 Multi-Step Workflow

### Business Task (Social Media)

```
1. CLASSIFY → Detect business keywords (sales, client, project)
2. ROUTE → SOCIAL_AUTO (for LinkedIn/Twitter/Facebook)
3. DRAFT → Create draft post in /Plans/
4. APPROVE → Auto-approve (or wait for HITL)
5. EXECUTE → Post to platform via MCP
6. LOG → Record action in audit log
7. ARCHIVE → Move to /Done/
```

### Personal Task (Email/Message)

```
1. CLASSIFY → Detect personal keywords (email, message, gmail)
2. ROUTE → HITL (Human-in-the-Loop)
3. DRAFT → Create draft response
4. APPROVE → Wait for human approval
5. EXECUTE → Send via MCP (Gmail/WhatsApp)
6. LOG → Record action in audit log
7. ARCHIVE → Move to /Done/
```

---

## 🔧 Configuration

### Command Line Options

```bash
python tools\ralph_loop_runner.py [task_description] [--max-iterations N]

Arguments:
  task_description    Description of task to process (default: "Process multi-step task")
  --max-iterations    Maximum iterations per task (default: 20)
```

### Step Timeout

```python
STEP_TIMEOUT: Final[float] = 300.0  # 5 minutes per step
```

### Loop Delay

```python
LOOP_DELAY: Final[float] = 1.0  # 1 second between iterations
```

---

## 📝 Example Log Entry

```json
{
  "timestamp": "2026-03-23T20:30:59.598928",
  "action_type": "TASK_CLASSIFIED",
  "actor": "ralph_loop_runner",
  "target": "test_multistep_sales_lead.md",
  "parameters": {
    "domain": "business",
    "personal_score": 1,
    "business_score": 3,
    "keywords_found": []
  },
  "approval_status": "not_required",
  "result": "success",
  "duration_ms": 0,
  "error": null,
  "session_id": "session_1774279859",
  "hostname": "DESKTOP-AMMQCHP"
}
```

---

## 🔄 Workflow States

| State | Description |
|-------|-------------|
| `PENDING` | Task waiting to be processed |
| `IN_PROGRESS` | Task currently being processed |
| `WAITING_APPROVAL` | Task waiting for HITL approval |
| `COMPLETED` | Task completed successfully |
| `FAILED` | Task failed (error occurred) |
| `BLOCKED` | Task blocked (manual intervention needed) |

---

## 🐛 Troubleshooting

### Task Not Processing

**Problem:** Task stays in Needs_Action

**Solution:**
1. Check file has `.md` extension
2. Verify file has valid markdown content
3. Run with `--max-iterations 20`

### Step Failing

**Problem:** Step fails with error

**Solution:**
1. Check `Logs/ralph_loop_[date].log` for details
2. Check `Logs/audit_[date].jsonl` for error entry
3. Verify required directories exist

### Files Not Moving

**Problem:** Task file stays in Needs_Action after completion

**Solution:**
1. Check file permissions
2. Verify Done folder exists
3. Check audit log for FILE_MOVED entry

---

## 📎 Quick Reference

```bash
# ─────────────────────────────────────────────────────────────
# BASIC COMMANDS
# ─────────────────────────────────────────────────────────────

# Run Ralph Loop
python tools\ralph_loop_runner.py "Process tasks" --max-iterations 20

# Run with custom description
python tools\ralph_loop_runner.py "Process sales leads" --max-iterations 15

# ─────────────────────────────────────────────────────────────
# VERIFY RESULTS
# ─────────────────────────────────────────────────────────────

# Check completed tasks
dir Done\*.md

# Check drafts created
dir Plans\*ralph*.md

# Check approval requests
dir Pending_Approval\*.md

# View audit log
type Logs\audit_*.jsonl

# View loop logs
type Logs\ralph_loop_*.log

# ─────────────────────────────────────────────────────────────
# CREATE TEST TASK
# ─────────────────────────────────────────────────────────────

# Create test sales lead
echo ---
type: sales_lead
priority: P1
keywords: sales, project
---
# Test Sales Lead

Interested in your services for my project.
Budget: $10,000

> Needs_Action\test_sales.md
```

---

## 🔗 Integration Points

| Integration | Purpose |
|-------------|---------|
| **Cross Domain Integrator** | Task classification and routing |
| **Audit Logger** | Full action traceability |
| **HITL Handler** | Human approval workflow |
| **MCP Servers** | External API execution |

---

*Ralph Wiggum Loop Runner v1.0.0 • AI Employee Gold Tier*
