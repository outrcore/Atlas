#!/usr/bin/env python3
"""
Quick brain maintenance script.
Run this to process recent conversations and update memory.

Usage:
    python scripts/brain_maintain.py
    python scripts/brain_maintain.py --predict
    python scripts/brain_maintain.py --status
"""
import os
import sys
import asyncio
import argparse
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    parser = argparse.ArgumentParser(description="Brain maintenance")
    parser.add_argument("--predict", action="store_true", help="Run intent prediction")
    parser.add_argument("--status", action="store_true", help="Show status only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()
    
    from brain import Brain
    
    print("🧠 ATLAS Brain Maintenance")
    print("=" * 40)
    
    brain = Brain()
    await brain.initialize()
    
    if args.status:
        status = brain.get_status()
        print(f"Initialized: {status['initialized']}")
        print(f"Activities logged: {status['activity_count']}")
        print(f"Memories stored: {status['memory_count']}")
        print(f"Last maintenance: {status['last_maintenance'] or 'Never'}")
        return
    
    if args.predict:
        print("\n🔮 Running intent prediction...")
        prediction = await brain.predict_intent()
        
        if prediction.get("_success"):
            print(f"\n📋 Context: {prediction.get('overall_context', 'N/A')}")
            
            if prediction.get("immediate_needs"):
                print("\n🎯 Immediate needs:")
                for need in prediction["immediate_needs"]:
                    print(f"  - {need.get('need')} ({need.get('confidence', 0):.0%})")
                    
            if prediction.get("proactive_suggestions"):
                print("\n💡 Suggestions:")
                for sug in prediction["proactive_suggestions"]:
                    print(f"  - {sug.get('suggestion')}")
        else:
            print(f"❌ Prediction failed: {prediction.get('_error')}")
        return
    
    # Run full maintenance
    print("\n⚙️ Running maintenance...")
    await brain.run_maintenance()
    
    # Show updated status
    status = brain.get_status()
    print(f"\n✅ Maintenance complete!")
    print(f"   Activities: {status['activity_count']}")
    print(f"   Memories: {status['memory_count']}")


if __name__ == "__main__":
    asyncio.run(main())
