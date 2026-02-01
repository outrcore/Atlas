"""
Activity Logger - Captures and manages all activities/conversations.
"""
import os
import json
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any


class ActivityLogger:
    """
    Logs and manages activities (conversations, actions, events).
    
    Activities are stored as JSONL files organized by date.
    """
    
    def __init__(self, activity_dir: Path):
        self.activity_dir = Path(activity_dir)
        self.activity_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache of recent activities
        self._recent_cache: List[Dict] = []
        self._processed_ids: set = set()
        
        # Load processed IDs
        self._load_processed_ids()
        
    def _get_log_path(self, date: Optional[datetime] = None) -> Path:
        """Get the log file path for a given date."""
        date = date or datetime.now()
        return self.activity_dir / f"{date.strftime('%Y-%m-%d')}.jsonl"
        
    def _load_processed_ids(self):
        """Load set of processed activity IDs."""
        processed_file = self.activity_dir / "processed.json"
        if processed_file.exists():
            self._processed_ids = set(json.loads(processed_file.read_text()))
            
    def _save_processed_ids(self):
        """Save processed activity IDs."""
        processed_file = self.activity_dir / "processed.json"
        processed_file.write_text(json.dumps(list(self._processed_ids)))
        
    def log(
        self,
        activity_type: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Log an activity.
        
        Args:
            activity_type: Type (conversation, action, observation, decision, etc.)
            content: The content/text
            metadata: Optional additional data
            
        Returns:
            Activity ID
        """
        activity_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now()
        
        activity = {
            "id": activity_id,
            "type": activity_type,
            "content": content,
            "metadata": metadata or {},
            "timestamp": timestamp.isoformat(),
        }
        
        # Write to daily log file
        log_path = self._get_log_path(timestamp)
        with open(log_path, "a") as f:
            f.write(json.dumps(activity) + "\n")
            
        # Add to cache
        self._recent_cache.append(activity)
        
        # Trim cache if too large
        if len(self._recent_cache) > 1000:
            self._recent_cache = self._recent_cache[-500:]
            
        return activity_id
        
    def load_recent(self, days: int = 7):
        """Load recent activities into cache."""
        self._recent_cache = []
        
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            log_path = self._get_log_path(date)
            
            if log_path.exists():
                with open(log_path, "r") as f:
                    for line in f:
                        if line.strip():
                            self._recent_cache.append(json.loads(line))
                            
        # Sort by timestamp
        self._recent_cache.sort(key=lambda x: x["timestamp"])
        
    def get_recent(self, hours: int = 24) -> List[Dict]:
        """Get activities from the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()
        
        return [
            a for a in self._recent_cache
            if a["timestamp"] >= cutoff_str
        ]
        
    def get_unprocessed(self) -> List[Dict]:
        """Get activities that haven't been processed yet."""
        return [
            a for a in self._recent_cache
            if a["id"] not in self._processed_ids
        ]
        
    def mark_processed(self, activity_id: str):
        """Mark an activity as processed."""
        self._processed_ids.add(activity_id)
        self._save_processed_ids()
        
    def get_by_type(self, activity_type: str, limit: int = 50) -> List[Dict]:
        """Get activities of a specific type."""
        matching = [
            a for a in reversed(self._recent_cache)
            if a["type"] == activity_type
        ]
        return matching[:limit]
        
    def search(self, query: str, limit: int = 20) -> List[Dict]:
        """Simple text search in activities."""
        query_lower = query.lower()
        matching = [
            a for a in reversed(self._recent_cache)
            if query_lower in a["content"].lower()
        ]
        return matching[:limit]
        
    def count(self) -> int:
        """Get total activity count in cache."""
        return len(self._recent_cache)
        
    def cleanup(self, days: int = 30):
        """Remove activity logs older than N days."""
        cutoff = datetime.now() - timedelta(days=days)
        
        for log_file in self.activity_dir.glob("*.jsonl"):
            try:
                file_date = datetime.strptime(log_file.stem, "%Y-%m-%d")
                if file_date < cutoff:
                    log_file.unlink()
            except ValueError:
                pass  # Skip files that don't match date format
                
    def get_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get a summary of recent activities."""
        recent = self.get_recent(hours)
        
        by_type = {}
        for a in recent:
            t = a["type"]
            by_type[t] = by_type.get(t, 0) + 1
            
        return {
            "total": len(recent),
            "by_type": by_type,
            "hours_covered": hours,
            "oldest": recent[0]["timestamp"] if recent else None,
            "newest": recent[-1]["timestamp"] if recent else None,
        }
        
    def export_for_analysis(self, hours: int = 24) -> str:
        """Export recent activities as formatted text for Claude analysis."""
        recent = self.get_recent(hours)
        
        lines = [f"# Activity Log (Last {hours} hours)", ""]
        
        for a in recent:
            ts = a["timestamp"][:16].replace("T", " ")
            lines.append(f"[{ts}] {a['type'].upper()}")
            lines.append(a["content"][:500])  # Truncate long content
            lines.append("")
            
        return "\n".join(lines)
