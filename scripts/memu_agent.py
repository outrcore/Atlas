#!/usr/bin/env python3
"""
memU Background Agent for ATLAS

This agent runs in the background and:
1. Logs activities from conversations
2. Runs theory of mind predictions
3. Generates memory suggestions
4. Clusters and organizes memories

Usage:
    python memu_agent.py --mode daemon  # Run as background daemon
    python memu_agent.py --mode once    # Run once and exit
    python memu_agent.py --predict      # Run intent prediction
"""
import os
import sys
import json
import asyncio
import argparse
from datetime import datetime
from pathlib import Path

# Add workspace to path
sys.path.insert(0, "/workspace/clawd")

MEMORY_DIR = "/workspace/clawd/memu_memory"
LOG_FILE = "/workspace/clawd/memory/memu_activity.jsonl"


def get_llm_client():
    """Get LLM client for memU (uses OpenAI API format)."""
    from memu import OpenAIClient
    
    # Check for API keys
    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if openai_key:
        return OpenAIClient(api_key=openai_key)
    elif anthropic_key:
        # Could use Anthropic via OpenAI-compatible proxy if available
        print("⚠️ OpenAI key preferred for embeddings. Using Anthropic...")
        # For now, return None - embeddings won't work
        return None
    else:
        print("❌ No API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY")
        return None


def create_agent():
    """Create and configure the memU agent."""
    from memu import MemoryAgent
    
    client = get_llm_client()
    if not client:
        return None
    
    # Ensure memory directory exists
    Path(MEMORY_DIR).mkdir(parents=True, exist_ok=True)
    
    agent = MemoryAgent(
        llm_client=client,
        agent_id="atlas",
        user_id="matt",
        memory_dir=MEMORY_DIR,
        enable_embeddings=True
    )
    
    return agent


def log_activity(activity: dict):
    """Log an activity to the activity log."""
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
    
    activity["timestamp"] = datetime.now().isoformat()
    
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(activity) + "\n")


def add_memory(agent, content: str, category: str = "general"):
    """Add a memory to the memU store."""
    try:
        result = agent.call_function(
            "add_activity_memory",
            {
                "content": content,
                "category": category,
                "metadata": {
                    "source": "atlas",
                    "timestamp": datetime.now().isoformat()
                }
            }
        )
        return result
    except Exception as e:
        print(f"Error adding memory: {e}")
        return None


def run_theory_of_mind(agent):
    """Run intent prediction on recent activities."""
    try:
        result = agent.call_function("run_theory_of_mind", {})
        return result
    except Exception as e:
        print(f"Error running theory of mind: {e}")
        return None


def generate_suggestions(agent):
    """Generate proactive memory suggestions."""
    try:
        result = agent.call_function("generate_memory_suggestions", {})
        return result
    except Exception as e:
        print(f"Error generating suggestions: {e}")
        return None


def cluster_memories(agent):
    """Cluster and organize memories."""
    try:
        result = agent.call_function("cluster_memories", {})
        return result
    except Exception as e:
        print(f"Error clustering memories: {e}")
        return None


async def daemon_loop(agent, interval_seconds: int = 300):
    """Run the agent in daemon mode."""
    print(f"🧠 memU daemon starting (interval: {interval_seconds}s)")
    
    while True:
        try:
            print(f"\n[{datetime.now().isoformat()}] Running memory maintenance...")
            
            # Run theory of mind
            predictions = run_theory_of_mind(agent)
            if predictions:
                print(f"  Predictions: {predictions}")
                log_activity({"type": "prediction", "data": predictions})
            
            # Generate suggestions
            suggestions = generate_suggestions(agent)
            if suggestions:
                print(f"  Suggestions: {suggestions}")
                log_activity({"type": "suggestions", "data": suggestions})
            
            # Cluster memories periodically
            clusters = cluster_memories(agent)
            if clusters:
                print(f"  Clusters updated")
                log_activity({"type": "cluster", "data": clusters})
            
        except Exception as e:
            print(f"  Error in daemon loop: {e}")
        
        await asyncio.sleep(interval_seconds)


def main():
    parser = argparse.ArgumentParser(description="memU Background Agent")
    parser.add_argument("--mode", choices=["daemon", "once", "test"], default="test")
    parser.add_argument("--predict", action="store_true", help="Run intent prediction")
    parser.add_argument("--interval", type=int, default=300, help="Daemon interval (seconds)")
    
    args = parser.parse_args()
    
    print("🧠 memU Agent for ATLAS")
    print("=" * 40)
    
    agent = create_agent()
    if not agent:
        print("Failed to create agent. Check API keys.")
        return 1
    
    print(f"✅ Agent initialized")
    print(f"   Memory dir: {MEMORY_DIR}")
    print(f"   Mode: {args.mode}")
    
    if args.predict:
        result = run_theory_of_mind(agent)
        print(f"\n🔮 Predictions:\n{result}")
        return 0
    
    if args.mode == "daemon":
        asyncio.run(daemon_loop(agent, args.interval))
    elif args.mode == "once":
        run_theory_of_mind(agent)
        generate_suggestions(agent)
        cluster_memories(agent)
    else:
        print("\nTest mode - agent ready but not running.")
        print("Use --mode daemon to run continuously")
        print("Use --mode once to run maintenance once")
        print("Use --predict to run intent prediction")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
