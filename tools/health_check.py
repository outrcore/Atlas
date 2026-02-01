#!/usr/bin/env python3
"""
ATLAS Health Check Script

Run this during heartbeats to monitor system stability.
Exit codes: 0 = healthy, 1 = warning, 2 = critical
"""

import subprocess
import json
from datetime import datetime

def check_memory():
    """Check if memory usage is concerning"""
    result = subprocess.run(['free', '-m'], capture_output=True, text=True)
    lines = result.stdout.strip().split('\n')
    mem_line = lines[1].split()
    total = int(mem_line[1])
    used = int(mem_line[2])
    pct = (used / total) * 100
    
    status = "OK" if pct < 80 else "WARNING" if pct < 95 else "CRITICAL"
    return {
        "check": "memory",
        "status": status,
        "used_mb": used,
        "total_mb": total,
        "percent": round(pct, 1)
    }

def check_screens():
    """Check core screen sessions are running"""
    result = subprocess.run(['screen', '-ls'], capture_output=True, text=True)
    output = result.stdout
    
    core_screens = ['atlas-voice', 'atlas-discord', 'tunnel', 'brain-daemon', 'Jarvis']
    running = [s for s in core_screens if s in output]
    missing = [s for s in core_screens if s not in output]
    
    # Check for too many screens (potential orphans)
    screen_count = output.count('Detached') + output.count('Attached')
    
    status = "OK" if not missing and screen_count < 10 else "WARNING"
    return {
        "check": "screens",
        "status": status,
        "running": running,
        "missing": missing,
        "total_count": screen_count
    }

def check_gateway():
    """Check if openclaw-gateway is running"""
    result = subprocess.run(['pgrep', '-f', 'openclaw-gateway'], capture_output=True, text=True)
    running = result.returncode == 0
    
    return {
        "check": "gateway",
        "status": "OK" if running else "CRITICAL",
        "running": running
    }

def check_orphan_processes():
    """Check for orphaned claude/npx processes"""
    result = subprocess.run(
        ['ps', 'aux'], 
        capture_output=True, text=True
    )
    
    lines = result.stdout.split('\n')
    claude_procs = [l for l in lines if 'claude' in l.lower() and 'grep' not in l]
    
    # Filter out legitimate processes
    orphans = [p for p in claude_procs if 'claude -p' in p or 'npx.*claude' in p]
    
    return {
        "check": "orphans",
        "status": "OK" if len(orphans) == 0 else "WARNING",
        "orphan_count": len(orphans),
        "details": orphans[:3] if orphans else []
    }

def check_log_errors():
    """Check recent log for errors"""
    log_path = f"/tmp/openclaw/openclaw-{datetime.now().strftime('%Y-%m-%d')}.log"
    try:
        result = subprocess.run(
            ['tail', '-100', log_path],
            capture_output=True, text=True
        )
        
        errors = [l for l in result.stdout.split('\n') if '"logLevelName":"ERROR"' in l]
        rate_limits = [l for l in result.stdout.split('\n') if 'rate limit' in l.lower()]
        
        status = "OK"
        if len(errors) > 10:
            status = "WARNING"
        if len(rate_limits) > 0:
            status = "WARNING"
            
        return {
            "check": "logs",
            "status": status,
            "recent_errors": len(errors),
            "rate_limit_warnings": len(rate_limits)
        }
    except Exception as e:
        return {
            "check": "logs",
            "status": "UNKNOWN",
            "error": str(e)
        }

def main():
    print(f"=== ATLAS Health Check - {datetime.now().isoformat()} ===\n")
    
    checks = [
        check_memory(),
        check_screens(),
        check_gateway(),
        check_orphan_processes(),
        check_log_errors()
    ]
    
    overall = "OK"
    for check in checks:
        status = check["status"]
        if status == "CRITICAL":
            overall = "CRITICAL"
        elif status == "WARNING" and overall != "CRITICAL":
            overall = "WARNING"
            
        icon = "✅" if status == "OK" else "⚠️" if status == "WARNING" else "❌"
        print(f"{icon} {check['check']}: {status}")
        
        # Print details for non-OK checks
        if status != "OK":
            for k, v in check.items():
                if k not in ['check', 'status']:
                    print(f"   {k}: {v}")
        print()
    
    print(f"Overall: {overall}")
    
    # Exit code
    exit_code = 0 if overall == "OK" else 1 if overall == "WARNING" else 2
    return exit_code

if __name__ == "__main__":
    exit(main())
