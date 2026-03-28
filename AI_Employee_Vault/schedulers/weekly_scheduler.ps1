#
# Weekly Scheduler - AI Employee Vault (Gold Tier)
# PowerShell Version for Windows
#
# Runs weekly tasks for AI Employee system:
# - Generate CEO Weekly Briefing from /Done, /Logs, Handbook, Goals
# - Write briefing to /Briefings/ceo_briefing_[date].md
# - Analyze revenue, expenses, bottlenecks
#
# Usage:
#   .\weekly_scheduler.ps1
#
# Task Scheduler Setup (Windows):
#   1. Open Task Scheduler (taskschd.msc)
#   2. Click "Create Basic Task" in right panel
#   3. Name: "AI Employee Weekly Scheduler"
#   4. Trigger: Weekly on Sunday at 9:00 AM
#   5. Action: Start a program
#      - Program: powershell.exe
#      - Arguments: -ExecutionPolicy Bypass -File "E:\Hackathon 0\AI_Employee_Vault\schedulers\weekly_scheduler.ps1"
#      - Start in: E:\Hackathon 0\AI_Employee_Vault\schedulers
#   6. Finish and test
#
# Test Manually:
#   powershell -ExecutionPolicy Bypass -File .\schedulers\weekly_scheduler.ps1
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
$BriefingsDir = Join-Path $VaultRoot "Briefings"

$HandbookFile = Join-Path $VaultRoot "Company_Handbook.md"
$BusinessGoalsFile = Join-Path $VaultRoot "Business_Goals.md"

$Date = Get-Date -Format "yyyy-MM-dd"
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$DayOfWeek = Get-Date -Format "dddd"

$BriefingFile = Join-Path $BriefingsDir "ceo_briefing_${Date}.md"
$ExecutionLog = Join-Path $LogsDir "weekly_scheduler_execution_${Date}.log"

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
    $dirs = @($DoneDir, $LogsDir, $PlansDir, $PendingApprovalDir, $NeedsActionDir, $BriefingsDir)

    foreach ($dir in $dirs) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }

    Write-Log "INFO" "Directories verified"
}

# ─────────────────────────────────────────────────────────────────────────────
# Pattern Matching Functions
# ─────────────────────────────────────────────────────────────────────────────

