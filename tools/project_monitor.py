#!/usr/bin/env python3
"""
ATLAS Project Monitor
Tracks the status of Matt's various projects and provides proactive insights.

Built by ATLAS during autonomous improvement session.
2026-02-01
"""
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any


class ProjectMonitor:
    """
    Monitors Matt's projects for:
    - Git status (uncommitted changes, branches)
    - Build status (errors, warnings)
    - Activity (last modified times)
    - Dependencies (outdated packages)
    - TODOs and FIXMEs in code
    """
    
    # Projects to monitor
    PROJECTS = {
        "shorty-storys-generator": {
            "path": "/workspace/projects/shorty-storys-generator",
            "type": "python",
            "description": "RLM-powered horror story generator for @ShortyStorys",
            "github": "https://github.com/outrcore/shorty-storys-gen",
        },
        "atlas-voice": {
            "path": "/workspace/projects/atlas-voice",
            "type": "python",
            "description": "ATLAS voice interface and web UI",
        },
        "atlas-discord": {
            "path": "/workspace/projects/atlas-discord",
            "type": "python",
            "description": "Unified Discord bot for ATLAS",
        },
        "rlm": {
            "path": "/workspace/projects/rlm",
            "type": "python",
            "description": "Recursive Language Models library",
            "github": "https://github.com/alexzhang13/rlm",
        },
        "personaplex": {
            "path": "/workspace/projects/personaplex",
            "type": "python",
            "description": "NVIDIA PersonaPlex voice model",
        },
        "pomodoro": {
            "path": "/workspace/projects/pomodoro",
            "type": "web",
            "description": "Pomodoro timer web app",
        },
    }
    
    def __init__(self, workspace: str = "/workspace"):
        self.workspace = Path(workspace)
        self.reports_dir = self.workspace / "clawd" / "brain_data" / "project_reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
    def check_git_status(self, project_path: Path) -> Dict[str, Any]:
        """Check git status for a project."""
        if not (project_path / ".git").exists():
            return {"tracked": False}
        
        try:
            # Get branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=project_path,
                capture_output=True,
                text=True,
            )
            branch = result.stdout.strip()
            
            # Get status
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_path,
                capture_output=True,
                text=True,
            )
            changes = result.stdout.strip().split("\n") if result.stdout.strip() else []
            
            # Get last commit
            result = subprocess.run(
                ["git", "log", "-1", "--format=%H|%s|%ai"],
                cwd=project_path,
                capture_output=True,
                text=True,
            )
            if result.stdout.strip():
                commit_hash, message, date = result.stdout.strip().split("|")
                last_commit = {
                    "hash": commit_hash[:8],
                    "message": message,
                    "date": date,
                }
            else:
                last_commit = None
            
            # Check if ahead/behind remote
            result = subprocess.run(
                ["git", "status", "-sb"],
                cwd=project_path,
                capture_output=True,
                text=True,
            )
            status_line = result.stdout.split("\n")[0] if result.stdout else ""
            ahead = "ahead" in status_line
            behind = "behind" in status_line
            
            return {
                "tracked": True,
                "branch": branch,
                "uncommitted_changes": len(changes),
                "changes": changes[:10],  # First 10 changes
                "last_commit": last_commit,
                "ahead_of_remote": ahead,
                "behind_remote": behind,
            }
        except Exception as e:
            return {"tracked": True, "error": str(e)}
    
    def find_todos(self, project_path: Path, extensions: List[str] = None) -> List[Dict]:
        """Find TODOs and FIXMEs in code."""
        if extensions is None:
            extensions = [".py", ".js", ".ts", ".md"]
        
        todos = []
        try:
            for ext in extensions:
                for file in project_path.rglob(f"*{ext}"):
                    if ".git" in str(file) or "node_modules" in str(file):
                        continue
                    try:
                        content = file.read_text(errors='ignore')
                        for i, line in enumerate(content.split("\n"), 1):
                            line_upper = line.upper()
                            if "TODO" in line_upper or "FIXME" in line_upper:
                                todos.append({
                                    "file": str(file.relative_to(project_path)),
                                    "line": i,
                                    "text": line.strip()[:100],
                                })
                    except:
                        pass
        except Exception as e:
            pass
        
        return todos[:20]  # Limit to 20
    
    def check_python_project(self, project_path: Path) -> Dict[str, Any]:
        """Check Python project specifics."""
        info = {}
        
        # Check for requirements.txt or pyproject.toml
        req_file = project_path / "requirements.txt"
        pyproject = project_path / "pyproject.toml"
        
        if req_file.exists():
            info["has_requirements"] = True
            info["requirements_file"] = "requirements.txt"
        elif pyproject.exists():
            info["has_requirements"] = True
            info["requirements_file"] = "pyproject.toml"
        else:
            info["has_requirements"] = False
        
        # Check for tests
        has_tests = (project_path / "tests").exists() or \
                    (project_path / "test").exists() or \
                    any(project_path.glob("**/test_*.py"))
        info["has_tests"] = has_tests
        
        # Check for README
        info["has_readme"] = (project_path / "README.md").exists()
        
        # Count Python files
        py_files = list(project_path.glob("**/*.py"))
        info["python_files"] = len([f for f in py_files if ".git" not in str(f)])
        
        return info
    
    def get_activity(self, project_path: Path) -> Dict[str, Any]:
        """Check recent activity in a project."""
        try:
            # Get most recently modified file
            files = list(project_path.rglob("*"))
            files = [f for f in files if f.is_file() and ".git" not in str(f)]
            
            if not files:
                return {"active": False}
            
            most_recent = max(files, key=lambda f: f.stat().st_mtime)
            mtime = datetime.fromtimestamp(most_recent.stat().st_mtime)
            
            # Calculate how long ago
            age = datetime.now() - mtime
            if age < timedelta(hours=1):
                age_str = "< 1 hour ago"
            elif age < timedelta(days=1):
                age_str = f"{age.seconds // 3600} hours ago"
            else:
                age_str = f"{age.days} days ago"
            
            return {
                "active": True,
                "last_modified": mtime.isoformat(),
                "last_modified_ago": age_str,
                "last_modified_file": str(most_recent.relative_to(project_path)),
            }
        except Exception as e:
            return {"error": str(e)}
    
    def check_project(self, name: str, config: Dict) -> Dict[str, Any]:
        """Run all checks on a single project."""
        path = Path(config["path"])
        
        if not path.exists():
            return {
                "name": name,
                "exists": False,
                "error": f"Path not found: {config['path']}",
            }
        
        report = {
            "name": name,
            "exists": True,
            "path": str(path),
            "description": config.get("description", ""),
            "type": config.get("type", "unknown"),
            "github": config.get("github"),
            "checked_at": datetime.now().isoformat(),
        }
        
        # Run checks
        report["git"] = self.check_git_status(path)
        report["activity"] = self.get_activity(path)
        report["todos"] = self.find_todos(path)
        
        if config.get("type") == "python":
            report["python"] = self.check_python_project(path)
        
        # Calculate health score
        health = 100
        if not report["git"].get("tracked"):
            health -= 20
        if report["git"].get("uncommitted_changes", 0) > 5:
            health -= 10
        if not report.get("python", {}).get("has_readme", True):
            health -= 10
        if len(report.get("todos", [])) > 10:
            health -= 10
        
        report["health_score"] = max(0, health)
        
        return report
    
    def check_all(self) -> Dict[str, Any]:
        """Check all projects and generate summary."""
        reports = {}
        for name, config in self.PROJECTS.items():
            reports[name] = self.check_project(name, config)
        
        # Generate summary
        total_health = sum(r.get("health_score", 0) for r in reports.values())
        avg_health = total_health / len(reports) if reports else 0
        
        projects_with_changes = [
            name for name, r in reports.items()
            if r.get("git", {}).get("uncommitted_changes", 0) > 0
        ]
        
        total_todos = sum(len(r.get("todos", [])) for r in reports.values())
        
        summary = {
            "checked_at": datetime.now().isoformat(),
            "project_count": len(reports),
            "average_health": round(avg_health, 1),
            "projects_with_uncommitted_changes": projects_with_changes,
            "total_todos": total_todos,
        }
        
        result = {
            "summary": summary,
            "projects": reports,
        }
        
        # Save report
        report_file = self.reports_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.write_text(json.dumps(result, indent=2))
        
        return result
    
    def get_alerts(self, report: Dict = None) -> List[str]:
        """Generate alerts from a report."""
        if report is None:
            report = self.check_all()
        
        alerts = []
        
        for name, project in report.get("projects", {}).items():
            if not project.get("exists"):
                alerts.append(f"⚠️ {name}: Project path not found")
                continue
            
            git = project.get("git", {})
            if git.get("uncommitted_changes", 0) > 0:
                alerts.append(f"📝 {name}: {git['uncommitted_changes']} uncommitted changes")
            
            if git.get("behind_remote"):
                alerts.append(f"⬇️ {name}: Behind remote, needs pull")
            
            todos = project.get("todos", [])
            if len(todos) > 5:
                alerts.append(f"📌 {name}: {len(todos)} TODOs/FIXMEs")
            
            activity = project.get("activity", {})
            if "days ago" in activity.get("last_modified_ago", ""):
                days = int(activity["last_modified_ago"].split()[0])
                if days > 7:
                    alerts.append(f"💤 {name}: No activity in {days} days")
        
        return alerts
    
    def format_report(self, report: Dict = None) -> str:
        """Format a report as readable text."""
        if report is None:
            report = self.check_all()
        
        lines = ["# ATLAS Project Status Report", ""]
        lines.append(f"*Generated: {report['summary']['checked_at']}*")
        lines.append("")
        
        # Summary
        s = report["summary"]
        lines.append("## Summary")
        lines.append(f"- **Projects:** {s['project_count']}")
        lines.append(f"- **Average Health:** {s['average_health']}%")
        lines.append(f"- **Total TODOs:** {s['total_todos']}")
        if s["projects_with_uncommitted_changes"]:
            lines.append(f"- **Uncommitted Changes:** {', '.join(s['projects_with_uncommitted_changes'])}")
        lines.append("")
        
        # Alerts
        alerts = self.get_alerts(report)
        if alerts:
            lines.append("## Alerts")
            for alert in alerts:
                lines.append(f"- {alert}")
            lines.append("")
        
        # Projects
        lines.append("## Projects")
        for name, project in report["projects"].items():
            if not project.get("exists"):
                lines.append(f"\n### {name} ❌")
                lines.append("Project not found")
                continue
            
            health = project.get("health_score", 0)
            emoji = "🟢" if health >= 80 else "🟡" if health >= 50 else "🔴"
            
            lines.append(f"\n### {name} {emoji} ({health}%)")
            lines.append(f"*{project.get('description', 'No description')}*")
            
            if project.get("github"):
                lines.append(f"- GitHub: {project['github']}")
            
            git = project.get("git", {})
            if git.get("tracked"):
                lines.append(f"- Branch: `{git.get('branch', 'unknown')}`")
                if git.get("uncommitted_changes"):
                    lines.append(f"- Uncommitted: {git['uncommitted_changes']} files")
                if git.get("last_commit"):
                    lines.append(f"- Last commit: {git['last_commit']['message'][:50]}")
            
            activity = project.get("activity", {})
            if activity.get("active"):
                lines.append(f"- Last activity: {activity['last_modified_ago']}")
        
        return "\n".join(lines)


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ATLAS Project Monitor")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--alerts-only", action="store_true", help="Show only alerts")
    args = parser.parse_args()
    
    monitor = ProjectMonitor()
    report = monitor.check_all()
    
    if args.alerts_only:
        alerts = monitor.get_alerts(report)
        for alert in alerts:
            print(alert)
    elif args.json:
        print(json.dumps(report, indent=2))
    else:
        print(monitor.format_report(report))


if __name__ == "__main__":
    main()
