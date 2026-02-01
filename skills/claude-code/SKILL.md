---
name: claude-code
description: Spawn Claude Code as a sub-agent for autonomous coding tasks - building, fixing, reviewing, and iterating on code projects.
metadata: {"openclaw":{"emoji":"🤖","requires":{"bins":["claude-code"]}}}
---

# Claude Code Integration

Use Claude Code when the user asks to build, create, modify, fix, or work on code projects. Claude Code is an autonomous coding agent that can handle complex multi-file tasks.

## ⚠️ Important: Use the Wrapper

Always use `claude-code` (not `claude`) to avoid ANTHROPIC_API_KEY conflicts:

```bash
claude-code
```

## Authentication

If you see "Invalid API key" or "Missing API key", the OAuth token expired:

1. Run `claude-code` interactively
2. Type `/login`
3. Select option 1 (Claude subscription)
4. User opens URL in browser, authorizes, pastes code back

## Recommended: Interactive Mode

The `-p` flag is unreliable. **Use interactive mode instead:**

```bash
cd /workspace/projects/<name>
claude-code
# Then type your task in the TUI
```

## Quick Reference

| Flag | Purpose |
|------|---------|
| `--continue` | Continue last conversation |
| `--permission-mode acceptEdits` | Auto-accept file edits (still prompts for bash) |
| `--max-turns <n>` | Limit turns (default 50) |

**Note:** `--dangerously-skip-permissions` is blocked when running as root.

## Patterns

### New Project
```bash
mkdir -p /workspace/projects/<name> && cd /workspace/projects/<name> && git init
claude-code
# Type your task when the TUI opens
```

### Continue Previous Work
```bash
cd /workspace/projects/<name>
claude-code --continue
```

## When to Use Claude Code vs Direct Coding

**Use Claude Code when:**
- Building new projects from scratch
- Complex multi-file refactoring
- Tasks that benefit from autonomous iteration
- User explicitly asks to "use Claude Code" or "spawn an agent"

**Code directly when:**
- Simple file edits
- Quick fixes
- User wants to see your work in real-time
- Tasks requiring conversation/clarification

## Project Directory

All projects go in `/workspace/projects/`:
```
/workspace/projects/
├── pomodoro/          # Example: terminal pomodoro timer
├── trading-bot/
└── my-api/
```

## Reporting Results

After Claude Code completes:
1. Summarize what was built/changed
2. List key files created
3. Provide any setup/run instructions
4. Mention if there were issues or TODOs
