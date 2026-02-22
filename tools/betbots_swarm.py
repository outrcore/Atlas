#!/usr/bin/env python3
"""
ProjectBeta Swarm - Improved parallel task execution with context and validation.
"""

import json
import re
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from fireworks_orchestrator import FireworksOrchestrator

# ProjectBeta codebase context
CODEBASE_CONTEXT = """
## ProjectBeta Codebase Context

**Stack:**
- Backend: Express.js + better-sqlite3 (SYNCHRONOUS, not async)
- Frontend: React + TypeScript + Tailwind CSS
- Database: SQLite (NOT MongoDB)

**Database patterns (IMPORTANT - use these exactly):**
```javascript
// Query pattern - SYNCHRONOUS
const results = db.prepare('SELECT * FROM table WHERE id = ?').all(id);
const single = db.prepare('SELECT * FROM table WHERE id = ?').get(id);
db.prepare('INSERT INTO table (col) VALUES (?)').run(value);
```

**Tables:** bots, markets, positions, transactions
- bots: id mod name, balance, verified, webhook_url, api_key, created_at
- markets: id, title, description, category, status, pool_yes, pool_no, winner, created_at
- transactions: id, user_id, market_id, type, outcome, shares, price, fee, created_at
- positions: id, user_id, market_id, outcome, shares, avg_price

**API response pattern:**
```javascript
res.json({ success: true, data: result });
res.status(400).json({ success: false, error: 'message' });
```

**React component pattern:**
```tsx
interface Props { ... }
export function ComponentName({ prop1, prop2 }: Props) {
  return (
    <div className="tailwind classes">
      ...
    </div>
  );
}
```
"""

CODE_INSTRUCTION = """

IMPORTANT: Output ONLY the code in a single code block. No explanations before or after.
Start your response with ``` and end with ```.
"""


def extract_code(response: str) -> str:
    """Extract clean code from response, handling thinking model output."""
    # Find all code blocks
    blocks = re.findall(r'```(?:\w*)\n?(.*?)```', response, re.DOTALL)
    
    if blocks:
        # Get the longest code block (usually the most complete)
        code = max(blocks, key=len).strip()
        return code
    
    # No code blocks - try to find code-like content
    lines = response.split('\n')
    code_lines = []
    in_code = False
    
    for line in lines:
        # Heuristics for code
        if any(kw in line for kw in ['function', 'const ', 'import ', 'export ', 'interface ', 'router.', 'class ']):
            in_code = True
        if in_code:
            # Stop at obvious non-code
            if line.strip().startswith(('Actually', 'Note:', 'This ', 'The ', 'I ', 'We ')):
                break
            code_lines.append(line)
    
    return '\n'.join(code_lines).strip() if code_lines else response


def validate_code(code: str, task_type: str) -> Dict[str, Any]:
    """Basic validation of generated code."""
    issues = []
    
    # Check for common problems
    if 'MongoDB' in code or '$regex' in code or '.find(' in code:
        issues.append("Uses MongoDB patterns instead of SQLite")
    
    if 'await ' in code and task_type == 'backend':
        # Check if it's properly async
        if 'async ' not in code:
            issues.append("Uses await without async function")
    
    if task_type == 'backend' and 'db.prepare' not in code and 'SELECT' not in code.upper():
        if 'validation' not in task_type.lower() and 'websocket' not in task_type.lower():
            issues.append("Missing database operations for backend task")
    
    if len(code) < 100:
        issues.append("Code seems too short/incomplete")
    
    # Check for thinking leakage
    thinking_indicators = ['I need to', 'Let me', 'The user wants', 'Actually,', 'I should']
    for indicator in thinking_indicators:
        if indicator in code:
            issues.append(f"Thinking leaked into code: '{indicator}'")
            break
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "code_length": len(code)
    }


@dataclass
class SwarmTask:
    label: str
    prompt: str
    task_type: str  # 'backend', 'frontend', 'websocket'
    output_file: Optional[str] = None


@dataclass  
class SwarmResult:
    label: str
    code: str
    raw_response: str
    validation: Dict[str, Any]
    runtime: float
    cost: float
    

