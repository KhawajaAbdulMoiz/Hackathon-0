#
# Daily Scheduler - AI Employee Vault (Silver Tier)
# PowerShell Version for Windows
#
# Runs daily tasks for AI Employee system:
# - Generate daily summary from /Done files
# - Write briefing to /Logs/daily_briefing_[date].md
# - Clean up old logs (optional)
#
# Usage:
#   .\daily_scheduler.ps1
#
# Task Scheduler Setup (Windows):
#   1. Open Task Scheduler (taskschd.msc)
#   2. Click "Create Basic Task" in right panel
#   3. Name: "AI Employee Daily Scheduler"
#   4. Trigger: Daily at 8:00 AM
#   5. Action: Start a program
#      - Program: powershell.exe
#      - Arguments: -ExecutionPolicy Bypass -File "E:\Hackathon 0\AI_Employee_Vault\schedulers\daily_scheduler.ps1"
#      - Start in: E:\Hackathon 0\AI_Employee_Vault\schedulers
#   6. Finish and test
#
# Test Manually:
#   powershell -ExecutionPolicy Bypass -File .\schedulers\daily_scheduler.ps1
#

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VaultRoot = Split-Path -Parent $ScriptDir

$DoneDir = Join-Path $VaultRoot "Done"
$LogsDir = Join-Path $VaultRoot "Logs"
$PlansDir = Join-Path $VaultRoot "Plans"
$PendingApprovalDir = Join-Path $VaultRoot "Pending_Approval"
$NeedsActionDir = Join-Path $VaultRoot "Needs_Action"

$Date = Get-Date -Format "yyyy-MM-dd"
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$DayOfWeek = Get-Date -Format "dddd"

$LogFile = Join-Path $LogsDir "daily_briefing_${Date}.md"
$ExecutionLog = Join-Path $LogsDir "scheduler_execution_${Date}.log"

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

