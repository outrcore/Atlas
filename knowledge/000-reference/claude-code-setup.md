# Claude Code Setup

## Auth
- **Account:** mythicalsouo@gmail.com
- **Plan:** Claude Max (Opus 4.5)
- **Token location:** `/root/.claude.json` (symlinked to `/workspace/clawd/.claude.json`)

## Usage

### Start Claude Code
```bash
claude-code  # Uses wrapper that unsets ANTHROPIC_API_KEY
```

### If "Invalid API key" Error
1. Run `claude-code` interactively
2. Type `/login`
3. Select option 1 (Claude subscription)
4. Open URL in browser, authorize
5. Paste code back

### Permission Modes
- `--permission-mode acceptEdits` — Auto-approve file edits
- `--permission-mode default` — Ask for everything
- `--dangerously-skip-permissions` — BLOCKED for root user

### Flags
- `--continue` — Resume last conversation
- `--max-turns N` — Limit turns

## Important Notes
- **Interactive mode is reliable**, `-p` flag is flaky
- Wrapper at `/usr/local/bin/claude-code` unsets conflicting env vars
- OAuth tokens expire — need to re-auth periodically
