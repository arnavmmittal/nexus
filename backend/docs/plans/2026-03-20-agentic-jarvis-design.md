# Agentic Jarvis System Design

**Date:** 2026-03-20
**Status:** Approved, Implementation In Progress

## Overview

Transform Jarvis from a data-tracking assistant into a fully autonomous agent capable of executing code, researching topics, controlling the system, and providing financial insights.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      JARVIS AGENT                          │
├─────────────────────────────────────────────────────────────┤
│  Voice Interface → Intent Parser → Task Planner            │
│                           ↓                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   CODER     │ │  RESEARCHER │ │   SYSTEM    │           │
│  │  - Shell    │ │  - Web      │ │  - Files    │           │
│  │  - GitHub   │ │  - Explain  │ │  - Apps     │           │
│  │  - Code Gen │ │  - Summarize│ │  - macOS    │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│                                                             │
│  ┌─────────────┐                                           │
│  │  FINANCE    │  ← Read-only (no trading)                 │
│  │  - Robinhood│                                           │
│  │  - Spending │                                           │
│  └─────────────┘                                           │
├─────────────────────────────────────────────────────────────┤
│  Execution Engine: Confirm → Execute → Report              │
│  Cost Tracker: $5/day limit with real-time monitoring      │
│  Security: Sandboxed execution, no credentials in logs     │
└─────────────────────────────────────────────────────────────┘
```

## Design Decisions

1. **Confirmation-first** - Every action shows a plan, waits for approval
2. **Cost-aware** - Tracks API spending, stops at $5/day
3. **Sandboxed execution** - Shell commands run in controlled environment
4. **Modular** - Each capability is a separate module
5. **Self-modifying** - Can modify Nexus codebase itself

## Module 1: Coder

Tools for code execution and GitHub integration.

| Tool | Description | Confirmation |
|------|-------------|--------------|
| `run_shell_command` | Execute terminal commands | Always |
| `write_file` | Create/edit files on disk | Always |
| `read_file` | Read file contents | Auto |
| `create_github_repo` | Create new GitHub repository | Always |
| `git_commit_push` | Stage, commit, and push changes | Always |
| `create_pull_request` | Open a PR on GitHub | Always |
| `install_package` | npm/pip install | Always |

**Safety:**
- Commands run in sandboxed directory
- No sudo without explicit override
- $5/day API cost cap

## Module 2: Researcher

Tools for knowledge and learning.

| Tool | Description | Confirmation |
|------|-------------|--------------|
| `web_search` | Search the web via API | Auto |
| `fetch_webpage` | Read and summarize URL | Auto |
| `explain_concept` | Break down complex topics | Auto |
| `research_topic` | Deep dive with multiple sources | Confirm |
| `summarize_article` | TL;DR any article | Auto |
| `compare_options` | Research and compare choices | Confirm |

**API Options:**
- Tavily ($0.01/search)
- Perplexity API ($0.005/query)

## Module 3: System Control

Tools for macOS automation.

| Tool | Description | Confirmation |
|------|-------------|--------------|
| `open_app` | Launch applications | Auto |
| `open_url` | Open URL in browser | Auto |
| `list_files` | List directory contents | Auto |
| `move_file` | Move/rename files | Confirm |
| `delete_file` | Delete files | Always |
| `create_folder` | Create directories | Confirm |
| `take_screenshot` | Capture screen | Confirm |
| `get_clipboard` | Read clipboard | Auto |
| `set_clipboard` | Copy to clipboard | Auto |
| `run_applescript` | Execute AppleScript | Always |

**Safety:**
- File operations restricted to home directory
- No system folders
- Delete always confirms

## Module 4: Finance (Read-Only)

Tools for portfolio insights without trading.

| Tool | Description | Confirmation |
|------|-------------|--------------|
| `get_portfolio_summary` | Total value, daily change | Auto |
| `get_stock_price` | Current price for ticker | Auto |
| `get_holdings` | List positions with P&L | Auto |
| `get_watchlist` | Watched stocks | Auto |
| `analyze_portfolio` | AI diversification analysis | Confirm |
| `get_spending_insights` | Expense patterns | Auto |
| `compare_to_market` | Performance vs S&P 500 | Auto |

## Module 5: Persistence

- **Conversation History**: Save sessions to database, searchable
- **Auto-Start**: LaunchAgent runs backend on login
- **Health Check**: `/api/health` endpoint for frontend

## Module 6: Cost Tracker

- Track API costs per call
- Dashboard showing daily usage
- Hard stop at $5/day limit
- Alerts at 80% threshold

**Free Actions:**
- All existing database tools
- Open apps, read files
- Cached portfolio data

**Paid Actions:**
- Claude API calls
- Web searches
- Code generation

## Implementation Plan

1. **Coder Module** - `feature/agentic-coder`
2. **Researcher Module** - `feature/agentic-researcher`
3. **System Module** - `feature/agentic-system`
4. **Finance Module** - `feature/agentic-finance`
5. **Persistence** - `feature/agentic-persistence`
6. **Cost Tracker** - `feature/agentic-cost-tracker`
7. **Integration** - Merge all, update AI engine

## Files to Create/Modify

### Backend
- `app/agent/` - New agent modules directory
- `app/agent/coder.py` - Coder tools
- `app/agent/researcher.py` - Research tools
- `app/agent/system.py` - System control tools
- `app/agent/finance.py` - Finance tools
- `app/agent/cost_tracker.py` - Cost tracking
- `app/agent/executor.py` - Confirmation & execution engine
- `app/models/conversation.py` - Conversation history model
- `app/core/autostart.py` - LaunchAgent setup

### Frontend
- `components/jarvis/CostTracker.tsx` - Usage dashboard
- `components/dashboard/` - New dashboard widgets

---

*Approved by: Arnav Mittal*
*Implementation: Parallel agents on feature branches*