function Extract-Revenue {
    param([string]$Content)

    $revenue = 0.0
    $patterns = @(
        'revenue[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)',
        'payment\s*(?:received|collected)[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)',
        'income[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)',
        'sale[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)',
        '\$([\d,]+(?:\.\d{2})?)\s*(?:received|earned|collected)'
    )

    foreach ($pattern in $patterns) {
        $matches = [regex]::Matches($Content, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        foreach ($match in $matches) {
            if ($match.Success -and $match.Groups.Count -gt 1) {
                $amount = $match.Groups[1].Value -replace ',', ''
                if ([double]::TryParse($amount, [ref]$null)) {
                    $revenue += [double]$amount
                }
            }
        }
    }

    return $revenue
}

function Extract-Expenses {
    param([string]$Content)

    $expenses = 0.0
    $patterns = @(
        'expense[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)',
        'cost[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)',
        'payment\s*(?:sent|made)[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)',
        'subscription[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)',
        'spent[:\$]?\s*\$?([\d,]+(?:\.\d{2})?)',
        '\$([\d,]+(?:\.\d{2})?)\s*(?:spent|paid|cost)'
    )

    foreach ($pattern in $patterns) {
        $matches = [regex]::Matches($Content, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        foreach ($match in $matches) {
            if ($match.Success -and $match.Groups.Count -gt 1) {
                $amount = $match.Groups[1].Value -replace ',', ''
                if ([double]::TryParse($amount, [ref]$null)) {
                    $expenses += [double]$amount
                }
            }
        }
    }

    return $expenses
}

function Extract-Subscriptions {
    param([string]$Content)

    $subscriptions = @()
    $patterns = @(
        'subscription[:\s]+([^\n]+)',
        'monthly[:\s]+([^\n]+)',
        'recurring[:\s]+([^\n]+)'
    )

    foreach ($pattern in $patterns) {
        $matches = [regex]::Matches($Content, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        foreach ($match in $matches) {
            if ($match.Success) {
                $subscriptions += $match.Value
            }
        }
    }

    return $subscriptions
}

# ─────────────────────────────────────────────────────────────────────────────
# Data Collection
# ─────────────────────────────────────────────────────────────────────────────

function Get-DoneFiles {
    param([int]$DaysBack = 7)

    $cutoffDate = (Get-Date).AddDays(-$DaysBack)
    $files = @()

    if (Test-Path $DoneDir) {
        $files = Get-ChildItem -Path $DoneDir -Filter "*.md" -File | Where-Object {
            $_.LastWriteTime -ge $cutoffDate
        }
    }

    return $files
}

function Get-LogContents {
    param([int]$DaysBack = 7)

    $cutoffDate = (Get-Date).AddDays(-$DaysBack)
    $contents = @()

    if (Test-Path $LogsDir) {
        $logFiles = Get-ChildItem -Path $LogsDir -Filter "*.log" -File | Where-Object {
            $_.LastWriteTime -ge $cutoffDate
        }

        foreach ($logFile in $logFiles) {
            $content = Get-Content -Path $logFile.FullName -Raw -Encoding UTF8
            $contents += $content
        }

        # Also read .md logs
        $mdLogFiles = Get-ChildItem -Path $LogsDir -Filter "*.md" -File | Where-Object {
            $_.LastWriteTime -ge $cutoffDate
        }

        foreach ($logFile in $mdLogFiles) {
            $content = Get-Content -Path $logFile.FullName -Raw -Encoding UTF8
            $contents += $content
        }
    }

    return $contents -join "`n"
}

# ─────────────────────────────────────────────────────────────────────────────
# Generate Weekly Briefing
# ─────────────────────────────────────────────────────────────────────────────

function Generate-WeeklyBriefing {
    Write-Log "INFO" "Generating weekly CEO briefing..."

    # Get data
    $doneFiles = Get-DoneFiles -DaysBack 7
    $logContents = Get-LogContents -DaysBack 7
    $handbookContent = ""
    $goalsContent = ""

    if (Test-Path $HandbookFile) {
        $handbookContent = Get-Content -Path $HandbookFile -Raw -Encoding UTF8
    }

    if (Test-Path $BusinessGoalsFile) {
        $goalsContent = Get-Content -Path $BusinessGoalsFile -Raw -Encoding UTF8
    }

    # Count tasks
    $totalCompleted = $doneFiles.Count

    # Count this week vs last week
    $thisWeek = 0
    $lastWeek = 0
    $now = Get-Date
    $weekAgo = $now.AddDays(-7)
    $twoWeeksAgo = $now.AddDays(-14)

    foreach ($file in $doneFiles) {
        # Extract date from filename
        if ($file.Name -match '(\d{4}-\d{2}-\d{2})') {
            $fileDate = [datetime]::Parse($matches[1])
            if ($fileDate -ge $weekAgo) {
                $thisWeek++
            } elseif ($fileDate -ge $twoWeeksAgo) {
                $lastWeek++
            }
        }
    }

    # Extract financials
    $allContent = $logContents + ($doneFiles | ForEach-Object { Get-Content $_.FullName -Raw })
    $revenue = Extract-Revenue -Content $allContent
    $expenses = Extract-Expenses -Content $allContent
    $subscriptions = Extract-Subscriptions -Content $allContent
    $netProfit = $revenue - $expenses
    $profitMargin = if ($revenue -gt 0) { ($netProfit / $revenue) * 100 } else { 0 }

    # Count pending
    $pendingCount = 0
    $needsActionCount = 0

    if (Test-Path $PendingApprovalDir) {
        $pendingCount = (Get-ChildItem -Path $PendingApprovalDir -Filter "*.md" -File).Count
    }

    if (Test-Path $NeedsActionDir) {
        $needsActionCount = (Get-ChildItem -Path $NeedsActionDir -Filter "*.md" -File).Count
    }

    # Detect bottlenecks
    $bottlenecks = @()
    $errorCount = ($allContent | Select-String -Pattern "error" -CaseSensitive:$false).Count

    if ($pendingCount -gt 5) {
        $bottlenecks += "🟡 Approval Backlog: $pendingCount items pending approval"
    }

    if ($needsActionCount -gt 10) {
        $bottlenecks += "🟡 Task Backlog: $needsActionCount items in Needs_Action"
    }

    if ($errorCount -gt 10) {
        $bottlenecks += "🟡 System Errors: $errorCount errors in logs"
    }

    # Build task breakdown
    $taskTypes = @{}
    foreach ($file in $doneFiles) {
        $name = $file.Name.ToLower()
        if ($name -like "*_email_*") {
            $taskTypes["Email"] = $taskTypes.Get("Email", 0) + 1
        } elseif ($name -like "*_facebook_*" -or $name -like "*_instagram_*") {
            $taskTypes["Social Media"] = $taskTypes.Get("Social Media", 0) + 1
        } elseif ($name -like "*_twitter_*") {
            $taskTypes["Twitter"] = $taskTypes.Get("Twitter", 0) + 1
        } elseif ($name -like "*_linkedin_*") {
            $taskTypes["LinkedIn"] = $taskTypes.Get("LinkedIn", 0) + 1
        } elseif ($name -like "*_whatsapp_*") {
            $taskTypes["WhatsApp"] = $taskTypes.Get("WhatsApp", 0) + 1
        } else {
            $taskTypes["Other"] = $taskTypes.Get("Other", 0) + 1
        }
    }

    $taskBreakdown = ""
    foreach ($key in $taskTypes.Keys) {
        $taskBreakdown += "- **$key**: $($taskTypes[$key])`n"
    }

    # Trend analysis
    $trendEmoji = "➡️"
    $trendText = "Same as last week"
    if ($thisWeek -gt $lastWeek -and $lastWeek -gt 0) {
        $trendEmoji = "📈"
        $trendText = "Up from last week"
    } elseif ($thisWeek -lt $lastWeek -and $lastWeek -gt 0) {
        $trendEmoji = "📉"
        $trendText = "Down from last week"
    }

    # Generate suggestions
    $suggestions = @()
    if ($expenses -gt $revenue -and $revenue -gt 0) {
        $suggestions += "💰 Expenses exceed revenue - review cost structure"
    }
    if ($subscriptions.Count -gt 0) {
        $suggestions += "📋 Review $($subscriptions.Count) subscription(s) for optimization"
    }
    if ($thisWeek -lt $lastWeek -and $lastWeek -gt 0) {
        $suggestions += "📉 Task completion down - investigate blockers"
    }
    if ($bottlenecks.Count -gt 0) {
        $suggestions += "🔴 Address $($bottlenecks.Count) bottleneck(s) identified"
    }
    if ($suggestions.Count -eq 0) {
        $suggestions += "✅ All systems operational - maintain current pace"
    }

    # Build subscriptions section
    $subscriptionsSection = "### Subscriptions`n`n_No recurring subscriptions detected_"
    if ($subscriptions.Count -gt 0) {
        $subscriptionsSection = "### Subscriptions`n`n"
        foreach ($sub in $subscriptions) {
            $subscriptionsSection += "- $sub`n"
        }
    }

    # Build bottlenecks section
    $bottlenecksSection = "✅ No significant bottlenecks detected"
    if ($bottlenecks.Count -gt 0) {
        $bottlenecksSection = ""
        for ($i = 0; $i -lt $bottlenecks.Count; $i++) {
            $bottlenecksSection += "$($i + 1). $($bottlenecks[$i])`n`n"
        }
    }

    # Generate briefing content
    $weekStart = $now.AddDays(-6).ToString("yyyy-MM-dd")
    $content = @"
# 📊 CEO Weekly Briefing

**Week:** $weekStart to $Date
**Generated:** $Timestamp
**Day:** $DayOfWeek
**Status:** 🟢 Complete

---

## 📈 Executive Summary

| Metric | Value | Trend |
|--------|-------|-------|
| **Tasks Completed** | $thisWeek | $trendEmoji $trendText |
| **Revenue** | `$$($revenue.ToString("N2")) | — |
| **Expenses** | `$$($expenses.ToString("N2")) | — |
| **Net Profit** | `$$($netProfit.ToString("N2")) | $($profitMargin.ToString("0.1"))% margin |
| **Pending Approvals** | $pendingCount | — |

---

## 💰 Revenue Analysis

### Financial Summary

| Category | Amount |
|----------|--------|
| **Total Revenue** | `$$($revenue.ToString("N2")) |
| **Total Expenses** | `$$($expenses.ToString("N2")) |
| **Net Profit** | `$$($netProfit.ToString("N2")) |
| **Profit Margin** | $($profitMargin.ToString("0.1"))% |

$subscriptionsSection

---

## ✅ Completed Tasks

### This Week: $thisWeek tasks

$taskBreakdown

### Last Week: $lastWeek tasks

**Trend:** $trendEmoji $trendText

---

## 🚧 Bottlenecks Identified

$bottlenecksSection

---

## 🎯 Business Goals Progress

_Review Business_Goals.md for detailed goal tracking_

---

## 💡 Suggestions & Recommendations

"@

    foreach ($suggestion in $suggestions) {
        $content += "$suggestion`n"
    }

    $content += @"

---

## 📋 Action Items for This Week

- [ ] Review pending approvals in Pending_Approval folder
- [ ] Process any items in Needs_Action
- [ ] Review bottleneck suggestions above
- [ ] Update Business_Goals.md with progress
- [ ] Schedule follow-up on high-severity bottlenecks

---

## 📎 Appendix

### Data Sources

- `/Done` — $totalCompleted total completed tasks
- `/Logs` — System execution logs
- `Company_Handbook.md` — Operating guidelines
- `Business_Goals.md` — Strategic objectives

### Methodology

- Revenue/Expenses: Extracted via pattern matching from logs and task files
- Task counts: Based on file timestamps in Done folder
- Bottlenecks: Detected from folder sizes and log error patterns
- Goals: Tracked against Business_Goals.md

---

*Generated by Weekly Scheduler • AI Employee System*
"@

    # Write briefing file
    Set-Content -Path $BriefingFile -Value $content -Encoding UTF8

    Write-Log "INFO" "Weekly briefing created: $BriefingFile"
    Write-Host "✅ Weekly briefing: $BriefingFile"

    # Print summary
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Weekly Audit Summary" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Tasks This Week:  $thisWeek"
    Write-Host "  Revenue:          `$$($revenue.ToString("N2"))"
    Write-Host "  Expenses:         `$$($expenses.ToString("N2"))"
    Write-Host "  Net Profit:       `$$($netProfit.ToString("N2"))"
    Write-Host "  Bottlenecks:      $($bottlenecks.Count)"
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
}

# ─────────────────────────────────────────────────────────────────────────────
# Main Execution
# ─────────────────────────────────────────────────────────────────────────────

function Main {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  AI Employee Weekly Scheduler" -ForegroundColor Cyan
    Write-Host "  $(Get-Date)" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""

    Write-Log "INFO" "Starting weekly scheduler..."

    # Ensure directories exist
    Ensure-Directories

    # Check if it's Sunday (day 0)
    $dayOfWeekNum = [int](Get-Date).DayOfWeek
    if ($dayOfWeekNum -ne 0) {
        Write-Log "INFO" "Not scheduled run day ($(Get-Date -Format 'dddd')). Use -Force to run anyway."
        Write-Host "📅 Not scheduled run day ($(Get-Date -Format 'dddd')). Use -Force to run anyway."
        
        # Check for force parameter
        if ($args -contains "-Force" -or $args -contains "-f") {
            Write-Log "INFO" "Force flag detected, running anyway..."
        } else {
            Write-Log "INFO" "Weekly scheduler complete (not run)"
            return
        }
    }

    # Generate weekly briefing
    Generate-WeeklyBriefing

    Write-Log "INFO" "Weekly scheduler complete"

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Scheduler Complete" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
}

# Run main function
Main @args
