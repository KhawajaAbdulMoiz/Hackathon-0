# Daily Scheduler - AI Employee Vault

Automated daily briefing generation for AI Employee system.

## Features

| Feature | Description |
|---------|-------------|
| **Daily Briefing** | Generates summary from /Done files at 8AM daily |
| **Productivity Tracking** | Compares today vs yesterday completion |
| **Recommendations** | Suggests actions based on vault state |
| **Cross-Platform** | Works on Windows (PowerShell), Mac/Linux (Bash) |

---

## Files

| File | Platform |
|------|----------|
| `daily_scheduler.sh` | Linux/Mac |
| `daily_scheduler.ps1` | Windows |

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

*Daily Scheduler v1.0.0 • AI Employee Vault*
