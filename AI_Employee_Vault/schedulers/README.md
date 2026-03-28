# Daily & Weekly Scheduler - AI Employee Vault

Automated daily and weekly briefing generation for AI Employee system.

## Features

| Feature | Description |
|---------|-------------|
| **Daily Briefing** | Generates summary from /Done files at 8AM daily |
| **Weekly CEO Briefing** | Comprehensive audit with revenue, tasks, bottlenecks (Sunday 9AM) |
| **Productivity Tracking** | Compares today vs yesterday completion |
| **Revenue Analysis** | Pattern matching for income/expenses/subscriptions |
| **Bottleneck Detection** | Identifies system and workflow issues |
| **Cross-Platform** | Works on Windows (PowerShell), Mac/Linux (Bash) |

---

## Files

| File | Type | Platform |
|------|------|----------|
| `daily_scheduler.sh` | Daily | Linux/Mac |
| `daily_scheduler.ps1` | Daily | Windows |
| `weekly_scheduler.ps1` | Weekly | Windows |

---

## Manual Testing

### Linux/Mac
```bash
cd "E:\Hackathon 0\AI_Employee_Vault"
bash schedulers/daily_scheduler.sh
```

### Windows (PowerShell)
```powershell
cd "E:\Hackathon 0\AI_Employee_Vault"
powershell -ExecutionPolicy Bypass -File schedulers\daily_scheduler.ps1
```

---

## Scheduled Setup

### Linux/Mac (Cron)

1. **Open crontab:**
   ```bash
   crontab -e
   ```

2. **Add daily 8AM entry:**
   ```bash
   0 8 * * * /bin/bash /path/to/AI_Employee_Vault/schedulers/daily_scheduler.sh
   ```

3. **Make script executable:**
   ```bash
   chmod +x schedulers/daily_scheduler.sh
   ```

4. **Verify cron job:**
   ```bash
   crontab -l
   ```

5. **Check cron logs (if needed):**
   ```bash
   # Ubuntu/Debian
   grep CRON /var/log/syslog
   
   # macOS
   log show --predicate 'process == "cron"' --last 1h
   ```

### Windows (Task Scheduler)

#### Method 1: GUI Setup

1. **Open Task Scheduler:**
   - Press `Win + R`
   - Type `taskschd.msc`
   - Press Enter

2. **Create Basic Task:**
   - Click "Create Basic Task..." in right panel
   - Name: `AI Employee Daily Scheduler`
   - Description: `Generates daily briefing from Done files`

3. **Set Trigger:**
   - Select "Daily"
   - Start time: `8:00:00 AM`
   - Recur every: `1` days

4. **Set Action:**
   - Select "Start a program"
   - Program/script: `powershell.exe`
   - Add arguments: `-ExecutionPolicy Bypass -File "E:\Hackathon 0\AI_Employee_Vault\schedulers\daily_scheduler.ps1"`
   - Start in: `E:\Hackathon 0\AI_Employee_Vault\schedulers`

5. **Finish and Test:**
   - Click Finish
   - Right-click task → "Run" to test

#### Method 2: PowerShell Command

```powershell
# Create scheduled task via PowerShell
$taskName = "AI Employee Daily Scheduler"
$scriptPath = "E:\Hackathon 0\AI_Employee_Vault\schedulers\daily_scheduler.ps1"
$startTime = "8:00 AM"

# Create trigger (daily at 8AM)
$trigger = New-ScheduledTaskTrigger -Daily -At $startTime

# Create action (run PowerShell script)
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -File `"$scriptPath`"" `
    -WorkingDirectory "E:\Hackathon 0\AI_Employee_Vault\schedulers"

# Create principal (run with highest privileges)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Register the task
Register-ScheduledTask -TaskName $taskName `
    -Trigger $trigger `
    -Action $action `
    -Principal $principal `
    -Description "Generates daily briefing from AI Employee Done files"

# Verify
Get-ScheduledTask -TaskName $taskName

