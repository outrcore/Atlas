#!/usr/bin/env python3
"""
Brain Daemon - Runs the ATLAS Brain as a background service.

Responsibilities:
- Periodic maintenance (extraction, linking, clustering)
- Intent prediction updates
- Proactive suggestion generation
- Activity log management

Usage:
    python -m brain.daemon --mode daemon     # Run continuously
    python -m brain.daemon --mode once       # Run once and exit
    python -m brain.daemon --predict         # Just run prediction
    python -m brain.daemon --status          # Show status
"""
import os
import sys
import asyncio
import argparse
import signal
from datetime import datetime
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from brain import Brain


class BrainDaemon:
    """Background daemon for the ATLAS Brain."""
    
    def __init__(
        self,
        maintenance_interval: int = 300,  # 5 minutes
        prediction_interval: int = 1800,  # 30 minutes
    ):
        self.brain = Brain()
        self.maintenance_interval = maintenance_interval
        self.prediction_interval = prediction_interval
        self._running = False
        self._last_prediction = None
        
    async def start(self):
        """Start the daemon."""
        print("🧠 Starting ATLAS Brain Daemon...")
        print(f"   Maintenance interval: {self.maintenance_interval}s")
        print(f"   Prediction interval: {self.prediction_interval}s")
        
        await self.brain.initialize()
        
        self._running = True
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
        
        # Run main loop
        await self._main_loop()
        
    def _handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        print("\n🧠 Shutting down Brain Daemon...")
        self._running = False
        
    async def _main_loop(self):
        """Main daemon loop."""
        last_maintenance = datetime.now()
        last_prediction = datetime.now()
        
        while self._running:
            now = datetime.now()
            
            # Run maintenance
            if (now - last_maintenance).total_seconds() >= self.maintenance_interval:
                try:
                    await self.brain.run_maintenance()
                    last_maintenance = now
                except Exception as e:
                    print(f"❌ Maintenance error: {e}")
                    
            # Run prediction
            if (now - last_prediction).total_seconds() >= self.prediction_interval:
                try:
                    prediction = await self.brain.predict_intent()
                    self._last_prediction = prediction
                    
                    if prediction.get("_success"):
                        self._log_prediction(prediction)
                    
                    last_prediction = now
                except Exception as e:
                    print(f"❌ Prediction error: {e}")
                    
            # Sleep for a bit
            await asyncio.sleep(60)
            
    def _log_prediction(self, prediction: dict):
        """Log prediction results."""
        print(f"\n🔮 Intent Prediction at {datetime.now().strftime('%H:%M')}:")
        
        if prediction.get("immediate_needs"):
            print("  Immediate needs:")
            for need in prediction["immediate_needs"][:3]:
                print(f"    - {need.get('need', 'Unknown')} ({need.get('confidence', 0):.0%})")
                
        if prediction.get("proactive_suggestions"):
            print("  Suggestions:")
            for sug in prediction["proactive_suggestions"][:3]:
                print(f"    - {sug.get('suggestion', 'Unknown')}")
                
    async def run_once(self):
        """Run maintenance once and exit."""
        print("🧠 Running Brain maintenance (one-time)...")
        await self.brain.initialize()
        await self.brain.run_maintenance()
        print("✅ Done!")
        
    async def run_prediction(self):
        """Run prediction once and show results."""
        print("🧠 Running intent prediction...")
        await self.brain.initialize()
        
        prediction = await self.brain.predict_intent()
        
        if prediction.get("_success"):
            print("\n" + "=" * 50)
            print("🔮 INTENT PREDICTION RESULTS")
            print("=" * 50)
            
            print("\n📋 Overall Context:")
            print(f"   {prediction.get('overall_context', 'N/A')}")
            
            print("\n🎯 Immediate Needs:")
            for need in prediction.get("immediate_needs", []):
                print(f"   • {need.get('need')} (confidence: {need.get('confidence', 0):.0%})")
                print(f"     Reasoning: {need.get('reasoning', 'N/A')}")
                
            print("\n📝 Upcoming Tasks:")
            for task in prediction.get("upcoming_tasks", []):
                print(f"   • [{task.get('priority', 'medium').upper()}] {task.get('task')}")
                
            print("\n⚠️  Potential Blockers:")
            for blocker in prediction.get("potential_blockers", []):
                print(f"   • {blocker.get('blocker')}")
                print(f"     Suggestion: {blocker.get('suggestion', 'N/A')}")
                
            print("\n💡 Proactive Suggestions:")
            for sug in prediction.get("proactive_suggestions", []):
                print(f"   • {sug.get('suggestion')}")
                print(f"     Benefit: {sug.get('benefit', 'N/A')}")
                
            print("\n🔄 Patterns Noticed:")
            for pattern in prediction.get("patterns", []):
                print(f"   • {pattern}")
                
        else:
            print(f"❌ Prediction failed: {prediction.get('_error')}")
            
    def show_status(self):
        """Show brain status."""
        print("🧠 ATLAS Brain Status")
        print("=" * 40)
        
        status = self.brain.get_status()
        
        print(f"Initialized: {status['initialized']}")
        print(f"Last maintenance: {status['last_maintenance'] or 'Never'}")
        print(f"Activity count: {status['activity_count']}")
        print(f"Memory count: {status['memory_count']}")
        
        print("\nPaths:")
        for name, path in status["paths"].items():
            exists = "✓" if Path(path).exists() else "✗"
            print(f"  {exists} {name}: {path}")


async def main():
    parser = argparse.ArgumentParser(description="ATLAS Brain Daemon")
    parser.add_argument("--mode", choices=["daemon", "once"], default="daemon")
    parser.add_argument("--predict", action="store_true", help="Run prediction only")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--maintenance-interval", type=int, default=300)
    parser.add_argument("--prediction-interval", type=int, default=1800)
    
    args = parser.parse_args()
    
    daemon = BrainDaemon(
        maintenance_interval=args.maintenance_interval,
        prediction_interval=args.prediction_interval,
    )
    
    if args.status:
        daemon.show_status()
    elif args.predict:
        await daemon.run_prediction()
    elif args.mode == "once":
        await daemon.run_once()
    else:
        await daemon.start()


if __name__ == "__main__":
    asyncio.run(main())
