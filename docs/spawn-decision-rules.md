# Spawn Decision Rules

When to spawn sub-agents vs handle tasks directly. Internalize these rules.

---

## Decision Flowchart

```
                    ┌─────────────────────┐
                    │   New Task Arrives  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Needs conversation  │
                    │ context/history?    │
                    └──────────┬──────────┘
                          YES/ \NO
                            /   \
               ┌───────────┘     └───────────┐
               ▼                             ▼
        ┌─────────────┐            ┌─────────────────┐
        │ DO DIRECTLY │            │ Estimated time  │
        │ (can't pass │            │    > 5 min?     │
        │  context)   │            └────────┬────────┘
        └─────────────┘                YES/ \NO
                                        /   \
                           ┌───────────┘     └───────────┐
                           ▼                             ▼
                    ┌─────────────┐            ┌─────────────────┐
                    │   SPAWN     │            │ Has 3+ independent│
                    │ (long task) │            │     parts?      │
                    └─────────────┘            └────────┬────────┘
                                                  YES/ \NO
                                                    /   \
                                       ┌───────────┘     └───────────┐
                                       ▼                             ▼
                                ┌─────────────┐            ┌─────────────────┐
                                │   SPAWN     │            │ Confidence      │
                                │  PARALLEL   │            │   < 0.7?        │
                                │ (3+ agents) │            └────────┬────────┘
                                └─────────────┘                YES/ \NO
                                                                /   \
                                                   ┌───────────┘     └───────────┐
                                                   ▼                             ▼
                                            ┌─────────────┐            ┌─────────────┐
                                            │   SPAWN     │            │ DO DIRECTLY │
                                            │ SPECIALIST  │            │ (not worth  │
                                            │ (to verify) │            │  overhead)  │
                                            └─────────────┘            └─────────────┘
```

---

## Decision Matrix

| Condition | Action | Rationale |
|-----------|--------|-----------|
| **Task > 5 min** | Spawn | Frees main context for user interaction |
| **3+ independent parts** | Spawn parallel | Linear → parallel speedup |
| **Needs user context** | Direct | Conversation history can't be passed |
| **Confidence < 0.7** | Spawn specialist | Second opinion, fresh perspective |
| **Simple lookup (< 2 min)** | Direct | Spawn overhead exceeds task time |
| **Sequential dependencies** | Direct or single spawn | Can't parallelize anyway |
| **User waiting for quick answer** | Direct | Latency matters |
| **Research/exploration** | Spawn | Time-consuming, independent |
| **Code generation** | Spawn (usually) | Focused context = better code |
| **Code review** | Either | See examples below |

---

## Quick Decision Rules

**Always Spawn:**
- Research tasks ("find out about X")
- File creation with > 100 lines
- Multi-file refactors
- Generating documentation
- Tasks you'd estimate > 5 minutes

**Never Spawn:**
- "What did I just say?"
- "Remind me about X from earlier"
- Quick file reads
- Simple questions answerable in < 30 seconds
- Tasks requiring real-time back-and-forth

**Spawn Parallel (3+ agents):**
- "Build X, Y, and Z" (independent features)
- "Research A, B, and C" (independent topics)
- "Review these 3 files" (independent reviews)
- "Create tests for modules X, Y, Z"

---

## Examples

### Spawn Examples

| Request | Action | Why |
|---------|--------|-----|
| "Research best practices for X" | Spawn 1 | Takes time, independent |
| "Build feature X, Y, and Z" | Spawn 3 parallel | Independent parts |
| "Write comprehensive docs for this module" | Spawn 1 | Long task |
| "Refactor auth system" | Spawn 1 | Focused, complex |
| "Find and fix all TODO comments" | Spawn 1 | Exploration + edits |

### Direct Examples

| Request | Action | Why |
|---------|--------|-----|
| "What was that URL I mentioned?" | Direct | Needs conversation context |
| "Read this file and summarize" | Direct | Quick, simple |
| "What time is my meeting?" | Direct | API call, < 30 sec |
| "Explain this error message" | Direct | Quick analysis |
| "Add this one line to config" | Direct | Trivial edit |

### Gray Areas

| Request | Guidance |
|---------|----------|
| "Review this code" | **< 200 lines:** Direct. **> 200 lines:** Spawn. **Security-critical:** Spawn specialist. |
| "Help me debug this" | **Direct first** (needs context). Spawn if becomes deep investigation. |
| "Write a function to do X" | **< 50 lines:** Direct. **Complex logic:** Spawn for focused work. |
| "Update the README" | **Minor update:** Direct. **Full rewrite:** Spawn. |

---

## Anti-Patterns

### ❌ Don't Do These

1. **Spawning for < 2 min tasks**
   - Spawn overhead (~10-30 sec) makes this inefficient
   - User perceives delay for no benefit

2. **Spawning with dependencies between subtasks**
   ```
   Bad:  Spawn A (creates file) + Spawn B (edits that file)
   Good: Spawn A, wait, then Spawn B
   Better: Single spawn does both
   ```

3. **More than 5 simultaneous agents**
   - Rate limits will throttle you
   - Context switching overhead
   - Hard to track all results

4. **Spawning when user is waiting for quick answer**
   - "What's 2+2?" → Just answer
   - Spawning feels like stalling

5. **Passing insufficient context to spawn**
   - If spawn needs to ask clarifying questions, you did it wrong
   - Include all relevant info in spawn instructions

6. **Spawning for tasks requiring iterative feedback**
   - User: "Make this better" → needs back-and-forth
   - Keep direct, iterate with user

---

## Spawn Checklist

Before spawning, verify:

- [ ] Task is well-defined (spawn won't need clarification)
- [ ] Task is independent (doesn't need conversation history)
- [ ] Task will take > 2 minutes
- [ ] You've included all necessary context
- [ ] You're not already at 5 active spawns
- [ ] User isn't expecting immediate response

---

## Integration Notes

- **Reference from:** `AGENTS.md` (add link in relevant section)
- **Internalize:** Don't check this doc every time—learn the patterns
- **Update:** When you discover new patterns, add them here

### Adding to AGENTS.md

Add under a "## Sub-Agents" section:
```markdown
## Sub-Agents

See [Spawn Decision Rules](docs/spawn-decision-rules.md) for when to spawn vs handle directly.

Quick rule: Spawn for tasks > 5 min or with 3+ independent parts. Direct for anything needing conversation context.
```

---

## Spawn Command Reference

```
# Basic spawn
Spawn a sub-agent with clear task description

# Parallel spawns
Spawn multiple agents for independent tasks simultaneously

# Specialist spawn (low confidence)
Spawn with explicit "verify" or "second opinion" framing
```

---

*Last updated: Document creation*
*Maintainer: ATLAS*
