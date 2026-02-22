#!/usr/bin/env python3
"""
ATLAS Threshold-Based Alerts
============================
Monitors for interesting patterns and sends alerts when thresholds are met.
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field

WORKSPACE = Path("/workspace/clawd")
ALERTS_STATE_FILE = WORKSPACE / "brain_data" / "alerts_state.json"


@dataclass
class AlertState:
    """Tracks what we've already alerted on."""
    last_alert_time: datetime = field(default_factory=datetime.now)
    alerted_items: List[str] = field(default_factory=list)
    alert_counts: Dict[str, int] = field(default_factory=dict)


class AlertMonitor:
    """Monitor for threshold-based alerts."""
    
    def __init__(self):
        self.workspace = WORKSPACE
        self.state_file = ALERTS_STATE_FILE
        self.state = self._load_state()
        
        # Thresholds
        self.staging_threshold = 10  # Alert when staging has 10+ new items
        self.error_threshold = 3     # Alert on 3+ errors in logs
        self.insight_threshold = 5   # Alert on 5+ significant insights
        self.cooldown_hours = 4      # Min hours between same alert type
        
    def _load_state(self) -> AlertState:
        """Load alert state from file."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                return AlertState(
                    last_alert_time=datetime.fromisoformat(data.get('last_alert_time', datetime.now().isoformat())),
                    alerted_items=data.get('alerted_items', []),
                    alert_counts=data.get('alert_counts', {})
                )
            except:
                pass
        return AlertState()
    
    def _save_state(self):
        """Save alert state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'last_alert_time': self.state.last_alert_time.isoformat(),
            'alerted_items': self.state.alerted_items[-100:],  # Keep last 100
            'alert_counts': self.state.alert_counts
        }
        self.state_file.write_text(json.dumps(data, indent=2))
    
    def _can_alert(self, alert_type: str) -> bool:
        """Check if we can send this type of alert (cooldown check)."""
        last_count = self.state.alert_counts.get(alert_type, 0)
        hours_since = (datetime.now() - self.state.last_alert_time).total_seconds() / 3600
        
        # Reset counts if it's been a while
        if hours_since > 24:
            self.state.alert_counts = {}
            return True
        
        # Check cooldown
        return hours_since >= self.cooldown_hours or last_count == 0
    
    def _record_alert(self, alert_type: str, item_id: str):
        """Record that we sent an alert."""
        self.state.last_alert_time = datetime.now()
        self.state.alerted_items.append(item_id)
        self.state.alert_counts[alert_type] = self.state.alert_counts.get(alert_type, 0) + 1
        self._save_state()
    
    def check_staging_overflow(self) -> Optional[Dict]:
        """Check if staging file has many unreviewed items."""
        staging_file = self.workspace / "memory" / "STAGING.md"
        
        if not staging_file.exists():
            return None
        
        content = staging_file.read_text()
        items = [l for l in content.split('\n') if l.startswith('- ')]
        
        if len(items) >= self.staging_threshold and self._can_alert('staging'):
            return {
                'type': 'staging_overflow',
                'count': len(items),
                'message': f"📋 Memory staging has {len(items)} items waiting for review. I'll curate these during the next maintenance cycle.",
                'priority': 'low'
            }
        
        return None
    
    def check_error_spike(self) -> Optional[Dict]:
        """Check for error spikes in recent activity."""
        today_log = self.workspace / "memory" / f"{datetime.now().strftime('%Y-%m-%d')}.md"
        
        if not today_log.exists():
            return None
        
        content = today_log.read_text().lower()
        error_keywords = ['error', 'failed', 'exception', 'crash', 'traceback']
        error_count = sum(content.count(kw) for kw in error_keywords)
        
        if error_count >= self.error_threshold and self._can_alert('errors'):
            return {
                'type': 'error_spike',
                'count': error_count,
                'message': f"⚠️ Detected {error_count} error mentions in today's logs. Might be worth investigating.",
                'priority': 'medium'
            }
        
        return None
    
    def check_significant_insights(self) -> Optional[Dict]:
        """Check for significant insights discovered."""
        staging_file = self.workspace / "memory" / "STAGING.md"
        
        if not staging_file.exists():
            return None
        
        content = staging_file.read_text()
        
        # Look for high-value patterns
        high_value_keywords = ['lesson', 'important', 'critical', 'discovered', 'breakthrough', 'realized']
        insights = []
        
        for line in content.split('\n'):
            if line.startswith('- '):
                if any(kw in line.lower() for kw in high_value_keywords):
                    item_id = hash(line)
                    if str(item_id) not in self.state.alerted_items:
                        insights.append(line[2:].strip()[:100])
        
        if len(insights) >= self.insight_threshold and self._can_alert('insights'):
            return {
                'type': 'significant_insights',
                'count': len(insights),
                'insights': insights[:5],
                'message': f"💡 Found {len(insights)} potentially significant insights:\n" + '\n'.join(f"  • {i}" for i in insights[:3]),
                'priority': 'medium'
            }
        
        return None
    
    def check_project_milestone(self) -> Optional[Dict]:
        """Check for project milestones (many commits, etc.)."""
        import subprocess
        
        projects_dir = Path("/workspace/projects")
        
        for project_dir in projects_dir.iterdir():
            if not (project_dir / '.git').exists():
                continue
            
            try:
                # Check today's commits
                result = subprocess.run(
                    ['git', 'log', '--since=1 day ago', '--oneline'],
                    cwd=project_dir,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    commits = [l for l in result.stdout.strip().split('\n') if l]
                    
                    # Alert on 10+ commits in a day (productive day!)
                    if len(commits) >= 10:
                        alert_id = f"{project_dir.name}-{datetime.now().strftime('%Y-%m-%d')}"
                        if alert_id not in self.state.alerted_items and self._can_alert('milestone'):
                            self._record_alert('milestone', alert_id)
                            return {
                                'type': 'project_milestone',
                                'project': project_dir.name,
                                'commits': len(commits),
                                'message': f"🎯 Productive day on {project_dir.name}! {len(commits)} commits today.",
                                'priority': 'low'
                            }
            except:
                pass
        
        return None
    
    def run_all_checks(self) -> List[Dict]:
        """Run all alert checks and return any triggered alerts."""
        alerts = []
        
        checks = [
            self.check_staging_overflow,
            self.check_error_spike,
            self.check_significant_insights,
            self.check_project_milestone,
        ]
        
        for check in checks:
            try:
                result = check()
                if result:
                    alerts.append(result)
            except Exception as e:
                print(f"[alerts] Check failed: {e}")
        
        return alerts


def run_alert_check() -> List[Dict]:
    """Run alert checks and return any alerts."""
    monitor = AlertMonitor()
    return monitor.run_all_checks()


if __name__ == "__main__":
    alerts = run_alert_check()
    if alerts:
        print(f"Found {len(alerts)} alerts:")
        for alert in alerts:
            print(f"  [{alert['priority']}] {alert['message']}")
    else:
        print("No alerts triggered.")
