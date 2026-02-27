# Email MCP Server

Email capabilities for AI Employee Vault via Gmail API.

## Features

| Capability | Description | Approval Required |
|------------|-------------|-------------------|
| `draft_email` | Create email draft, save to /Plans | ❌ No |
| `send_email` | Send email via Gmail API | ✅ Yes |
| `list_emails` | List recent emails from Gmail | ❌ No |
| `mark_as_read` | Mark email as read | ❌ No |

## Installation

```bash
cd mcp_servers/email-mcp
npm install
```

## Run Server

```bash
# From vault root
node mcp_servers/email-mcp/index.js

# Or from mcp folder
cd mcp_servers/email-mcp
npm start
```

## Test Commands

```bash
# Run full test suite
node mcp_servers/email-mcp/index.js --test

# Test draft creation
node mcp_servers/email-mcp/index.js --draft

# Test send email (requires auth)
node mcp_servers/email-mcp/index.js --send

# List recent emails
node mcp_servers/email-mcp/index.js --list
```

## MCP Inspector (Debug)

```bash
npm install -g @modelcontextprotocol/inspector
npx @modelcontextprotocol/inspector node mcp_servers/email-mcp/index.js
```

## Usage Examples

### Draft an Email

```javascript
// Via MCP client
const result = await mcp.callTool('draft_email', {
  to: 'client@example.com',
  subject: 'Project Proposal',
  body: '<p>Dear Client,</p><p>Attached is our proposal...</p>',
  cc: 'manager@company.com',
  priority: 'P1'
});

// Result: Draft saved to /Plans/email_draft_[date].md
```

### Send an Email (After Approval)

```javascript
// After reviewing and approving draft
const result = await mcp.callTool('send_email', {
  to: 'client@example.com',
  subject: 'Project Proposal',
  body: '<p>Dear Client,</p><p>Attached is our proposal...</p>',
  cc: 'manager@company.com'
});

// Result: Email sent via Gmail
```

### List Recent Emails

```javascript
const result = await mcp.callTool('list_emails', {
  maxResults: 10
});

// Result: List of recent emails with metadata
```

## Workflow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  draft_email │ ──► │  /Plans/     │ ──► │   Human      │
│  (Create)    │     │  (Draft)     │     │   Review     │
└──────────────┘     └──────────────┘     └──────────────┘
                                                  │
                                                  ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    Done/     │ ◄── │  send_email  │ ◄── │  /Approved/  │
│  (Archive)   │     │   (Send)     │     │  (Approved)  │
└──────────────┘     └──────────────┘     └──────────────┘
```

## Draft File Format

Drafts are saved as markdown files in `/Plans/`:

```markdown
---
type: email_draft
to: client@example.com
subject: Project Proposal
created: 2026-02-25T14-30-00
status: draft
priority: P1
requires_approval: true
---

# 📧 Email Draft

## Email Body

<p>Dear Client,</p>
<p>Attached is our proposal...</p>

---

## Approval Checklist

- [ ] Recipient email address verified
- [ ] Subject line is clear and accurate
- [ ] Body content reviewed for tone and accuracy
- [ ] Ready to send
```

## Authentication

1. Ensure `client_secret_*.json` is in vault root
2. First run will require OAuth authorization
3. Token is saved to `token.json` for subsequent runs

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Credentials not found | Check `client_secret_*.json` exists in vault root |
| Authentication failed | Delete `token.json` and re-authenticate |
| Draft not saved | Check `/Plans` folder permissions |
| Send failed | Verify Gmail API scopes include compose |

## Logs

Logs are written to `/Logs/email_mcp_[date].log`

---

*Email MCP Server v1.0.0 • AI Employee Vault*
