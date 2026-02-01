#!/usr/bin/env python3
"""
Basic usage example for ATLAS Brain.

Run from workspace root:
    python brain/examples/basic_usage.py
"""
import os
import sys
import asyncio
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from brain import Brain


async def main():
    print("🧠 ATLAS Brain - Basic Usage Example")
    print("=" * 50)
    
    # Create and initialize the brain
    brain = Brain()
    await brain.initialize()
    print("✓ Brain initialized")
    
    # Log some activities
    print("\n📝 Logging activities...")
    brain.log_activity(
        "conversation",
        "User asked about integrating memU concepts into ATLAS"
    )
    brain.log_activity(
        "action",
        "Created brain module with proactive memory features"
    )
    brain.log_activity(
        "decision",
        "Decided to build custom solution instead of using memU dependency"
    )
    print("✓ Logged 3 activities")
    
    # Add some memories
    print("\n💾 Adding memories...")
    await brain.link_memory(
        "Matt prefers Fahrenheit over Celsius for temperature display",
        category="300-personal",
        metadata={"type": "preference", "confidence": "high"}
    )
    await brain.link_memory(
        "ATLAS Brain uses LanceDB for vector storage",
        category="100-projects",
        metadata={"project": "atlas-brain"}
    )
    print("✓ Added 2 memories")
    
    # Search for related memories
    print("\n🔍 Searching memories...")
    results = await brain.find_related("What temperature units does Matt prefer?")
    print(f"✓ Found {len(results)} related memories")
    for r in results:
        print(f"   - {r['content'][:60]}... (score: {r['score']:.2f})")
    
    # Get proactive suggestions
    print("\n💡 Getting suggestions...")
    suggestions = await brain.get_proactive_suggestions("Working on voice interface")
    print(f"✓ Got {len(suggestions)} suggestions")
    for s in suggestions[:3]:
        print(f"   - [{s['type']}] {s['suggestion'][:50]}...")
    
    # Get brain status
    print("\n📊 Brain Status:")
    status = brain.get_status()
    print(f"   Initialized: {status['initialized']}")
    print(f"   Activities: {status['activity_count']}")
    print(f"   Memories: {status['memory_count']}")
    
    # If we have an API key, try extraction and prediction
    if os.environ.get("ANTHROPIC_API_KEY"):
        print("\n🤖 Testing Claude integration...")
        
        # Extract insights
        conversation = """
        User: I'm heading to the gym now
        Assistant: Great! Have a good workout. The weather is 14°F outside, so bundle up!
        User: Thanks! I'll probably grab coffee after.
        """
        
        insights = await brain.extract_insights(conversation)
        if insights.get("_success"):
            print("✓ Extracted insights:")
            print(f"   Facts: {insights.get('facts', [])}")
            print(f"   Topics: {insights.get('topics', [])}")
        
        # Predict intent
        predictions = await brain.predict_intent()
        if predictions.get("_success"):
            print("✓ Predictions available:")
            print(f"   Context: {predictions.get('overall_context', 'N/A')[:100]}")
    else:
        print("\n⚠️ Set ANTHROPIC_API_KEY to test Claude features")
    
    print("\n" + "=" * 50)
    print("🧠 Example complete!")


if __name__ == "__main__":
    asyncio.run(main())
