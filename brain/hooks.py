"""
Brain Hooks - Integration points for OpenClaw sessions.

These hooks can be called from session events to keep the brain updated.
"""
import os
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

# Singleton brain instance
_brain_instance = None


def get_brain():
    """Get or create the brain singleton."""
    global _brain_instance
    
    if _brain_instance is None:
        from . import Brain
        _brain_instance = Brain()
        
    return _brain_instance


async def on_session_message(
    role: str,
    content: str,
    session_id: Optional[str] = None,
    channel: Optional[str] = None,
):
    """
    Hook called when a message is sent/received in a session.
    
    Args:
        role: "user" or "assistant"
        content: Message content
        session_id: Optional session identifier
        channel: Optional channel (telegram, discord, etc.)
    """
    brain = get_brain()
    
    # Log the activity
    brain.log_activity(
        activity_type="conversation",
        content=f"[{role}] {content}",
        metadata={
            "role": role,
            "session_id": session_id,
            "channel": channel,
            "timestamp": datetime.now().isoformat(),
        },
    )


async def on_session_end(
    session_id: str,
    messages: list,
    duration_seconds: Optional[int] = None,
):
    """
    Hook called when a session ends.
    
    Args:
        session_id: Session identifier
        messages: List of messages from the session
        duration_seconds: How long the session lasted
    """
    brain = get_brain()
    
    # Format conversation for extraction
    conversation = "\n".join([
        f"[{m.get('role', 'unknown')}] {m.get('content', '')[:500]}"
        for m in messages
    ])
    
    # Log session end
    brain.log_activity(
        activity_type="session_end",
        content=f"Session {session_id} ended after {duration_seconds}s with {len(messages)} messages",
        metadata={
            "session_id": session_id,
            "message_count": len(messages),
            "duration": duration_seconds,
        },
    )
    
    # Extract insights (async, but don't block)
    asyncio.create_task(_extract_session_insights(brain, conversation, session_id))


async def _extract_session_insights(brain, conversation: str, session_id: str):
    """Background task to extract insights from a session."""
    try:
        insights = await brain.extract_insights(conversation)
        
        if insights.get("_success"):
            # Store extracted facts
            for fact in insights.get("facts", []):
                await brain.link_memory(
                    content=fact,
                    category="000-reference",
                    metadata={"source": session_id, "type": "fact"},
                )
                
            # Store preferences
            for pref in insights.get("preferences", []):
                await brain.link_memory(
                    content=pref,
                    category="300-personal",
                    metadata={"source": session_id, "type": "preference"},
                )
                
            # Log action items to daily memory
            if insights.get("action_items"):
                _append_to_daily_memory(
                    "## Action Items (auto-extracted)\n" +
                    "\n".join(f"- [ ] {item}" for item in insights["action_items"])
                )
                
    except Exception as e:
        print(f"Error extracting session insights: {e}")


def _append_to_daily_memory(content: str):
    """Append content to today's memory file."""
    today = datetime.now().strftime("%Y-%m-%d")
    memory_file = Path("/workspace/clawd/memory") / f"{today}.md"
    
    with open(memory_file, "a") as f:
        f.write(f"\n\n{content}\n")


async def on_tool_call(
    tool_name: str,
    arguments: Dict[str, Any],
    result: Optional[str] = None,
):
    """
    Hook called when a tool is invoked.
    
    Args:
        tool_name: Name of the tool
        arguments: Tool arguments
        result: Tool result (if available)
    """
    brain = get_brain()
    
    # Log significant tool calls
    significant_tools = ["exec", "write", "message", "web_search", "browser"]
    
    if any(t in tool_name.lower() for t in significant_tools):
        brain.log_activity(
            activity_type="tool_call",
            content=f"Called {tool_name} with {len(arguments)} args",
            metadata={
                "tool": tool_name,
                "args_summary": str(arguments)[:200],
            },
        )


async def get_context_for_message(
    message: str,
    limit: int = 5,
) -> str:
    """
    Get relevant context for a user message.
    
    This can be called before generating a response to augment
    the context with relevant memories.
    
    Args:
        message: User's message
        limit: Max context items
        
    Returns:
        Formatted context string
    """
    brain = get_brain()
    
    if not brain._initialized:
        await brain.initialize()
        
    # Find related memories
    related = await brain.find_related(message, limit=limit)
    
    if not related:
        return ""
        
    context_lines = ["## Relevant Context from Memory", ""]
    
    for mem in related:
        if mem["score"] > 0.5:
            context_lines.append(f"- {mem['content'][:150]}")
            
    return "\n".join(context_lines)


def sync_log_activity(activity_type: str, content: str, metadata: Optional[Dict] = None):
    """
    Synchronous wrapper for logging activities.
    Use this when you can't use async.
    """
    brain = get_brain()
    brain.log_activity(activity_type, content, metadata)


# Quick access functions
log = sync_log_activity
