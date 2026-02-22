# OpenClaw Upgrade Guide - ATLAS Customizations

**Created:** 2026-02-06
**Purpose:** Document all ATLAS customizations and provide rollback procedures

---

## Current State

- **Version:** 2026.2.3
- **Location:** `/workspace/Jarvis/`
- **Origin:** `outrcore/Atlas.git` (Matt's fork)
- **Upstream:** `openclaw/openclaw.git`

---

## ATLAS Customizations Inventory

### 1. New Files (1,282 lines total)

These are entirely new files that don't exist in upstream:

| File | Lines | Purpose |
|------|-------|---------|
| `src/agents/pi-embedded-runner/run/auto-memory.ts` | 483 | Sonnet-based memory extraction with dedup |
| `src/agents/pi-embedded-runner/run/auto-rag.ts` | 155 | Auto-inject context from vector search |
| `src/agents/pi-embedded-runner/run/proactive-recall.ts` | 498 | MEMORY.md + entity + temporal search |
| `src/hooks/bundled/brain-logger/handler.ts` | 118 | Log activity to brain system |
| `src/hooks/bundled/brain-logger/HOOK.md` | 28 | Hook documentation |

### 2. Modified Files (Integration Points)

These upstream files have ATLAS code added:

#### `src/agents/pi-embedded-runner/run/attempt.ts`
- **Import additions:** `triggerMemoryExtraction`, `maybeInjectRagContext`, `getProactiveContext`, `shouldRunProactiveRecall`
- **Line ~198:** Auto-RAG injection before agent run
- **Line ~210:** Proactive recall context injection
- **Line ~913:** Fire-and-forget memory extraction after response

#### `src/auto-reply/reply/dispatch-from-config.ts`
- **Lines 1-58:** `logToBrain()` function for user message logging
- **Line ~255:** Call to log user messages to brain activity

#### `src/auto-reply/reply/reply-dispatcher.ts`
- **Lines 1-50:** `logAssistantToBrain()` function for assistant response logging
- **Line ~170:** Call to log assistant responses (final only)
- **Options additions:** `channel`, `sessionKey` for brain logging

#### `src/config/schema.ts`
- **2 lines added:** Field labels for `autoInject` and `autoExtract`

#### `src/config/types.tools.ts`
- **4 lines added:** Type definitions for `autoInject?: boolean` and `autoExtract?: boolean`

#### `src/config/zod-schema.agent-runtime.ts`
- **2 lines added:** Zod schema for `autoInject` and `autoExtract` in MemorySearchSchema

---

## Paths That Must Be Preserved

The brain system writes to these hardcoded paths:

```
/workspace/clawd/brain_data/activity/    # JSONL activity logs
/workspace/clawd/memory/                  # Daily memory files
```

---

## Upgrade Procedure

### Step 1: Create Backup Branch
```bash
cd /workspace/Jarvis
git checkout -b pre-upgrade-backup-$(date +%Y%m%d)
git push origin pre-upgrade-backup-$(date +%Y%m%d)
```

### Step 2: Stash Local Changes (if any uncommitted)
```bash
git stash
```

### Step 3: Fetch Upstream
```bash
git fetch upstream
```

### Step 4: Merge Upstream
```bash
git merge upstream/main
```

### Step 5: Resolve Conflicts
Expected conflicts in:
- `attempt.ts` - Keep BOTH upstream changes AND our memory hooks
- `schema.ts` - Add our 2 lines alongside upstream changes
- Possibly `reply-dispatcher.ts`

For each conflict:
1. Keep upstream's structural changes
2. Re-add our ATLAS imports and function calls
3. Verify brain logging paths are intact

### Step 6: Rebuild
```bash
pnpm install
pnpm build
```

### Step 7: Restart Gateway
```bash
screen -S Jarvis -X quit
screen -dmS Jarvis bash -c "cd /workspace/Jarvis && pnpm openclaw gateway 2>&1"
```

### Step 8: Verify
```bash
# Check version
cat package.json | grep version

# Check gateway is running
screen -ls | grep Jarvis

# Test a message in Telegram
```

---

## Rollback Procedure

### If Build Fails
```bash
cd /workspace/Jarvis
git merge --abort  # If still merging
git checkout pre-upgrade-backup-$(date +%Y%m%d)
pnpm install
pnpm build
# Restart gateway
```

### If Gateway Crashes After Upgrade
```bash
cd /workspace/Jarvis
git log --oneline -5  # Find the bad commit
git revert HEAD       # Or: git reset --hard <commit-before-merge>
pnpm build
# Restart gateway
```

### Nuclear Option (Full Reset)
```bash
cd /workspace/Jarvis
git fetch origin
git reset --hard origin/main  # Reset to Matt's fork (pre-merge state)
pnpm install
pnpm build
# Restart gateway
```

---

## Quick Reference: Key Integration Points

### To Add Memory Extraction
In `attempt.ts`, after response is ready:
```typescript
triggerMemoryExtraction({
  userMessage: params.prompt,
  assistantResponse: assistantTexts.join("\n"),
  cfg: params.config,
  sessionKey: params.sessionKey,
  conversationContext: contextMessages,
});
```

### To Add RAG Injection
In `attempt.ts`, before agent run:
```typescript
let { contextFiles, ragInjected } = await maybeInjectRagContext({
  userMessage: params.prompt,
  cfg: params.config,
  sessionKey: params.sessionKey,
  contextFiles: baseContextFiles,
});
```

### To Add Proactive Recall
In `attempt.ts`, before agent run:
```typescript
if (shouldRunProactiveRecall(params.prompt)) {
  const proactiveContext = await getProactiveContext({
    query: params.prompt,
    cfg: params.config,
    sessionKey: params.sessionKey,
  });
  // Inject as PROACTIVE_RECALL.md
}
```

---

## Config Settings

In `openclaw.json`, under `agents.defaults.memorySearch`:
```json
{
  "memorySearch": {
    "enabled": true,
    "autoInject": true,    // Enable auto-RAG
    "autoExtract": true    // Enable auto-memory extraction
  }
}
```

---

## Contact

If something breaks badly:
1. Check `/workspace/Jarvis/` for git state
2. Check `screen -ls` for running processes
3. Check logs: `screen -r Jarvis` then scroll up
4. Rollback using procedures above

**Backup branch naming:** `pre-upgrade-backup-YYYYMMDD`
