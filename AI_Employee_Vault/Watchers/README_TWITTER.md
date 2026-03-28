# 🐦 Twitter (X) Watcher & Twitter Post Generator

**Gold Tier AI Employee Skills**

Monitor Twitter (X) for DMs, tweets, and notifications with business keywords, automatically generate tweet responses, and route for human approval.

---

## 📁 File Locations

| File | Path |
|------|------|
| **Watcher Script** | `Watchers/twitter_watcher.py` |
| **Twitter Post Generator** | `skills/twitter_post_generator.py` |
| **PM2 Config** | `ecosystem.config.js` |
| **Session Storage** | `Watchers/session/twitter/` |
| **Logs** | `Logs/twitter_watcher_[date].log` |
| **Summary Logs** | `Logs/twitter_post_gen_[date].md` |

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
python Watchers\twitter_watcher.py
```

**Important:** When the browser opens:
1. Login to Twitter (X)
2. Navigate to Messages (DMs)
3. Check Notifications tab
4. The session will be saved automatically

### 3. Start with PM2

```bash
# Start all watchers from config
pm2 start ecosystem.config.js

# Or start Twitter watcher individually
pm2 start Watchers\twitter_watcher.py --name "twitter-watcher" --interpreter python

# View status
pm2 status

# View logs
pm2 logs twitter-watcher
```

---

## 📋 How It Works

### Twitter (X) Watcher

```
┌─────────────────────────────────────────────────────────────────┐
│                  WATCHER (60-second cycle)                      │
├─────────────────────────────────────────────────────────────────┤
│  1. Check Twitter Direct Messages (DMs)                         │
│  2. Check Twitter Notifications (mentions, replies)             │
│  3. Check Home Timeline (tweets with mentions)                  │
│  4. Detect keywords: sales, client, project                     │
│  5. Create .md file in /Needs_Action with:                      │
│     - YAML frontmatter (metadata)                               │
│     - Tweet/DM content                                          │
│     - AI-generated summary                                      │
│  6. Save session cookies for auto-login                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    /Needs_Action/*.md
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              TWITTER POST GENERATOR SKILL                       │
├─────────────────────────────────────────────────────────────────┤
│  1. Scan /Needs_Action for Twitter content                      │
│  2. Generate detailed summary                                   │
│  3. Analyze sentiment (positive/negative/neutral)               │
│  4. Classify lead type (sales/client/project/tweet_reply)       │
│  5. Draft tweet response (under 280 chars)                      │
│  6. Draft DM response (longer format)                           │
│  7. Create HITL approval request                                │
│  8. Save to /Plans/ and /Pending_Approval/                      │
└─────────────────────────────────────────────────────────────────┘
```

### Output Files

| Location | Content |
|----------|---------|
| `/Needs_Action/[timestamp]_twitter_[type]_[keywords].md` | Raw content with summary |
| `/Plans/twitter_draft_[type]_[timestamp].md` | Drafted tweet/DM response |
| `/Pending_Approval/APPROVAL_twitter_response_[timestamp].md` | HITL approval request |
| `/Logs/twitter_watcher_[date].log` | Watcher activity log |
| `/Logs/twitter_post_gen_[date].md` | Processing summary log |

---

## 🧪 Testing Guide

### Test 1: Send Twitter DM Test Message

1. **Send a test DM on Twitter (X):**
   - Go to your Twitter account
   - Open Messages (DMs)
   - Send a message to yourself or have someone send it
   - Include keywords: "sales", "client", or "project"
   
   **Example message:**
   ```
   Hi! I'm interested in your sales services for my upcoming project. 
   Can you provide more information about your offerings?
   ```

2. **Run the watcher manually:**
   ```bash
   python Watchers\twitter_watcher.py
   ```

3. **Check for new file in Needs_Action:**
   ```bash
   dir Needs_Action\*_twitter*.md
   ```

4. **Verify the file content:**
   - YAML frontmatter with platform, sender, keywords
   - Message content extracted
   - AI summary generated

### Test 2: Tweet/Mention Test

1. **Tweet or mention your account:**
   - Post a tweet mentioning your account with keywords
   - Example: "@YourHandle Great sales service for projects!"

2. **Run the watcher:**
   ```bash
   python Watchers\twitter_watcher.py
   ```

3. **Check Needs_Action for the tweet**

### Test 3: Run Twitter Post Generator

1. **Process the Twitter content:**
   ```bash
   python skills\twitter_post_generator.py
   ```

2. **Check output:**
   - Draft saved to `/Plans/twitter_draft_*.md`
   - Approval request in `/Pending_Approval/APPROVAL_twitter_response_*.md`

3. **Review the draft:**
   - Check sentiment analysis
   - Review suggested tweet (under 280 chars)
   - Review suggested DM (longer format)
   - Verify action items

### Test 4: PM2 Monitoring

1. **Start with PM2:**
   ```bash
   pm2 start ecosystem.config.js
   ```

2. **Monitor:**
   ```bash
   # Watch logs in real-time
   pm2 logs twitter-watcher --lines 50
   
   # Check status
   pm2 status
   
   # View detailed info
   pm2 show twitter-watcher
   ```

3. **Stop when done:**
   ```bash
   pm2 stop twitter-watcher
   ```

---

## ⚙️ Configuration

### Watcher Settings

Edit `Watchers/twitter_watcher.py`:

```python
# Check interval (default: 60 seconds)
CHECK_INTERVAL: Final[float] = 60.0

# Keywords to detect
KEYWORDS: Final[list[str]] = ["sales", "client", "project"]

# Headless mode (False for first login)
HEADLESS: Final[bool] = False
```

### Response Templates

Edit `skills/twitter_post_generator.py`:

```python
RESPONSE_TEMPLATES: Final[dict[str, str]] = {
    "sales": """...""",
    "client": """...""",
    "project": """...""",
    "general": """...""",
    "tweet_reply": """...""",
}

# Customize company name
DEFAULT_COMPANY: Final[str] = "Our Team"
DEFAULT_HANDLE: Final[str] = "@yourhandle"
```

### Tweet Character Limit

```python
# Maximum tweet length (Twitter limit)
MAX_TWEET_LENGTH: Final[int] = 280
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
rm -rf Watchers/session/twitter/*

# Re-run watcher to login again
python Watchers\twitter_watcher.py
```

### No Content Detected

1. Ensure you're logged into Twitter
2. Check if DMs/notifications exist
3. Review logs for errors:
   ```bash
   pm2 logs twitter-watcher --lines 100
   ```

### Twitter API Changes

Twitter frequently updates their UI. If selectors break:
1. Check the watcher logs for specific errors
2. Update CSS selectors in `_extract_dms()`, `_extract_notifications()`, `_extract_timeline()`
3. Re-test manually first

### PM2 Errors

```bash
# Restart process
pm2 restart twitter-watcher

# Delete and recreate
pm2 delete twitter-watcher
pm2 start ecosystem.config.js
```

---

## 📊 Usage Examples

### Run Watcher Continuously

```bash
# Start with PM2
pm2 start Watchers\twitter_watcher.py --name "twitter-watcher" --interpreter python

# Auto-start on system reboot
pm2 startup
pm2 save
```

### Process Messages On-Demand

```bash
# Run Twitter post generator
python skills\twitter_post_generator.py

# Or via Qwen CLI
@Twitter_Post_Generator_process_Twitter
```

### View Processing Logs

```bash
# Watcher logs
type Logs\twitter_watcher_*.log

# Summary logs
type Logs\twitter_post_gen_*.md
```

---

## 🔐 Security Notes

- Session cookies are stored locally in `Watchers/session/twitter/`
- Never commit session files to version control
- Re-authenticate periodically for security
- Use dedicated business accounts when possible
- Twitter may detect automation - use responsibly

---

## 📈 Success Metrics

| Metric | Target |
|--------|--------|
| Check Interval | Every 60 seconds |
| Keyword Detection | sales, client, project |
| Tweet Length | Under 280 characters |
| Response Draft Time | < 5 seconds per message |
| HITL Approval | Required before posting |

---

## 🎯 Command Reference

```bash
# ─────────────────────────────────────────────────────────────
# WATCHER COMMANDS
# ─────────────────────────────────────────────────────────────

# Manual run (first time for login)
python Watchers\twitter_watcher.py

# Start with PM2
pm2 start Watchers\twitter_watcher.py --name "twitter-watcher" --interpreter python

# Or use ecosystem config
pm2 start ecosystem.config.js

# View logs
pm2 logs twitter-watcher

# Stop
pm2 stop twitter-watcher

# ─────────────────────────────────────────────────────────────
# SKILL COMMANDS
# ─────────────────────────────────────────────────────────────

# Run Twitter post generator
python skills\twitter_post_generator.py

# Qwen CLI command
@Twitter_Post_Generator_process_Twitter

# ─────────────────────────────────────────────────────────────
# FILE LOCATIONS
# ─────────────────────────────────────────────────────────────

# Watch for new content
dir Needs_Action\*_twitter*.md

# Check drafts
dir Plans\twitter_draft_*.md

# Check approval requests
dir Pending_Approval\APPROVAL_twitter_response_*.md

# View logs
type Logs\twitter_watcher_*.log
type Logs\twitter_post_gen_*.md
```

---

## 📝 Response Templates

### Sales Lead Tweet
```
Hi {sender}! 👋 Thanks for your interest in our sales services!

We'd love to help with {topic}. Our team delivers tailored solutions.

Could you share more about:
• Your requirements
• Timeline
• Budget range

Let's connect! 🚀

#BusinessGrowth #Sales
```

### Client Inquiry Tweet
```
Hello {sender}! 👋

Thanks for reaching out about {topic}! We're here to help.

To better assist you:
• What challenges are you facing?
• What's your ideal outcome?
• Any deadlines?

We're committed to excellence! 💼

#ClientSuccess #Support
```

---

*Generated for AI Employee Gold Tier • Twitter (X) Integration*