# Test run
Start-ScheduledTask -TaskName $taskName
```

---

## Output

### Daily Briefing File

Location: `/Logs/daily_briefing_[date].md`

```markdown
# 📅 Daily Briefing: 2026-02-25

**Generated:** 2026-02-25 08:00:00
**Day:** Wednesday
**Status:** 🟢 Complete

---

## 📊 Today's Summary

| Metric | Value |
|--------|-------|
| **Tasks Completed** | 5 |
| **Yesterday's Count** | 3 |
| **Active Plans** | 2 |
| **Pending Approval** | 1 |
| **Needs Action** | 0 |

---

## ✅ Completed Today

| Task | Time | Notes |
|------|------|-------|
| 2026-02-25_email_task.md | 07:45 | Auto-processed |
| 2026-02-25_sales_lead.md | 09:30 | Auto-processed |

---

## 📈 Productivity Analysis

**Trend:** 📈 Up from yesterday (3 → 5)

---

## 🎯 Recommendations

- ✅ Good progress today! Keep it up.
```

### Execution Log

Location: `/Logs/scheduler_execution_[date].log`

```
[2026-02-25 08:00:01] [INFO] Starting daily scheduler...
[2026-02-25 08:00:01] [INFO] Directories verified
[2026-02-25 08:00:01] [INFO] Generating daily briefing...
[2026-02-25 08:00:02] [INFO] Daily briefing created: daily_briefing_2026-02-25.md
[2026-02-25 08:00:02] [INFO] Daily scheduler complete
```

---

## Customization

### Change Schedule Time

**Cron (Linux/Mac):**
```bash
# Run at 9AM instead
0 9 * * * /path/to/daily_scheduler.sh

# Run twice daily (8AM and 5PM)
0 8,17 * * * /path/to/daily_scheduler.sh

# Run only on weekdays
0 8 * * 1-5 /path/to/daily_scheduler.sh
```

**Task Scheduler (Windows):**
- Open Task Scheduler
- Find "AI Employee Daily Scheduler" task
- Right-click → Properties → Triggers
- Edit trigger to change time

### Enable Notifications

Uncomment in script:

**Bash:**
```bash
# In daily_scheduler.sh
send_notification "Daily briefing generated: $today_count tasks completed"
```

**PowerShell:**
```powershell
# In daily_scheduler.ps1
Send-Notification "Daily briefing generated: $todayCount tasks completed"
```

### Enable Log Cleanup

Uncomment in script:

**Bash:**
```bash
cleanup_old_logs
```

**PowerShell:**
```powershell
Cleanup-OldLogs
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Script not running | Check execution policy: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| Cron job not firing | Check cron daemon: `sudo systemctl status cron` |
| Permission denied | Make executable: `chmod +x daily_scheduler.sh` |
| No briefing generated | Check Logs folder exists and is writable |
| Task Scheduler error | Run as different user with appropriate permissions |

---

## Quick Reference

```bash
# Test scheduler manually
bash schedulers/daily_scheduler.sh

# View today's briefing
cat Logs/daily_briefing_$(date +%Y-%m-%d).md

# View execution log
tail -f Logs/scheduler_execution_$(date +%Y-%m-%d).log

# List cron jobs
crontab -l

# List scheduled tasks (Windows)
Get-ScheduledTask | Where-Object {$_.TaskName -like "*AI Employee*"}
```

---

## Weekly Scheduler (Gold Tier)

### Overview

The Weekly Scheduler runs every Sunday at 9:00 AM to generate a comprehensive CEO Briefing:

- **Revenue Analysis**: Extracts income/expenses via pattern matching
- **Task Metrics**: Compares this week vs last week completion
- **Bottleneck Detection**: Identifies system and workflow issues
- **Goals Tracking**: Progress against Business_Goals.md
- **Suggestions**: AI-generated recommendations

### Manual Testing

