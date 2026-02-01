"""
ATLAS Brain - Proactive Memory & Intelligence System

A custom implementation inspired by memU concepts, built on our existing
infrastructure (LanceDB, Dewey Decimal knowledge, MEMORY.md).

Components:
- ActivityLogger: Captures and logs all activities/conversations
- MemoryExtractor: Extracts facts, preferences, and insights using Claude
- SemanticLinker: Connects related memories using embeddings
- IntentPredictor: Predicts what the user might need next
- ProactiveSuggester: Surfaces relevant context proactively

Usage:
    from brain import Brain
    
    brain = Brain()
    brain.log_activity("conversation", content="...")
    insights = brain.extract_insights(conversation)
    predictions = brain.predict_intent()
"""

from .core import Brain
from .activity import ActivityLogger
from .extractor import MemoryExtractor
from .linker import SemanticLinker
from .predictor import IntentPredictor
from .suggester import ProactiveSuggester
from .memory_sync import MemorySync
from . import hooks

# Optional RLM integration (requires /workspace/projects/rlm)
try:
    from .rlm_integration import RLMBrain, create_rlm_brain
    RLM_AVAILABLE = True
except ImportError:
    RLMBrain = None
    create_rlm_brain = None
    RLM_AVAILABLE = False

# Task planning and reflection
from .task_planner import TaskPlanner, TaskPlan, TaskStep, TaskStatus
from .reflection import SelfReflector, Reflection, quick_reflect

__version__ = "0.1.0"
__all__ = [
    "Brain",
    "ActivityLogger", 
    "MemoryExtractor",
    "SemanticLinker",
    "IntentPredictor",
    "ProactiveSuggester",
    "MemorySync",
    "hooks",
    # RLM integration
    "RLMBrain",
    "create_rlm_brain",
    "RLM_AVAILABLE",
    # Task planning & reflection
    "TaskPlanner",
    "TaskPlan",
    "TaskStep",
    "TaskStatus",
    "SelfReflector",
    "Reflection",
    "quick_reflect",
]
