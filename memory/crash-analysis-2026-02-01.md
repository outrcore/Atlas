# Crash Analysis - February 1, 2026

## Summary
Gateway crashed/needed restart 4 times between 07:32 and 07:55 UTC.

## Root Causes Identified

### 1. Excessive Parallel Agent Spawning
**Problem:** I spawned 3 `sessions_spawn` subagents + 6 Claude Code screen sessions simultaneously.

**What happens:**
- Each subagent makes independent API calls to Anthropic
- Combined with main session = 4-10 concurrent API consumers
- Rate limits hit → `Profile anthropic:manual timed out (possible rate limit)`
- Subagent timeout (600s) causes instability

**Evidence:**
```
embedded run timeout: runId=26b13431... sessionId=07f8869c... timeoutMs=600000
Profile anthropic:manual timed out (possible rate limit). Trying next account...
```

### 2. Claude Code Used for Wrong Tasks
**Problem:** Tried to use Claude Code for web research. Claude Code's `-p` flag:
- Can't do web searches (no WebSearch tool)
- Can't write files without explicit permissions
- Times out waiting for permissions

**Evidence:** All Claude Code agents exited saying "need permission" or "need WebSearch"

### 3. web_fetch Failures Cascading
**Problem:** Multiple web_fetch calls to sites that block scrapers (Cloudflare, AllTrails, etc.)
- 403 errors from Cloudflare protection
- 404 errors from wrong URLs
- Each failure logged as ERROR

Not a crash cause, but added noise and wasted tokens on retry logic.

## What Actually Crashed

The Gateway itself didn't crash from OOM or fatal errors. Looking at the restarts:
- **Matt manually restarted** after seeing errors pile up
- **Subagent timeouts** may have caused hangs or unresponsive behavior
- **Rate limiting** caused API calls to fail, making me appear unresponsive

## Fixes Implemented

### Immediate
1. ✅ Killed all wander-* screen sessions
2. ✅ No more parallel agent spawning for research
3. ✅ Fixed Claude Code wrapper (was pointing to wrong path)

### Behavioral Rules (Self-Imposed)

**DO:**
- Use browser tool for web research
- Use web_fetch for simple page grabs
- Do research sequentially in main session
- Use sessions_spawn sparingly (1 at a time max)
- Use Claude Code ONLY for coding tasks

**DON'T:**
- Spawn 3+ agents simultaneously
- Use Claude Code for research
- Use sessions_spawn for tasks that need web access
- Make parallel API-heavy calls

### Monitoring Added
- Check screen sessions regularly
- Monitor for rate limit warnings in logs
- Kill orphaned processes

## Prevention Checklist

Before spawning agents:
1. [ ] Is this a CODING task? → Claude Code OK
2. [ ] Does it need web access? → Don't use subagents, do it myself
3. [ ] Am I spawning more than 1? → Stop, do sequentially
4. [ ] Are there existing subagents running? → Wait for them

## Technical Notes

- Gateway restart count today: 4
- Memory was fine: 23GB/251GB used
- No OOM kills in dmesg
- Rate limit tier: `default_claude_max_20x`
- Subagent timeout: 600000ms (10 min)
