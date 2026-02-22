"""
Checkpointing System for Long-Running Agent Tasks

Provides persistent state storage for tasks that may be interrupted,
allowing seamless resumption from the last saved point.

Usage:
    from checkpoint import Checkpoint
    
    cp = Checkpoint("my-task-id")
    
    # Check for existing state
    if state := cp.load():
        print(f"Resuming from: {state['phase']}")
    else:
        print("Starting fresh")
    
    # Save progress periodically
    cp.save({"phase": "processing", "progress": 0.5, "items": [...]})
    
    # Clear on completion
    cp.clear()

Integration with orchestrate.py:
    - Pass checkpoint_id to spawned agents via context
    - Agents call cp.save() at natural breakpoints (e.g., after each phase)
    - On resume, use get_resume_prompt() to include state in agent context
    - Orchestrator can list_checkpoints() to show resumable tasks
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

# Default checkpoint directory
CHECKPOINT_DIR = Path("/workspace/clawd/checkpoints")


class Checkpoint:
    """
    Manages checkpoint state for a single task.
    
    Attributes:
        task_id: Unique identifier for the task
        filepath: Path to the checkpoint JSON file
    
    Example:
        cp = Checkpoint("research-123")
        cp.save({"phase": "gathering", "sources": ["url1", "url2"]})
        state = cp.load()  # Returns saved dict or None
        cp.clear()  # Remove after completion
    """
    
    def __init__(self, task_id: str, checkpoint_dir: Optional[Path] = None):
        """
        Initialize a checkpoint handler for a specific task.
        
        Args:
            task_id: Unique identifier for the task (used as filename)
            checkpoint_dir: Custom directory for checkpoints (default: /workspace/clawd/checkpoints)
        """
        self.task_id = task_id
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else CHECKPOINT_DIR
        self.filepath = self.checkpoint_dir / f"{task_id}.json"
    
    def save(self, state: dict[str, Any], phase: Optional[str] = None, 
             progress: Optional[float] = None) -> bool:
        """
        Save checkpoint state to disk.
        
        Args:
            state: Arbitrary state data to persist
            phase: Optional phase name (also extracted from state['phase'] if present)
            progress: Optional progress percentage 0.0-1.0 (also from state['progress'])
        
        Returns:
            True if saved successfully, False on error
        
        Example:
            cp.save({"phase": "analysis", "items_processed": 50, "total": 100})
            # Or with explicit phase/progress:
            cp.save({"data": [...]}, phase="downloading", progress=0.75)
        """
        try:
            # Ensure directory exists
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract phase and progress from state if not provided explicitly
            effective_phase = phase or state.get("phase", "unknown")
            effective_progress = progress if progress is not None else state.get("progress")
            
            checkpoint_data = {
                "task_id": self.task_id,
                "timestamp": datetime.utcnow().isoformat(),
                "phase": effective_phase,
                "progress": effective_progress,
                "state": state
            }
            
            # Write atomically (write to temp, then rename)
            temp_path = self.filepath.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(checkpoint_data, f, indent=2, default=str)
            temp_path.rename(self.filepath)
            
            return True
        except Exception as e:
            print(f"[Checkpoint] Error saving {self.task_id}: {e}")
            return False
    
    def load(self) -> Optional[dict[str, Any]]:
        """
        Load checkpoint state from disk.
        
        Returns:
            The saved state dict, or None if no checkpoint exists
        
        Example:
            if state := cp.load():
                print(f"Resuming from phase: {state['phase']}")
                items = state['state']['items_processed']
        """
        try:
            if not self.filepath.exists():
                return None
            
            with open(self.filepath, "r") as f:
                data = json.load(f)
            
            return data
        except Exception as e:
            print(f"[Checkpoint] Error loading {self.task_id}: {e}")
            return None
    
    def clear(self) -> bool:
        """
        Remove the checkpoint file (call after task completion).
        
        Returns:
            True if cleared successfully or didn't exist, False on error
        """
        try:
            if self.filepath.exists():
                self.filepath.unlink()
            return True
        except Exception as e:
            print(f"[Checkpoint] Error clearing {self.task_id}: {e}")
            return False
    
    def exists(self) -> bool:
        """Check if a checkpoint exists for this task."""
        return self.filepath.exists()
    
    def age_hours(self) -> Optional[float]:
        """
        Get the age of the checkpoint in hours.
        
        Returns:
            Hours since last save, or None if no checkpoint
        """
        data = self.load()
        if not data or "timestamp" not in data:
            return None
        
        try:
            saved_time = datetime.fromisoformat(data["timestamp"])
            age = datetime.utcnow() - saved_time
            return age.total_seconds() / 3600
        except:
            return None


def get_resume_prompt(task_id: str, checkpoint_dir: Optional[Path] = None) -> Optional[str]:
    """
    Generate a prompt that includes checkpoint state for resuming a task.
    
    Use this to inject checkpoint context when spawning an agent to resume work.
    
    Args:
        task_id: The task identifier to resume
        checkpoint_dir: Custom checkpoint directory
    
    Returns:
        A formatted prompt string with state info, or None if no checkpoint
    
    Example:
        if prompt := get_resume_prompt("research-123"):
            # Include in agent spawn context
            orchestrator.spawn(task=prompt)
    """
    cp = Checkpoint(task_id, checkpoint_dir)
    data = cp.load()
    
    if not data:
        return None
    
    state = data.get("state", {})
    phase = data.get("phase", "unknown")
    progress = data.get("progress")
    timestamp = data.get("timestamp", "unknown")
    
    # Calculate age
    age_str = ""
    if age := cp.age_hours():
        if age < 1:
            age_str = f" ({int(age * 60)} minutes ago)"
        else:
            age_str = f" ({age:.1f} hours ago)"
    
    progress_str = f" ({progress*100:.0f}% complete)" if progress is not None else ""
    
    prompt = f"""## Resuming Task: {task_id}

