#!/bin/bash
#
# Daily Scheduler - AI Employee Vault (Silver Tier)
#
# Runs daily tasks for AI Employee system:
# - Generate daily summary from /Done files
# - Write briefing to /Logs/daily_briefing_[date].md
# - Clean up old logs (optional)
#
# Usage:
#   ./daily_scheduler.sh
#
# Cron Setup (Linux/Mac):
#   1. Open crontab: crontab -e
#   2. Add line: 0 8 * * * /path/to/daily_scheduler.sh
#   3. Save and exit
#
# Test Manually:
#   bash schedulers/daily_scheduler.sh
#

set -e

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_ROOT="$(dirname "$SCRIPT_DIR")"

DONE_DIR="$VAULT_ROOT/Done"
LOGS_DIR="$VAULT_ROOT/Logs"
PLANS_DIR="$VAULT_ROOT/Plans"

DATE=$(date +"%Y-%m-%d")
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
DAY_OF_WEEK=$(date +"%A")

LOG_FILE="$LOGS_DIR/daily_briefing_${DATE}.md"
EXECUTION_LOG="$LOGS_DIR/scheduler_execution_${DATE}.log"

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] [$level] $message" | tee -a "$EXECUTION_LOG"
}

# ─────────────────────────────────────────────────────────────────────────────
# Ensure Directories
# ─────────────────────────────────────────────────────────────────────────────

ensure_directories() {
    mkdir -p "$DONE_DIR" "$LOGS_DIR" "$PLANS_DIR"
    log "INFO" "Directories verified"
}

# ─────────────────────────────────────────────────────────────────────────────
# Generate Daily Briefing
# ─────────────────────────────────────────────────────────────────────────────

