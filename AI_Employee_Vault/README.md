# AI Employee Vault

A local-first, file-based knowledge management system for autonomous AI employees powered by Qwen CLI.

## Purpose

This vault serves as the central nervous system for an AI employee, providing a structured workflow for task management, knowledge storage, and activity logging. All data is stored locally in plain text formats for maximum portability, version control compatibility, and long-term accessibility.

---

## Folder Structure

```
AI_Employee_Vault/
├── Inbox/           # Raw incoming tasks and unprocessed information
├── Needs_Action/    # Tasks requiring immediate attention or work
├── Plans/           # Strategic plans, roadmaps, and project specifications
├── Done/            # Completed tasks and archived work
├── Logs/            # Activity logs, session records, and audit trails
├── Watchers/        # Automated monitoring scripts and trigger configurations
├── Dashboard.md     # Central hub for status overview and quick navigation
├── Company_Handbook.md  # Organizational knowledge and operating procedures
└── System_Prompt.md     # AI behavioral configuration and response guidelines
```

---

## Folder Descriptions

### 📥 Inbox
**Purpose:** Capture all incoming tasks, requests, and information that need processing.

- Temporary holding area for new items
- Items should be processed and moved to appropriate folders within 24 hours
- Examples: new task requests, incoming emails, meeting notes, raw data

### ⚡ Needs_Action
**Purpose:** Active tasks requiring immediate attention or ongoing work.

- Current priorities and work-in-progress items
- Tasks with approaching deadlines
- Items blocked and waiting on external dependencies
- Review this folder at the start of each work session

### 📋 Plans
**Purpose:** Strategic documentation, project plans, and long-term objectives.

- Project specifications and requirements
- Roadmaps and timelines
- Process documentation and SOPs
- Reference materials for ongoing initiatives

### ✅ Done
**Purpose:** Archive of completed work for reference and accountability.

- Completed tasks with final deliverables
- Project post-mortems and retrospectives
- Achievements and milestone records
- Organized by date or project for easy retrieval

### 📜 Logs
**Purpose:** Chronological records of AI employee activities and decisions.

- Daily session logs
- Decision rationale documentation
- Time tracking and productivity metrics
- Error logs and incident reports
- Audit trail for compliance

### 👁️ Watchers
**Purpose:** Automated monitoring configurations and trigger definitions.

- File system watchers for incoming changes
- Scheduled task configurations
- Alert thresholds and notification rules
- Integration hooks for external systems

---

## Workflow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Inbox     │ ──► │ Needs_Action │ ──► │    Plans    │
│  (Capture)  │     │   (Process)  │     │  (Execute)  │
└─────────────┘     └──────────────┘     └─────────────┘
                                              │
                                              ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Logs      │ ◄── │    Done      │ ◄── │  (Complete) │
│  (Record)   │     │  (Archive)   │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
```

---

## Usage Guidelines

1. **Process Inbox Daily**: Move items from Inbox to appropriate folders
2. **Log All Activities**: Record significant actions in Logs
3. **Archive Completed Work**: Move finished tasks to Done with summary
4. **Review Watchers**: Ensure monitoring configurations are current
5. **Update Dashboard**: Keep status indicators current

---

## File Conventions

- **Markdown (.md)**: All documentation and task files
- **Naming**: `YYYY-MM-DD_description.md` for dated entries
- **Tags**: Use `#tag` syntax for categorization
- **Status**: Include status badges `[ ] Todo` / `[~] In Progress` / `[x] Done`

---

## Version Control

This vault is designed to work with Git or other version control systems:
- Commit logs regularly for audit trails
- Use branches for experimental workflows
- Tag releases for milestone tracking

---

*Built for Qwen CLI • Local-First • Plain Text*