def run_project_beta_swarm(tasks: List[SwarmTask], max_workers: int = 4) -> List[SwarmResult]:
    """Run a swarm of tasks with context injection and validation."""
    
    orch = FireworksOrchestrator(model="kimi-k2.5", max_tokens=2000)
    
    # Prepare tasks with context
    prepared_tasks = []
    for task in tasks:
        full_prompt = CODEBASE_CONTEXT + "\n\n## Task\n" + task.prompt + CODE_INSTRUCTION
        prepared_tasks.append({
            "label": task.label,
            "prompt": full_prompt,
            "_task_type": task.task_type
        })
    
    print(f"🚀 ProjectBeta Swarm: {len(tasks)} tasks")
    start = time.time()
    
    # Run parallel
    raw_results = orch.run_parallel(prepared_tasks, max_workers=max_workers)
    
    elapsed = time.time() - start
    print(f"⏱️  Inference done in {elapsed:.1f}s")
    
    # Process results
    results = []
    for raw, task in zip(raw_results, tasks):
        # Extract code
        code = extract_code(raw.response)
        
        # Validate
        validation = validate_code(code, task.task_type)
        
        results.append(SwarmResult(
            label=raw.label,
            code=code,
            raw_response=raw.response,
            validation=validation,
            runtime=raw.runtime_seconds,
            cost=raw.cost_usd
        ))
    
    # Summary
    total_cost = sum(r.cost for r in results)
    valid_count = sum(1 for r in results if r.validation["valid"])
    
    print(f"\n📊 Results:")
    print(f"   Valid: {valid_count}/{len(results)}")
    print(f"   Cost: ${total_cost:.6f}")
    print(f"   Time: {elapsed:.1f}s")
    
    for r in results:
        status = "✅" if r.validation["valid"] else "⚠️"
        print(f"   {status} {r.label}: {r.validation['code_length']} chars")
        for issue in r.validation["issues"]:
            print(f"      ❌ {issue}")
    
    return results


if __name__ == "__main__":
    # Test swarm
    tasks = [
        SwarmTask(
            label="input-validation",
            task_type="backend",
            prompt="""Write Express.js middleware for validating bot registration and trade requests.

Validate bot registration:
- name: 2-50 characters, required
- webhookUrl: valid URL format, required

Validate trade requests:
- marketId: required string
- outcome: must be 'yes' or 'no'
- amount: positive number, max 1000

Return 400 with { success: false, error: 'specific message' } on validation failure.
Export as: validateBotRegistration and validateTradeRequest middleware functions."""
        ),
        SwarmTask(
            label="market-search",
            task_type="backend", 
            prompt="""Write Express.js route handler for GET /api/markets/search

Query parameters:
- q: search term (search in title and description, case-insensitive)
- status: filter by 'open', 'resolved', or omit for all
- category: filter by category or omit for all
- page: page number (default 1)
- limit: results per page (default 20, max 100)

Use SQLite with db.prepare().all() pattern. Use LIKE for search with % wildcards.
Return { success: true, data: markets, pagination: { page, limit, total, pages } }"""
        ),
        SwarmTask(
            label="bot-stats-card",
            task_type="frontend",
            prompt="""Write a React TypeScript component BotStatsCard.tsx

Props:
- name: string
- balance: number  
- profit: number (negative = loss)
- winRate: number (0-100)
- totalTrades: number
- verified: boolean

Display:
- Bot name (with verified checkmark badge if verified)
- Balance formatted as currency
- Profit/loss with green (positive) or red (negative) color
- Win rate as percentage
- Total trades count

Use Tailwind CSS. Compact card design suitable for a grid layout."""
        ),
        SwarmTask(
            label="trade-broadcaster",
            task_type="websocket",
            prompt="""Write a WebSocket trade broadcaster module.

Function: broadcastTrade(wss, tradeData)
- wss: WebSocket.Server instance
- tradeData: { marketId, odName, outcome, shares, price, timestamp }

Broadcast to all connected clients with readyState === WebSocket.OPEN
Message format: JSON with { type: 'trade', data: tradeData }

Also export: broadcastMarketUpdate(wss, marketId, poolYes, poolNo) for pool changes."""
        )
    ]
    
    results = run_project_beta_swarm(tasks)
    
    # Save results
    with open("/tmp/project_beta_swarm.json", "w") as f:
        json.dump([{
            "label": r.label,
            "code": r.code,
            "validation": r.validation,
            "runtime": r.runtime,
            "cost": r.cost
        } for r in results], f, indent=2)
    
    print("\n📁 Saved to /tmp/project_beta_swarm.json")
