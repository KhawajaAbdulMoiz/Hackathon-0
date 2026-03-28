# 📘 Facebook/Instagram Watcher & Social Summary Generator

**Gold Tier AI Employee Skills**

Monitor Facebook and Instagram for business opportunities, automatically generate response drafts, and route for human approval.

---

## 📁 File Locations

| File | Path |
|------|------|
| **Watcher Script** | `Watchers/facebook_instagram_watcher.py` |
| **Social Summary Skill** | `skills/social_summary_generator.py` |
| **PM2 Config** | `ecosystem.config.js` |
| **Session Storage** | `Watchers/session/facebook/` |
| **Logs** | `Logs/fb_ig_watcher_[date].log` |
| **Social Summary Logs** | `Logs/social_summary_[date].md` |

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Ensure Playwright is installed
pip install playwright
playwright install chromium

# Install PM2 (Node.js required)
npm install -g pm2
```

### 2. First-Time Login Setup

```bash
# Navigate to vault root
cd E:\Hackathon 0\AI_Employee_Vault

# Run watcher manually first (opens browser for login)
python Watchers\facebook_instagram_watcher.py
```

**Important:** When the browser opens:
1. Login to Facebook
2. Navigate to Messenger
3. Login to Instagram (if needed)
4. Navigate to Instagram Direct
5. The session will be saved automatically

### 3. Start with PM2

```bash
# Start the watcher
pm2 start ecosystem.config.js

# Or start individually
pm2 start Watchers\facebook_instagram_watcher.py --name "fb-ig-watcher" --interpreter python

# View status
pm2 status