This task was previously started and has a checkpoint{age_str}.

**Last Phase:** {phase}{progress_str}
**Checkpoint Time:** {timestamp}

**Saved State:**
```json
{json.dumps(state, indent=2, default=str)}
```

Continue from where the task left off. Do not restart from the beginning.
"""
    return prompt


def list_checkpoints(checkpoint_dir: Optional[Path] = None) -> list[dict[str, Any]]:
    """
    List all active checkpoints with metadata.
    
    Returns:
        List of checkpoint info dicts with task_id, phase, progress, age_hours
    
    Example:
        for cp_info in list_checkpoints():
            print(f"{cp_info['task_id']}: {cp_info['phase']} ({cp_info['age_hours']:.1f}h old)")
    """
    dir_path = Path(checkpoint_dir) if checkpoint_dir else CHECKPOINT_DIR
    
    if not dir_path.exists():
        return []
    
    checkpoints = []
    for filepath in dir_path.glob("*.json"):
        task_id = filepath.stem
        cp = Checkpoint(task_id, dir_path)
        data = cp.load()
        
        if data:
            checkpoints.append({
                "task_id": task_id,
                "phase": data.get("phase", "unknown"),
                "progress": data.get("progress"),
                "timestamp": data.get("timestamp"),
                "age_hours": cp.age_hours(),
                "filepath": str(filepath)
            })
    
    # Sort by age (most recent first)
    checkpoints.sort(key=lambda x: x.get("age_hours") or 999)
    return checkpoints


def cleanup_old_checkpoints(max_age_hours: float = 24.0, 
                            checkpoint_dir: Optional[Path] = None,
                            dry_run: bool = False) -> list[str]:
    """
    Remove checkpoints older than max_age_hours.
    
    Args:
        max_age_hours: Maximum age before cleanup (default: 24 hours)
        checkpoint_dir: Custom checkpoint directory
        dry_run: If True, only report what would be deleted
    
    Returns:
        List of task_ids that were (or would be) deleted
    
    Example:
        # Preview what would be deleted
        old = cleanup_old_checkpoints(max_age_hours=12, dry_run=True)
        print(f"Would delete: {old}")
        
        # Actually delete
        deleted = cleanup_old_checkpoints(max_age_hours=12)
    """
    dir_path = Path(checkpoint_dir) if checkpoint_dir else CHECKPOINT_DIR
    
    if not dir_path.exists():
        return []
    
    deleted = []
    for filepath in dir_path.glob("*.json"):
        task_id = filepath.stem
        cp = Checkpoint(task_id, dir_path)
        age = cp.age_hours()
        
        if age is not None and age > max_age_hours:
            if not dry_run:
                cp.clear()
            deleted.append(task_id)
    
    return deleted


def get_or_create_checkpoint(task_id: str, initial_state: Optional[dict] = None) -> tuple[Checkpoint, Optional[dict]]:
    """
    Convenience function: get existing checkpoint or create new one.
    
    Args:
        task_id: Task identifier
        initial_state: State to save if no checkpoint exists
    
    Returns:
        Tuple of (Checkpoint instance, existing state or None)
    
    Example:
        cp, existing = get_or_create_checkpoint("my-task", {"phase": "init"})
        if existing:
            print(f"Resuming from {existing['phase']}")
        else:
            print("Starting fresh")
    """
    cp = Checkpoint(task_id)
    existing = cp.load()
    
    if not existing and initial_state:
        cp.save(initial_state)
    
    return cp, existing


# --- CLI Interface ---

if __name__ == "__main__":
    import sys
    
    def print_usage():
        print("""