function Write-Log {
    param(
        [string]$Level,
        [string]$Message
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logLine = "[$timestamp] [$Level] $Message"
    
    # Write to console
    Write-Host $logLine
    
    # Append to execution log
    Add-Content -Path $ExecutionLog -Value $logLine -Encoding UTF8
}

# ─────────────────────────────────────────────────────────────────────────────
# Ensure Directories
# ─────────────────────────────────────────────────────────────────────────────

function Ensure-Directories {
    $dirs = @($DoneDir, $LogsDir, $PlansDir, $PendingApprovalDir, $NeedsActionDir)
    
    foreach ($dir in $dirs) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
    
    Write-Log "INFO" "Directories verified"
}

# ─────────────────────────────────────────────────────────────────────────────
# Generate Daily Briefing
# ─────────────────────────────────────────────────────────────────────────────

function Generate-DailyBriefing {
    Write-Log "INFO" "Generating daily briefing..."
    
    # Count files completed today
    $todayCount = 0
    $todayFiles = @()
    
    if (Test-Path $DoneDir) {
        $todayFiles = Get-ChildItem -Path $DoneDir -Filter "${Date}_*.md" -File -ErrorAction SilentlyContinue
        $todayCount = $todayFiles.Count
    }
    
    # Count files completed yesterday
    $yesterday = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
    $yesterdayCount = 0
    
    if (Test-Path $DoneDir) {
        $yesterdayFiles = Get-ChildItem -Path $DoneDir -Filter "${yesterday}_*.md" -File -ErrorAction SilentlyContinue
        $yesterdayCount = $yesterdayFiles.Count
    }
    
    # Get recent plans (modified in last 24 hours)
    $plansCount = 0
    if (Test-Path $PlansDir) {
        $plansCount = (Get-ChildItem -Path $PlansDir -Filter "*.md" -File | Where-Object {
            $_.LastWriteTime -gt (Get-Date).AddHours(-24)
        }).Count
    }
    
    # Get pending approvals
    $pendingCount = 0
    if (Test-Path $PendingApprovalDir) {
        $pendingCount = (Get-ChildItem -Path $PendingApprovalDir -Filter "*.md" -File -ErrorAction SilentlyContinue).Count
    }
    
    # Get Needs_Action count
    $needsActionCount = 0
    if (Test-Path $NeedsActionDir) {
        $needsActionCount = (Get-ChildItem -Path $NeedsActionDir -Filter "*.md" -File -ErrorAction SilentlyContinue).Count
    }
    
    # Build completed tasks table
    $completedTasks = ""
    if ($todayCount -gt 0) {
        $completedTasks = "| Task | Time | Notes |`n|------|------|-------|`n"
        foreach ($file in $todayFiles) {
            $filename = $file.Name
            $fileTime = $file.LastWriteTime.ToString("HH:mm")
            $completedTasks += "| $filename | $fileTime | Auto-processed |`n"
        }
    } else {
        $completedTasks = "_No tasks completed today yet_"
    }
    
    # Generate briefing content
    $content = @"
# 📅 Daily Briefing: $Date

**Generated:** $Timestamp
**Day:** $DayOfWeek
**Status:** 🟢 Complete

---

## 📊 Today's Summary

| Metric | Value |
|--------|-------|
| **Tasks Completed** | $todayCount |
| **Yesterday's Count** | $yesterdayCount |
| **Active Plans** | $plansCount |
| **Pending Approval** | $pendingCount |
| **Needs Action** | $needsActionCount |

---

## ✅ Completed Today

$completedTasks

---

## 📈 Productivity Analysis

"@
    
    # Add productivity analysis
    if ($todayCount -gt 0) {
        if ($yesterdayCount -gt 0) {
            if ($todayCount -gt $yesterdayCount) {
                $content += "**Trend:** 📈 Up from yesterday ($yesterdayCount → $todayCount)`n"
            } elseif ($todayCount -lt $yesterdayCount) {
                $content += "**Trend:** 📉 Down from yesterday ($yesterdayCount → $todayCount)`n"
            } else {
                $content += "**Trend:** ➡️ Same as yesterday ($todayCount)`n"
            }
        } else {
            $content += "**Trend:** 📊 First day of tracking`n"
        }
    } else {
        $content += "**Trend:** ⏳ No tasks completed yet today`n"
    }
    
    # Add recommendations
    $content += @"

---

## 🎯 Recommendations

"@
    
    if ($needsActionCount -gt 0) {
        $content += "- ⚡ **$needsActionCount task(s)** in Needs_Action - consider processing`n"
    }
    
    if ($pendingCount -gt 0) {
        $content += "- 🎯 **$pendingCount item(s)** awaiting approval in Pending_Approval`n"
    }
    
    if ($todayCount -eq 0) {
        $content += "- 📥 Check Inbox for new tasks to process`n"
    } else {
        $content += "- ✅ Good progress today! Keep it up.`n"
    }
    
    # Add notes section
    $content += @"

---

## 📝 Notes

_Add any additional notes or observations here_

---

## 🔗 Quick Links

- [Dashboard](../Dashboard.md)
- [Inbox](../Inbox/)
- [Needs_Action](../Needs_Action/)
- [Done](../Done/)
- [Pending_Approval](../Pending_Approval/)

---

*Generated by Daily Scheduler • $Timestamp*
"@
    
    # Write briefing file
    Set-Content -Path $LogFile -Value $content -Encoding UTF8
    
    Write-Log "INFO" "Daily briefing created: $LogFile"
    Write-Host "✅ Daily briefing: $LogFile"
}

# ─────────────────────────────────────────────────────────────────────────────
# Cleanup Old Logs (Optional)
# ─────────────────────────────────────────────────────────────────────────────

function Cleanup-OldLogs {
    Write-Log "INFO" "Cleaning up logs older than 30 days..."
    
    # Remove old .log files (30+ days)
    $cutoffDate = (Get-Date).AddDays(-30)
    Get-ChildItem -Path $LogsDir -Filter "*.log" -File | Where-Object {
        $_.LastWriteTime -lt $cutoffDate
    } | Remove-Item -Force
    
    # Remove old .md files (90+ days)
    $cutoffDateMd = (Get-Date).AddDays(-90)
    Get-ChildItem -Path $LogsDir -Filter "*.md" -File | Where-Object {
        $_.LastWriteTime -lt $cutoffDateMd -and $_.Name -like "daily_briefing_*"
    } | Remove-Item -Force
    
    Write-Log "INFO" "Cleanup complete"
}

# ─────────────────────────────────────────────────────────────────────────────
# Send Notification (Optional)
# ─────────────────────────────────────────────────────────────────────────────

function Send-Notification {
    param([string]$Message)
    
    # Windows toast notification (Windows 10+)
    try {
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        
        $template = @"
<toast>
    <visual>
        <binding template="ToastText02">
            <text id="1">AI Employee Daily Briefing</text>
            <text id="2">$Message</text>
        </binding>
    </visual>
</toast>
"@
        
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("AI Employee").Show($toast)
        
        Write-Log "INFO" "Notification sent"
    } catch {
        Write-Log "WARN" "Could not send notification: $_"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Main Execution
# ─────────────────────────────────────────────────────────────────────────────

function Main {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  AI Employee Daily Scheduler" -ForegroundColor Cyan
    Write-Host "  $(Get-Date)" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Log "INFO" "Starting daily scheduler..."
    
    # Ensure directories exist
    Ensure-Directories
    
    # Generate daily briefing
    Generate-DailyBriefing
    
    # Cleanup old logs (optional, uncomment to enable)
    # Cleanup-OldLogs
    
    # Send notification (optional, uncomment to enable)
    # Send-Notification "Daily briefing generated: $todayCount tasks completed"
    
    Write-Log "INFO" "Daily scheduler complete"
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Scheduler Complete" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
}

# Run main function
Main