# View logs
pm2 logs fb-ig-watcher
```

---

## 📋 How It Works

### Facebook/Instagram Watcher

```
┌─────────────────────────────────────────────────────────────────┐
│                    WATCHER (60-second cycle)                    │
├─────────────────────────────────────────────────────────────────┤
│  1. Check Facebook Messenger for new messages                   │
│  2. Check Instagram Direct for new messages                     │
│  3. Detect keywords: sales, client, project                     │
│  4. Create .md file in /Needs_Action with:                      │
│     - YAML frontmatter (metadata)                               │
│     - Message content                                           │
│     - AI-generated summary                                      │
│  5. Save session cookies for auto-login                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    /Needs_Action/*.md
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              SOCIAL SUMMARY GENERATOR SKILL                     │
├─────────────────────────────────────────────────────────────────┤
│  1. Scan /Needs_Action for social media messages                │
│  2. Generate detailed summary                                   │
│  3. Analyze sentiment (positive/negative/neutral)               │
│  4. Classify lead type (sales/client/project/general)           │
│  5. Draft personalized response                                 │
│  6. Create HITL approval request                                │
│  7. Save to /Plans/ and /Pending_Approval/                      │
└─────────────────────────────────────────────────────────────────┘
```

### Output Files

| Location | Content |
|----------|---------|
| `/Needs_Action/[timestamp]_[platform]_[keywords].md` | Raw message with summary |
| `/Plans/facebook_draft_[platform]_[timestamp].md` | Drafted response |
| `/Pending_Approval/APPROVAL_social_response_[timestamp].md` | HITL approval request |
| `/Logs/fb_ig_watcher_[date].log` | Watcher activity log |
| `/Logs/social_summary_[date].md` | Processing summary log |

---

## 🧪 Testing Guide

### Test 1: Send Facebook Test Message

1. **Send a test message on Facebook:**
   - Go to your Facebook Messenger
   - Send a message to your page (or have someone send it)
   - Include keywords: "sales", "client", or "project"
   
   **Example message:**
   ```
   Hi! I'm interested in your sales services for my upcoming project. 
   Can you provide more information about your offerings?
   ```

2. **Run the watcher manually:**
   ```bash
   python Watchers\facebook_instagram_watcher.py
   ```

3. **Check for new file in Needs_Action:**
   ```bash
   dir Needs_Action\*.md
   ```

4. **Verify the file content:**
   - YAML frontmatter with platform, sender, keywords
   - Message content extracted
   - AI summary generated

### Test 2: Run Social Summary Generator

1. **Process the Facebook message:**
   ```bash
   python skills\social_summary_generator.py
   ```

2. **Check output:**
   - Draft saved to `/Plans/facebook_draft_*.md`
   - Approval request in `/Pending_Approval/APPROVAL_social_response_*.md`

3. **Review the draft:**
   - Check sentiment analysis
   - Review suggested response
   - Verify action items

### Test 3: PM2 Monitoring

1. **Start with PM2:**
   ```bash
   pm2 start ecosystem.config.js
   ```

2. **Monitor:**
   ```bash
   # Watch logs in real-time
   pm2 logs fb-ig-watcher --lines 50
   
   # Check status
   pm2 status
   
   # View detailed info
   pm2 show fb-ig-watcher
   ```

3. **Stop when done:**
   ```bash
   pm2 stop fb-ig-watcher
   ```

---

## ⚙️ Configuration

### Watcher Settings

Edit `Watchers/facebook_instagram_watcher.py`:

```python
# Check interval (default: 60 seconds)
CHECK_INTERVAL: Final[float] = 60.0

# Keywords to detect
KEYWORDS: Final[list[str]] = ["sales", "client", "project"]

# Headless mode (False for first login)
HEADLESS: Final[bool] = False
```

### Response Templates

Edit `skills/social_summary_generator.py`:

```python
RESPONSE_TEMPLATES: Final[dict[str, str]] = {
    "sales": """...""",
    "client": """...""",
    "project": """...""",
    "general": """...""",
}

# Customize company name
DEFAULT_COMPANY: Final[str] = "Our Team"
```

---

## 🔧 Troubleshooting

### Browser Won't Start

```bash
# Reinstall Playwright browsers
playwright install chromium

# Check Python version (3.13+ required)
python --version
```

### Login Issues

```bash
# Clear saved session
rm -rf Watchers/session/facebook/*

# Re-run watcher to login again
python Watchers\facebook_instagram_watcher.py
```

### No Messages Detected

1. Ensure you're logged into Facebook/Instagram
2. Check if messages exist in Messenger/Direct
3. Review logs for errors:
   ```bash
   pm2 logs fb-ig-watcher --lines 100
   ```

### PM2 Errors

```bash
# Restart process
pm2 restart fb-ig-watcher

# Delete and recreate
pm2 delete fb-ig-watcher
pm2 start ecosystem.config.js
```

---

## 📊 Usage Examples

### Run Watcher Continuously

```bash
# Start with PM2
pm2 start Watchers\facebook_instagram_watcher.py --name "fb-ig-watcher" --interpreter python

# Auto-start on system reboot
pm2 startup
pm2 save
```

### Process Messages On-Demand

```bash
# Run social summary generator
python skills\social_summary_generator.py

# Or via Qwen CLI
@Social_Summary_Generator_process_Facebook
```

### View Processing Logs

```bash
# Watcher logs
type Logs\fb_ig_watcher_*.log

# Summary logs
type Logs\social_summary_*.md
```

---

## 🔐 Security Notes

- Session cookies are stored locally in `Watchers/session/facebook/`
- Never commit session files to version control
- Re-authenticate periodically for security
- Use dedicated business accounts when possible

---

## 📈 Success Metrics

| Metric | Target |
|--------|--------|
| Check Interval | Every 60 seconds |
| Keyword Detection | sales, client, project |
| Response Draft Time | < 5 seconds per message |
| HITL Approval | Required before sending |

---

## 🎯 Command Reference

```bash
# ─────────────────────────────────────────────────────────────
# WATCHER COMMANDS
# ─────────────────────────────────────────────────────────────

# Manual run (first time for login)
python Watchers\facebook_instagram_watcher.py

# Start with PM2
pm2 start Watchers\facebook_instagram_watcher.py --name "fb-ig-watcher" --interpreter python

# Or use ecosystem config
pm2 start ecosystem.config.js

# View logs
pm2 logs fb-ig-watcher

# Stop
pm2 stop fb-ig-watcher

# Restart
pm2 restart fb-ig-watcher

# ─────────────────────────────────────────────────────────────
# SKILL COMMANDS
# ─────────────────────────────────────────────────────────────

# Run social summary generator
python skills\social_summary_generator.py

# Qwen CLI command
@Social_Summary_Generator_process_Facebook

# ─────────────────────────────────────────────────────────────
# FILE LOCATIONS
# ─────────────────────────────────────────────────────────────

# Watch for new messages
dir Needs_Action\*_facebook*.md
dir Needs_Action\*_instagram*.md

# Check drafts
dir Plans\facebook_draft_*.md

# Check approval requests
dir Pending_Approval\APPROVAL_social_response_*.md

# View logs
type Logs\fb_ig_watcher_*.log
type Logs\social_summary_*.md
```

---

*Generated for AI Employee Gold Tier • Facebook/Instagram Integration*