generate_daily_briefing() {
    log "INFO" "Generating daily briefing..."

    # Count files completed today
    local today_count=0
    local today_files=()
    
    if [ -d "$DONE_DIR" ]; then
        while IFS= read -r -d '' file; do
            today_files+=("$file")
            ((today_count++)) || true
        done < <(find "$DONE_DIR" -maxdepth 1 -name "${DATE}_*.md" -print0 2>/dev/null)
    fi

    # Count files completed yesterday (for comparison)
    local yesterday=$(date -d "yesterday" +"%Y-%m-%d" 2>/dev/null || date -v-1d +"%Y-%m-%d" 2>/dev/null || echo "unknown")
    local yesterday_count=0
    
    if [ -d "$DONE_DIR" ] && [ "$yesterday" != "unknown" ]; then
        yesterday_count=$(find "$DONE_DIR" -maxdepth 1 -name "${yesterday}_*.md" 2>/dev/null | wc -l | tr -d ' ')
    fi

    # Get recent plans
    local plans_count=0
    if [ -d "$PLANS_DIR" ]; then
        plans_count=$(find "$PLANS_DIR" -maxdepth 1 -name "*.md" -mtime -1 2>/dev/null | wc -l | tr -d ' ')
    fi

    # Get pending approvals
    local pending_count=0
    if [ -d "$VAULT_ROOT/Pending_Approval" ]; then
        pending_count=$(find "$VAULT_ROOT/Pending_Approval" -maxdepth 1 -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    fi

    # Get Needs_Action count
    local needs_action_count=0
    if [ -d "$VAULT_ROOT/Needs_Action" ]; then
        needs_action_count=$(find "$VAULT_ROOT/Needs_Action" -maxdepth 1 -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    fi

    # Extract today's completed tasks
    local completed_tasks=""
    if [ ${#today_files[@]} -gt 0 ]; then
        completed_tasks="| Task | Time | Notes |\n|------|------|-------|\n"
        for file in "${today_files[@]}"; do
            local filename=$(basename "$file")
            local file_time=$(stat -f "%Sm" -t "%H:%M" "$file" 2>/dev/null || stat -c "%y" "$file" 2>/dev/null | cut -d' ' -f2 | cut -d'.' -f1)
            completed_tasks+="| $filename | $file_time | Auto-processed |\n"
        done
    else
        completed_tasks="_No tasks completed today yet_"
    fi

    # Generate briefing content
    cat > "$LOG_FILE" << EOF
# 📅 Daily Briefing: $DATE

**Generated:** $TIMESTAMP
**Day:** $DAY_OF_WEEK
**Status:** 🟢 Complete

---

## 📊 Today's Summary

| Metric | Value |
|--------|-------|
| **Tasks Completed** | $today_count |
| **Yesterday's Count** | $yesterday_count |
| **Active Plans** | $plans_count |
| **Pending Approval** | $pending_count |
| **Needs Action** | $needs_action_count |

---

## ✅ Completed Today

$(echo -e "$completed_tasks")

---

## 📈 Productivity Analysis

EOF

    # Add productivity analysis
    if [ "$today_count" -gt 0 ]; then
        if [ "$yesterday_count" != "0" ] && [ "$yesterday_count" != "unknown" ]; then
            if [ "$today_count" -gt "$yesterday_count" ]; then
                echo "**Trend:** 📈 Up from yesterday ($yesterday_count → $today_count)" >> "$LOG_FILE"
            elif [ "$today_count" -lt "$yesterday_count" ]; then
                echo "**Trend:** 📉 Down from yesterday ($yesterday_count → $today_count)" >> "$LOG_FILE"
            else
                echo "**Trend:** ➡️ Same as yesterday ($today_count)" >> "$LOG_FILE"
            fi
        else
            echo "**Trend:** 📊 First day of tracking" >> "$LOG_FILE"
        fi
    else
        echo "**Trend:** ⏳ No tasks completed yet today" >> "$LOG_FILE"
    fi

    # Add recommendations
    cat >> "$LOG_FILE" << EOF

---

## 🎯 Recommendations

EOF

    if [ "$needs_action_count" -gt 0 ]; then
        echo "- ⚡ **$needs_action_count task(s)** in Needs_Action - consider processing" >> "$LOG_FILE"
    fi
    
    if [ "$pending_count" -gt 0 ]; then
        echo "- 🎯 **$pending_count item(s)** awaiting approval in Pending_Approval" >> "$LOG_FILE"
    fi
    
    if [ "$today_count" -eq 0 ]; then
        echo "- 📥 Check Inbox for new tasks to process" >> "$LOG_FILE"
    else
        echo "- ✅ Good progress today! Keep it up." >> "$LOG_FILE"
    fi

    # Add sections for notes
    cat >> "$LOG_FILE" << EOF

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

*Generated by Daily Scheduler • $TIMESTAMP*
EOF

    log "INFO" "Daily briefing created: $LOG_FILE"
    echo "✅ Daily briefing: $LOG_FILE"
}

# ─────────────────────────────────────────────────────────────────────────────
# Cleanup Old Logs (Optional)
# ─────────────────────────────────────────────────────────────────────────────

cleanup_old_logs() {
    log "INFO" "Cleaning up logs older than 30 days..."
    
    # Find and remove old log files
    find "$LOGS_DIR" -name "*.log" -mtime +30 -delete 2>/dev/null || true
    find "$LOGS_DIR" -name "*.md" -mtime +90 -delete 2>/dev/null || true
    
    log "INFO" "Cleanup complete"
}

# ─────────────────────────────────────────────────────────────────────────────
# Send Notification (Optional)
# ─────────────────────────────────────────────────────────────────────────────

send_notification() {
    local message="$1"
    
    # macOS notification
    if command -v osascript &> /dev/null; then
        osascript -e "display notification \"$message\" with title \"AI Employee Daily Briefing\"" 2>/dev/null || true
    fi
    
    # Linux notification (if notify-send available)
    if command -v notify-send &> /dev/null; then
        notify-send "AI Employee Daily Briefing" "$message" 2>/dev/null || true
    fi
    
    log "INFO" "Notification sent"
}

# ─────────────────────────────────────────────────────────────────────────────
# Main Execution
# ─────────────────────────────────────────────────────────────────────────────

main() {
    echo ""
    echo "========================================"
    echo "  AI Employee Daily Scheduler"
    echo "  $(date)"
    echo "========================================"
    echo ""
    
    log "INFO" "Starting daily scheduler..."
    
    # Ensure directories exist
    ensure_directories
    
    # Generate daily briefing
    generate_daily_briefing
    
    # Cleanup old logs (optional, uncomment to enable)
    # cleanup_old_logs
    
    # Send notification (optional, uncomment to enable)
    # send_notification "Daily briefing generated: $today_count tasks completed"
    
    log "INFO" "Daily scheduler complete"
    
    echo ""
    echo "========================================"
    echo "  Scheduler Complete"
    echo "========================================"
    echo ""
}

# Run main function
main "$@"