Checkpoint CLI - Manage task checkpoints

Usage:
    python checkpoint.py list                    # List all checkpoints
    python checkpoint.py show <task_id>          # Show checkpoint details
    python checkpoint.py clear <task_id>         # Delete a checkpoint
    python checkpoint.py cleanup [hours=24]      # Remove old checkpoints
    python checkpoint.py cleanup --dry-run       # Preview cleanup
        """)
    
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "list":
        checkpoints = list_checkpoints()
        if not checkpoints:
            print("No active checkpoints.")
        else:
            print(f"{'Task ID':<30} {'Phase':<20} {'Progress':<10} {'Age':<10}")
            print("-" * 70)
            for cp in checkpoints:
                progress = f"{cp['progress']*100:.0f}%" if cp['progress'] else "-"
                age = f"{cp['age_hours']:.1f}h" if cp['age_hours'] else "-"
                print(f"{cp['task_id']:<30} {cp['phase']:<20} {progress:<10} {age:<10}")
    
    elif cmd == "show" and len(sys.argv) > 2:
        task_id = sys.argv[2]
        cp = Checkpoint(task_id)
        data = cp.load()
        if data:
            print(json.dumps(data, indent=2, default=str))
        else:
            print(f"No checkpoint found for: {task_id}")
    
    elif cmd == "clear" and len(sys.argv) > 2:
        task_id = sys.argv[2]
        cp = Checkpoint(task_id)
        if cp.clear():
            print(f"Cleared checkpoint: {task_id}")
        else:
            print(f"Failed to clear: {task_id}")
    
    elif cmd == "cleanup":
        dry_run = "--dry-run" in sys.argv
        hours = 24.0
        for arg in sys.argv[2:]:
            if arg.startswith("hours="):
                hours = float(arg.split("=")[1])
        
        deleted = cleanup_old_checkpoints(hours, dry_run=dry_run)
        action = "Would delete" if dry_run else "Deleted"
        if deleted:
            print(f"{action} {len(deleted)} checkpoint(s): {', '.join(deleted)}")
        else:
            print(f"No checkpoints older than {hours} hours.")
    
    elif cmd == "resume" and len(sys.argv) > 2:
        task_id = sys.argv[2]
        prompt = get_resume_prompt(task_id)
        if prompt:
            print(prompt)
        else:
            print(f"No checkpoint found for: {task_id}")
    
    else:
        print_usage()
