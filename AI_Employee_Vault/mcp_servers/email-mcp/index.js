#!/usr/bin/env node
/**
 * Email MCP Server - Silver Tier
 * 
 * Provides email capabilities via Gmail API for AI Employee system.
 * Supports drafting emails (save as .md) and sending emails (after approval).
 * 
 * Capabilities:
 * - draft_email: Create email draft, save to /Plans/email_draft_[date].md
 * - send_email: Send email via Gmail API (requires approval)
 * - list_emails: List recent emails from Gmail
 * - mark_as_read: Mark email as read
 * 
 * Usage:
 *   node mcp_servers/email-mcp/index.js
 * 
 * Test:
 *   npm install -g @modelcontextprotocol/inspector
 *   npx @modelcontextprotocol/inspector node mcp_servers/email-mcp/index.js
 */

const { Server } = require('@modelcontextprotocol/sdk/server/index.js');
const { StdioServerTransport } = require('@modelcontextprotocol/sdk/server/stdio.js');
const {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
} = require('@modelcontextprotocol/sdk/types.js');
const { readFileSync, writeFileSync, mkdirSync, existsSync } = require('fs');
const { join, dirname } = require('path');
const { authenticate } = require('google-auth-library');
const { gmail } = require('googleapis');

// ─────────────────────────────────────────────────────────────────────────────
// Configuration
// ─────────────────────────────────────────────────────────────────────────────

const VAULT_ROOT = join(dirname(require.main.filename), '..', '..');
const PLANS_DIR = join(VAULT_ROOT, 'Plans');
const LOGS_DIR = join(VAULT_ROOT, 'Logs');
const CREDENTIALS_FILE = join(
  VAULT_ROOT,
  'client_secret_1005799766116-6oj47f92vtmaacrvrfm0dgocjrkv8ukr.apps.googleusercontent.com.json'
);
const TOKEN_FILE = join(VAULT_ROOT, 'token.json');

const SCOPES = ['https://www.googleapis.com/auth/gmail.compose', 'https://www.googleapis.com/auth/gmail.readonly'];

// ─────────────────────────────────────────────────────────────────────────────
// Logging
// ─────────────────────────────────────────────────────────────────────────────

function ensureDirectories() {
  [PLANS_DIR, LOGS_DIR].forEach(dir => {
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }
  });
}