#### Windows (PowerShell)
```powershell
cd "E:\Hackathon 0\AI_Employee_Vault"
powershell -ExecutionPolicy Bypass -File schedulers\weekly_scheduler.ps1

# Force run (any day)
powershell -ExecutionPolicy Bypass -File schedulers\weekly_scheduler.ps1 -Force
```

#### Python Skill (Cross-Platform)
```bash
cd "E:\Hackathon 0\AI_Employee_Vault"

# Run on Sunday (scheduled day)
python skills\weekly_audit_briefer.py

# Force run (any day)
python skills\weekly_audit_briefer.py --force
```

### Scheduled Setup (Windows)

#### Method 1: GUI Setup

1. **Open Task Scheduler:**
   - Press `Win + R`
   - Type `taskschd.msc`
   - Press Enter

2. **Create Basic Task:**
   - Click "Create Basic Task..." in right panel
   - Name: `AI Employee Weekly Scheduler`
   - Description: `Generates weekly CEO briefing with revenue and task analysis`

3. **Set Trigger:**
   - Select "Weekly"
   - Start time: `9:00:00 AM`
   - Days: Check "Sunday"
   - Recur every: `1` weeks

4. **Set Action:**
   - Select "Start a program"
   - Program/script: `powershell.exe`
   - Add arguments: `-ExecutionPolicy Bypass -File "E:\Hackathon 0\AI_Employee_Vault\schedulers\weekly_scheduler.ps1"`
   - Start in: `E:\Hackathon 0\AI_Employee_Vault\schedulers`

5. **Finish and Test:**
   - Click Finish
   - Right-click task → "Run" to test

#### Method 2: PowerShell Command

```powershell
# Create scheduled task via PowerShell
$taskName = "AI Employee Weekly Scheduler"
$scriptPath = "E:\Hackathon 0\AI_Employee_Vault\schedulers\weekly_scheduler.ps1"
$startTime = "9:00 AM"

# Create trigger (weekly on Sunday at 9AM)
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At $startTime

# Create action (run PowerShell script)
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -File `"$scriptPath`"" `
    -WorkingDirectory "E:\Hackathon 0\AI_Employee_Vault\schedulers"

# Create principal (run with highest privileges)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Register the task
Register-ScheduledTask -TaskName $taskName `
    -Trigger $trigger `
    -Action $action `
    -Principal $principal `
    -Description "Generates weekly CEO briefing from AI Employee vault data"

# Verify
Get-ScheduledTask -TaskName $taskName

# Test run
Start-ScheduledTask -TaskName $taskName
```

### Output

#### CEO Weekly Briefing File

Location: `/Briefings/ceo_briefing_[date].md`

```markdown
# 📊 CEO Weekly Briefing

**Week:** 2026-03-17 to 2026-03-23
**Generated:** 2026-03-23 09:00:00
**Status:** 🟢 Complete

---

## 📈 Executive Summary

| Metric | Value | Trend |
|--------|-------|-------|
| **Tasks Completed** | 15 | 📈 Up |
| **Revenue** | $4,048.00 | — |
| **Expenses** | $500.00 | — |
| **Net Profit** | $3,548.00 | 87.6% margin |
| **Pending Approvals** | 2 | — |

---

## 💰 Revenue Analysis
...
```

### Data Sources

| Source | Purpose |
|--------|---------|
| `/Done` | Task completion metrics |
| `/Logs` | Revenue/expense extraction, error detection |
| `Company_Handbook.md` | Operating guidelines reference |
| `Business_Goals.md` | Goal progress tracking |

### Pattern Matching

The Weekly Audit Briefer uses regex patterns to extract financial data:

**Revenue Patterns:**
- `revenue: $X,XXX.XX`
- `payment received: $X,XXX.XX`
- `income: $X,XXX.XX`
- `$X,XXX.XX received/earned/collected`

**Expense Patterns:**
- `expense: $X,XXX.XX`
- `cost: $X,XXX.XX`
- `subscription: $X,XXX.XX`
- `$X,XXX.XX spent/paid`

---

*Daily & Weekly Scheduler v1.0.0 • AI Employee Vault*
