#!/usr/bin/env python3
"""
Test script for ATLAS Brain.
"""
import os
import sys
import asyncio
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set API key if available
API_KEY = os.environ.get("ANTHROPIC_API_KEY")


async def test_activity_logger():
    """Test the activity logger."""
    print("\n=== Testing Activity Logger ===")
    
    from brain.activity import ActivityLogger
    
    logger = ActivityLogger(Path("/tmp/brain_test/activity"))
    
    # Log some activities
    id1 = logger.log("conversation", "User: Hello, how are you?")
    id2 = logger.log("conversation", "Assistant: I'm doing well!")
    id3 = logger.log("action", "Created a new file")
    
    print(f"✓ Logged 3 activities: {id1}, {id2}, {id3}")
    
    # Get recent
    recent = logger.get_recent(hours=1)
    print(f"✓ Retrieved {len(recent)} recent activities")
    
    # Get summary
    summary = logger.get_summary(hours=1)
    print(f"✓ Summary: {summary}")
    
    return True


async def test_semantic_linker():
    """Test the semantic linker."""
    print("\n=== Testing Semantic Linker ===")
    
    from brain.linker import SemanticLinker
    
    linker = SemanticLinker(Path("/tmp/brain_test/vectors"))
    await linker.initialize()
    
    # Add some memories
    id1 = await linker.add_and_link(
        "Matt lives in Chicago and works as a trader",
        category="300-personal",
    )
    print(f"✓ Added memory: {id1}")
    
    id2 = await linker.add_and_link(
        "The voice interface uses Edge TTS for text to speech",
        category="100-projects",
    )
    print(f"✓ Added memory: {id2}")
    
    id3 = await linker.add_and_link(
        "Temperature should be displayed in Fahrenheit, not Celsius",
        category="300-personal",
    )
    print(f"✓ Added memory: {id3}")
    
    # Search
    results = await linker.search("What city does Matt live in?")
    print(f"✓ Search found {len(results)} results")
    if results:
        print(f"  Top result: {results[0]['content'][:50]}... (score: {results[0]['score']:.2f})")
        
    # Count
    count = linker.count()
    print(f"✓ Total memories: {count}")
    
    return True


async def test_extractor():
    """Test the memory extractor."""
    print("\n=== Testing Memory Extractor ===")
    
    if not API_KEY:
        print("⚠️ No API key, skipping extractor test")
        return True
        
    from brain.extractor import MemoryExtractor
    
    extractor = MemoryExtractor(api_key=API_KEY)
    
    conversation = """
    User: What's the weather like in Chicago?
    Assistant: It's currently 14°F (-10°C) with snow. Quite cold!
    User: Ugh, I hate the cold. Remind me to use Fahrenheit next time.
    Assistant: Noted! I'll use Fahrenheit from now on.
    User: Thanks. I'm heading to the gym now.
    Assistant: Great! Keep up the healthy habits. Have a good workout!
    """
    
    result = await extractor.extract(conversation)
    
    if result.get("_success"):
        print(f"✓ Extraction successful")
        print(f"  Facts: {result.get('facts', [])}")
        print(f"  Preferences: {result.get('preferences', [])}")
        print(f"  Topics: {result.get('topics', [])}")
    else:
        print(f"✗ Extraction failed: {result.get('_error')}")
        
    return result.get("_success", False)


async def test_predictor():
    """Test the intent predictor."""
    print("\n=== Testing Intent Predictor ===")
    
    if not API_KEY:
        print("⚠️ No API key, skipping predictor test")
        return True
        
    from brain.predictor import IntentPredictor
    
    predictor = IntentPredictor(api_key=API_KEY)
    
    activities = [
        {"type": "conversation", "content": "Working on the ATLAS voice interface", "timestamp": "2026-01-31T12:00:00"},
        {"type": "action", "content": "Created brain module for proactive memory", "timestamp": "2026-01-31T13:00:00"},
        {"type": "conversation", "content": "Discussed integrating memU concepts", "timestamp": "2026-01-31T14:00:00"},
    ]
    
    result = await predictor.predict(activities)
    
    if result.get("_success"):
        print(f"✓ Prediction successful")
        print(f"  Context: {result.get('overall_context', 'N/A')}")
        print(f"  Immediate needs: {len(result.get('immediate_needs', []))}")
        print(f"  Suggestions: {len(result.get('proactive_suggestions', []))}")
    else:
        print(f"✗ Prediction failed: {result.get('_error')}")
        
    return result.get("_success", False)


async def test_full_brain():
    """Test the full brain integration."""
    print("\n=== Testing Full Brain ===")
    
    from brain import Brain
    
    brain = Brain(workspace="/tmp/brain_test")
    
    # Initialize
    await brain.initialize()
    print("✓ Brain initialized")
    
    # Log activity
    brain.log_activity("test", "This is a test activity")
    print("✓ Activity logged")
    
    # Get status
    status = brain.get_status()
    print(f"✓ Status: initialized={status['initialized']}, activities={status['activity_count']}")
    
    # Add and search memory
    await brain.link_memory("Test memory for the brain", "000-reference")
    results = await brain.find_related("test memory")
    print(f"✓ Memory added and searched: {len(results)} results")
    
    return True


async def main():
    """Run all tests."""
    print("🧠 ATLAS Brain Test Suite")
    print("=" * 50)
    
    results = {
        "activity_logger": await test_activity_logger(),
        "semantic_linker": await test_semantic_linker(),
        "extractor": await test_extractor(),
        "predictor": await test_predictor(),
        "full_brain": await test_full_brain(),
    }
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
        
    all_passed = all(results.values())
    print(f"\n{'🎉 All tests passed!' if all_passed else '❌ Some tests failed'}")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