function log(level, message) {
  const timestamp = new Date().toISOString();
  const logLine = `[${timestamp}] [${level}] ${message}\n`;
  console.error(logLine.trim());
  
  // Also write to log file
  const logFile = join(LOGS_DIR, `email_mcp_${new Date().toISOString().split('T')[0]}.log`);
  try {
    ensureDirectories();
    const existing = existsSync(logFile) ? readFileSync(logFile, 'utf-8') : '';
    writeFileSync(logFile, existing + logLine);
  } catch (e) {
    // Ignore log write errors
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Gmail Service
// ─────────────────────────────────────────────────────────────────────────────

class GmailService {
  constructor() {
    this.auth = null;
    this.service = null;
  }

  async authenticate() {
    try {
      log('INFO', 'Authenticating with Gmail API...');
      
      if (!existsSync(CREDENTIALS_FILE)) {
        throw new Error(`Credentials file not found: ${CREDENTIALS_FILE}`);
      }

      const auth = await authenticate({
        keyFile: CREDENTIALS_FILE,
        scopes: SCOPES,
      });

      this.auth = auth;
      this.service = gmail({ version: 'v1', auth });
      
      log('INFO', 'Gmail API authentication successful');
      return true;
    } catch (error) {
      log('ERROR', `Authentication failed: ${error.message}`);
      throw error;
    }
  }

  async createDraft(to, subject, body, cc = '', bcc = '') {
    try {
      log('INFO', `Creating draft email to: ${to}, subject: ${subject}`);

      const message = this._makeMessage(to, subject, body, cc, bcc);
      
      const draft = await this.service.users.drafts.create({
        userId: 'me',
        requestBody: {
          message: {
            raw: message,
          },
        },
      });

      log('INFO', `Draft created with ID: ${draft.data.id}`);
      return {
        success: true,
        draftId: draft.data.id,
        message: 'Draft created successfully',
      };
    } catch (error) {
      log('ERROR', `Failed to create draft: ${error.message}`);
      return {
        success: false,
        error: error.message,
      };
    }
  }

  async sendEmail(to, subject, body, cc = '', bcc = '') {
    try {
      log('INFO', `Sending email to: ${to}, subject: ${subject}`);

      const message = this._makeMessage(to, subject, body, cc, bcc);
      
      const sent = await this.service.users.messages.send({
        userId: 'me',
        requestBody: {
          raw: message,
        },
      });

      log('INFO', `Email sent with ID: ${sent.data.id}`);
      return {
        success: true,
        messageId: sent.data.id,
        message: 'Email sent successfully',
      };
    } catch (error) {
      log('ERROR', `Failed to send email: ${error.message}`);
      return {
        success: false,
        error: error.message,
      };
    }
  }

  async listEmails(maxResults = 10) {
    try {
      log('INFO', `Listing ${maxResults} recent emails`);

      const response = await this.service.users.messages.list({
        userId: 'me',
        maxResults: maxResults,
      });

      const messages = response.data.messages || [];
      const emails = [];

      for (const msg of messages.slice(0, 5)) {
        const fullMessage = await this.service.users.messages.get({
          userId: 'me',
          id: msg.id,
          format: 'metadata',
          metadataHeaders: ['From', 'To', 'Subject', 'Date'],
        });

        const headers = fullMessage.data.payload.headers;
        emails.push({
          id: msg.id,
          from: this._getHeader(headers, 'From'),
          to: this._getHeader(headers, 'To'),
          subject: this._getHeader(headers, 'Subject'),
          date: this._getHeader(headers, 'Date'),
        });
      }

      log('INFO', `Listed ${emails.length} emails`);
      return { success: true, emails };
    } catch (error) {
      log('ERROR', `Failed to list emails: ${error.message}`);
      return { success: false, error: error.message };
    }
  }

  async markAsRead(messageId) {
    try {
      log('INFO', `Marking message ${messageId} as read`);

      await this.service.users.messages.modify({
        userId: 'me',
        id: messageId,
        requestBody: {
          removeLabelIds: ['UNREAD'],
        },
      });

      log('INFO', `Message ${messageId} marked as read`);
      return { success: true, message: 'Message marked as read' };
    } catch (error) {
      log('ERROR', `Failed to mark as read: ${error.message}`);
      return { success: false, error: error.message };
    }
  }

  _makeMessage(to, subject, body, cc, bcc) {
    const str = [
      `To: ${to}`,
      `Cc: ${cc}`,
      `Bcc: ${bcc}`,
      `From: me`,
      `Subject: ${subject}`,
      'MIME-Version: 1.0',
      'Content-Type: text/html; charset=utf-8',
      '',
      body,
    ].join('\n');

    return Buffer.from(str)
      .toString('base64')
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '');
  }

  _getHeader(headers, name) {
    const header = headers.find(h => h.name.toLowerCase() === name.toLowerCase());
    return header ? header.value : '';
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Draft File Manager
// ─────────────────────────────────────────────────────────────────────────────

class DraftFileManager {
  constructor() {
    ensureDirectories();
  }

  saveDraft(to, subject, body, metadata = {}) {
    try {
      const timestamp = new Date();
      const timestampStr = timestamp.toISOString().replace(/[:.]/g, '-').split('T').join('_');
      const subjectSafe = subject.replace(/[^a-zA-Z0-9_-]/g, '_').substring(0, 30);
      const filename = `email_draft_${timestampStr}_${subjectSafe}.md`;
      const filepath = join(PLANS_DIR, filename);

      const content = this._generateDraftContent(to, subject, body, metadata, timestamp);
      writeFileSync(filepath, content, 'utf-8');

      log('INFO', `Draft saved to: ${filepath}`);
      return {
        success: true,
        filepath,
        filename,
      };
    } catch (error) {
      log('ERROR', `Failed to save draft: ${error.message}`);
      return {
        success: false,
        error: error.message,
      };
    }
  }

  _generateDraftContent(to, subject, body, metadata, timestamp) {
    const timestampStr = timestamp.toISOString();
    const status = metadata.status || 'draft';
    const priority = metadata.priority || 'P2';

    return `---
type: email_draft
to: ${to}
subject: ${subject}
created: ${timestampStr}
status: ${status}
priority: ${priority}
requires_approval: true
---

# 📧 Email Draft

**Created:** ${timestamp.toISOString().split('T')[0]} ${timestamp.toISOString().split('T')[1].split('.')[0]}
**To:** ${to}
**Subject:** ${subject}
**Status:** 🟡 Draft - Pending Approval

---

## Email Body

${body}

---

## Approval Checklist

- [ ] Recipient email address verified
- [ ] Subject line is clear and accurate
- [ ] Body content reviewed for tone and accuracy
- [ ] Attachments included (if needed)
- [ ] Ready to send

---

## Send Instructions

To send this email after approval:

1. Move this file to /Approved folder
2. Use the send_email capability with the content from this file
3. Or run: node mcp_servers/email-mcp/index.js --send --file "${join('Plans', filename)}"

---

*Generated by Email MCP Server • ${timestampStr}*
`;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// MCP Server
// ─────────────────────────────────────────────────────────────────────────────

class EmailMCPServer {
  constructor() {
    this.server = null;
    this.gmailService = new GmailService();
    this.draftManager = new DraftFileManager();
    this.initialized = false;
  }

  async initialize() {
    log('INFO', 'Initializing Email MCP Server...');

    // Ensure directories exist
    ensureDirectories();

    // Authenticate with Gmail
    try {
      await this.gmailService.authenticate();
      this.initialized = true;
      log('INFO', 'Email MCP Server initialized successfully');
    } catch (error) {
      log('WARN', `Gmail authentication failed: ${error.message}`);
      log('INFO', 'Server will run in limited mode (drafts only)');
      this.initialized = false;
    }

    this.server = new Server(
      {
        name: 'email-mcp-server',
        version: '1.0.0',
      },
      {
        capabilities: {
          tools: {},
          resources: {},
        },
      }
    );

    this._setupHandlers();

    log('INFO', 'MCP Server handlers configured');
  }

  _setupHandlers() {
    // List Tools
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      log('DEBUG', 'Listing available tools');
      return {
        tools: [
          {
            name: 'draft_email',
            description: 'Create an email draft and save it to /Plans folder. Requires approval before sending.',
            inputSchema: {
              type: 'object',
              properties: {
                to: {
                  type: 'string',
                  description: 'Recipient email address',
                },
                subject: {
                  type: 'string',
                  description: 'Email subject line',
                },
                body: {
                  type: 'string',
                  description: 'Email body content (HTML supported)',
                },
                cc: {
                  type: 'string',
                  description: 'CC recipients (optional)',
                  default: '',
                },
                priority: {
                  type: 'string',
                  description: 'Priority level: P0, P1, P2, P3',
                  default: 'P2',
                },
              },
              required: ['to', 'subject', 'body'],
            },
          },
          {
            name: 'send_email',
            description: 'Send an email via Gmail API. Use only after draft approval.',
            inputSchema: {
              type: 'object',
              properties: {
                to: {
                  type: 'string',
                  description: 'Recipient email address',
                },
                subject: {
                  type: 'string',
                  description: 'Email subject line',
                },
                body: {
                  type: 'string',
                  description: 'Email body content (HTML supported)',
                },
                cc: {
                  type: 'string',
                  description: 'CC recipients (optional)',
                  default: '',
                },
                draftFile: {
                  type: 'string',
                  description: 'Path to approved draft file (optional)',
                },
              },
              required: ['to', 'subject', 'body'],
            },
          },
          {
            name: 'list_emails',
            description: 'List recent emails from Gmail inbox',
            inputSchema: {
              type: 'object',
              properties: {
                maxResults: {
                  type: 'number',
                  description: 'Maximum number of emails to list',
                  default: 10,
                },
              },
            },
          },
          {
            name: 'mark_as_read',
            description: 'Mark an email as read in Gmail',
            inputSchema: {
              type: 'object',
              properties: {
                messageId: {
                  type: 'string',
                  description: 'Gmail message ID to mark as read',
                },
              },
              required: ['messageId'],
            },
          },
        ],
      };
    });

    // Call Tool
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;
      log('INFO', `Tool called: ${name}`);

      try {
        switch (name) {
          case 'draft_email':
            return await this._handleDraftEmail(args);
          case 'send_email':
            return await this._handleSendEmail(args);
          case 'list_emails':
            return await this._handleListEmails(args);
          case 'mark_as_read':
            return await this._handleMarkAsRead(args);
          default:
            return {
              content: [{ type: 'text', text: `Unknown tool: ${name}` }],
              isError: true,
            };
        }
      } catch (error) {
        log('ERROR', `Tool execution error: ${error.message}`);
        return {
          content: [{ type: 'text', text: `Error: ${error.message}` }],
          isError: true,
        };
      }
    });

    // List Resources
    this.server.setRequestHandler(ListResourcesRequestSchema, async () => {
      return {
        resources: [
          {
            uri: 'email://drafts',
            name: 'Email Drafts',
            description: 'List of saved email drafts in /Plans folder',
            mimeType: 'application/json',
          },
        ],
      };
    });

    // Read Resource
    this.server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
      const { uri } = request.params;
      
      if (uri === 'email://drafts') {
        return await this._handleListDrafts();
      }

      return {
        contents: [{ uri, text: 'Resource not found' }],
      };
    });
  }

  async _handleDraftEmail(args) {
    const { to, subject, body, cc = '', priority = 'P2' } = args;

    log('INFO', `Drafting email: to=${to}, subject=${subject}`);

    // Save draft to file
    const fileResult = this.draftManager.saveDraft(to, subject, body, { status: 'draft', priority });

    // Also create Gmail draft if authenticated
    let gmailDraftResult = null;
    if (this.initialized) {
      gmailDraftResult = await this.gmailService.createDraft(to, subject, body, cc);
    }

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              message: 'Email draft created successfully',
              draftFile: fileResult.filename,
              draftPath: fileResult.filepath,
              gmailDraftId: gmailDraftResult?.draftId || null,
              status: 'pending_approval',
              nextStep: 'Review draft in /Plans folder and move to /Approved when ready to send',
            },
            null,
            2
          ),
        },
      ],
    };
  }

  async _handleSendEmail(args) {
    const { to, subject, body, cc = '' } = args;

    log('INFO', `Sending email: to=${to}, subject=${subject}`);

    if (!this.initialized) {
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(
              {
                success: false,
                error: 'Gmail API not authenticated. Check credentials and restart server.',
              },
              null,
              2
            ),
          },
        ],
        isError: true,
      };
    }

    const result = await this.gmailService.sendEmail(to, subject, body, cc);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  }

  async _handleListEmails(args) {
    const { maxResults = 10 } = args;

    if (!this.initialized) {
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(
              {
                success: false,
                error: 'Gmail API not authenticated',
              },
              null,
              2
            ),
          },
        ],
        isError: true,
      };
    }

    const result = await this.gmailService.listEmails(maxResults);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  }

  async _handleMarkAsRead(args) {
    const { messageId } = args;

    if (!this.initialized) {
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(
              {
                success: false,
                error: 'Gmail API not authenticated',
              },
              null,
              2
            ),
          },
        ],
        isError: true,
      };
    }

    const result = await this.gmailService.markAsRead(messageId);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  }

  async _handleListDrafts() {
    try {
      const drafts = [];
      const files = require('fs').readdirSync(PLANS_DIR);
      
      for (const file of files) {
        if (file.startsWith('email_draft_') && file.endsWith('.md')) {
          drafts.push({
            filename: file,
            path: join(PLANS_DIR, file),
          });
        }
      }

      return {
        contents: [
          {
            uri: 'email://drafts',
            mimeType: 'application/json',
            text: JSON.stringify({ drafts }, null, 2),
          },
        ],
      };
    } catch (error) {
      return {
        contents: [
          {
            uri: 'email://drafts',
            mimeType: 'application/json',
            text: JSON.stringify({ error: error.message }, null, 2),
          },
        ],
      };
    }
  }

  async start() {
    log('INFO', 'Starting Email MCP Server...');

    await this.initialize();

    const transport = new StdioServerTransport();
    await this.server.connect(transport);

    log('INFO', 'Email MCP Server running on stdio transport');
    console.error('Email MCP Server ready');
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// CLI Mode (for testing)
// ─────────────────────────────────────────────────────────────────────────────

async function runCLI() {
  const args = process.argv.slice(2);
  
  if (args.includes('--help') || args.includes('-h')) {
    console.log(`
Email MCP Server - CLI Mode

Usage:
  node mcp_servers/email-mcp/index.js              # Run as MCP server
  node mcp_servers/email-mcp/index.js --test       # Run test suite
  node mcp_servers/email-mcp/index.js --draft      # Test draft creation
  node mcp_servers/email-mcp/index.js --send       # Test send (requires approval)

Options:
  --help, -h     Show this help message
  --test         Run full test suite
  --draft        Test draft email creation
  --send         Test send email (requires approved draft)
  --list         List recent emails
`);
    process.exit(0);
  }

  if (args.includes('--test')) {
    await runTests();
    process.exit(0);
  }

  if (args.includes('--draft')) {
    await testDraft();
    process.exit(0);
  }

  if (args.includes('--send')) {
    await testSend();
    process.exit(0);
  }

  if (args.includes('--list')) {
    await testListEmails();
    process.exit(0);
  }

  // Default: Run as MCP server
  const server = new EmailMCPServer();
  await server.start();
}

async function runTests() {
  console.log('\n=== Email MCP Server Test Suite ===\n');
  
  const server = new EmailMCPServer();
  
  console.log('1. Testing initialization...');
  try {
    await server.initialize();
    console.log('   ✅ Initialization: PASSED\n');
  } catch (error) {
    console.log(`   ⚠️  Initialization: LIMITED MODE (${error.message})\n`);
  }

  console.log('2. Testing draft creation...');
  await testDraft();

  console.log('\n=== Test Suite Complete ===\n');
}

async function testDraft() {
  const draftManager = new DraftFileManager();
  const result = draftManager.saveDraft(
    'test@example.com',
    'Test Email Subject',
    '<p>This is a <strong>test email</strong> body.</p>',
    { status: 'draft', priority: 'P2' }
  );

  if (result.success) {
    console.log(`   ✅ Draft created: ${result.filename}`);
    console.log(`   📁 Path: ${result.filepath}`);
  } else {
    console.log(`   ❌ Draft failed: ${result.error}`);
  }
}

async function testSend() {
  const server = new EmailMCPServer();
  await server.initialize();

  if (!server.initialized) {
    console.log('   ⚠️  Cannot test send: Gmail API not authenticated');
    return;
  }

  const result = await server.gmailService.sendEmail(
    'test@example.com',
    'Test Email',
    '<p>This is a test email.</p>'
  );

  if (result.success) {
    console.log(`   ✅ Email sent: ${result.messageId}`);
  } else {
    console.log(`   ❌ Send failed: ${result.error}`);
  }
}

async function testListEmails() {
  const server = new EmailMCPServer();
  await server.initialize();

  if (!server.initialized) {
    console.log('   ⚠️  Cannot list emails: Gmail API not authenticated');
    return;
  }

  const result = await server.gmailService.listEmails(5);

  if (result.success) {
    console.log(`   ✅ Listed ${result.emails.length} emails:`);
    result.emails.forEach((email, i) => {
      console.log(`      ${i + 1}. ${email.subject} (from: ${email.from})`);
    });
  } else {
    console.log(`   ❌ List failed: ${result.error}`);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Entry Point
// ─────────────────────────────────────────────────────────────────────────────

runCLI().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});
