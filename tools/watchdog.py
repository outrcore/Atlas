#!/usr/bin/env python3
"""
ATLAS Watchdog — monitors critical screen sessions and restarts if dead.
Runs every 60s. Logs to stdout.
"""

import subprocess
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-5s | %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger("watchdog")

# Screen name → (working dir, command)
CRITICAL_SCREENS = {
    "Jarvis": ("cd /workspace/Jarvis && pnpm openclaw gateway 2>&1 | tee /tmp/jarvis-gateway.log"),
    # "quasar-live": DISABLED — rate limited, waiting for reset at 00:00 UTC
    "quasar-recorder": ("cd /workspace/projects/HyperClaude-QUASAR && python tools/tick_recorder.py 2>&1 | tee /tmp/quasar-recorder.log"),
    "quasar-monitor": ("cd /workspace/projects/HyperClaude-QUASAR && python tools/live_monitor.py 2>&1 | tee /tmp/quasar-monitor.log"),
    "amt-v5": ("cd /workspace/projects/HyperClaude-AMT-Atlas && python run_multi.py --config config_v5.yaml --live 2>&1 | tee /tmp/amt-v5.log"),
    "amt-test-b": ("cd /workspace/projects/HyperClaude-AMT-Atlas && python run_multi.py --config config_test_b.yaml --live 2>&1 | tee /tmp/amt-test-b.log"),
    "amt-test-c": ("cd /workspace/projects/HyperClaude-AMT-Atlas && python run_multi.py --config config_test_c.yaml --live 2>&1 | tee /tmp/amt-test-c.log"),
}

CHECK_INTERVAL = 60  # seconds


def get_running_screens():
    try:
        out = subprocess.check_output(["screen", "-ls"], text=True, stderr=subprocess.STDOUT)
        return out
    except subprocess.CalledProcessError as e:
        return e.output


def is_screen_alive(name):
    screens = get_running_screens()
    return f".{name}\t" in screens or f".{name} " in screens


def restart_screen(name, cmd):
    logger.warning(f"🔄 Restarting dead screen: {name}")
    subprocess.run(["screen", "-S", name, "-X", "quit"], capture_output=True)
    subprocess.run(
        ["screen", "-dmS", name, "bash", "-c", cmd],
        capture_output=True
    )
    time.sleep(2)
    if is_screen_alive(name):
        logger.info(f"  ✅ {name} restarted successfully")
        return True
    else:
        logger.error(f"  ❌ {name} failed to restart")
        return False


def main():
    logger.info(f"Watchdog started — monitoring {len(CRITICAL_SCREENS)} screens")
    restarts = {}

    while True:
        for name, cmd in CRITICAL_SCREENS.items():
            if not is_screen_alive(name):
                # Rate limit: max 3 restarts per screen per hour
                now = time.time()
                history = restarts.get(name, [])
                history = [t for t in history if now - t < 3600]
                
                if len(history) >= 3:
                    if len(history) == 3:  # only log once
                        logger.error(f"⛔ {name} hit restart limit (3/hr) — giving up")
                    continue
                
                if restart_screen(name, cmd):
                    history.append(now)
                    restarts[name] = history
            
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
