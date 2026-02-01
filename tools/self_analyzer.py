#!/usr/bin/env python3
"""
ATLAS Self-Analyzer
Analyzes ATLAS's own codebase and capabilities to suggest improvements.

Built by ATLAS during autonomous improvement session.
2026-02-01
"""
import os
import sys
import json
import ast
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from collections import defaultdict


class SelfAnalyzer:
    """
    Analyze ATLAS's codebase to identify:
    - Code quality issues
    - Missing features
    - Integration opportunities
    - Performance bottlenecks
    - Documentation gaps
    """
    
    ATLAS_PATHS = {
        "brain": "/workspace/clawd/brain",
        "tools": "/workspace/clawd/tools",
        "scripts": "/workspace/clawd/scripts",
        "knowledge": "/workspace/clawd/knowledge",
        "skills": "/workspace/Jarvis/skills",
        "projects": "/workspace/projects",
    }
    
    CAPABILITY_CHECKLIST = {
        "memory": {
            "short_term": "Activity logging for conversations",
            "long_term": "MEMORY.md and daily notes",
            "semantic": "Vector DB semantic search",
            "extraction": "Insight extraction from conversations",
        },
        "reasoning": {
            "rlm": "Recursive Language Models integration",
            "planning": "Multi-step task planning",
            "reflection": "Self-reflection on outputs",
        },
        "perception": {
            "vision": "Image analysis",
            "voice": "Speech recognition",
            "screen": "Screen capture/analysis",
        },
        "action": {
            "code": "Write and execute code",
            "browse": "Web browsing",
            "message": "Send messages across platforms",
            "file": "File operations",
        },
        "proactive": {
            "heartbeat": "Periodic check-ins",
            "monitoring": "System/project monitoring",
            "suggestions": "Proactive suggestions",
        },
    }
    
    def __init__(self, workspace: str = "/workspace/clawd"):
        self.workspace = Path(workspace)
        self.analysis_dir = self.workspace / "brain_data" / "self_analysis"
        self.analysis_dir.mkdir(parents=True, exist_ok=True)
    
    def analyze_python_file(self, filepath: Path) -> Dict[str, Any]:
        """Analyze a single Python file."""
        try:
            content = filepath.read_text()
            tree = ast.parse(content)
        except Exception as e:
            return {"error": str(e)}
        
        analysis = {
            "path": str(filepath),
            "lines": len(content.split("\n")),
            "functions": [],
            "classes": [],
            "imports": [],
            "todos": [],
            "complexity_hints": [],
        }
        
        # Analyze AST
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    "name": node.name,
                    "args": len(node.args.args),
                    "lines": node.end_lineno - node.lineno + 1 if hasattr(node, 'end_lineno') else 0,
                    "has_docstring": ast.get_docstring(node) is not None,
                }
                analysis["functions"].append(func_info)
                
                # Flag complex functions
                if func_info["lines"] > 50:
                    analysis["complexity_hints"].append(
                        f"Function '{node.name}' is {func_info['lines']} lines (consider splitting)"
                    )
                if func_info["args"] > 5:
                    analysis["complexity_hints"].append(
                        f"Function '{node.name}' has {func_info['args']} args (consider refactoring)"
                    )
                    
            elif isinstance(node, ast.ClassDef):
                class_info = {
                    "name": node.name,
                    "methods": len([n for n in node.body if isinstance(n, ast.FunctionDef)]),
                    "has_docstring": ast.get_docstring(node) is not None,
                }
                analysis["classes"].append(class_info)
                
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis["imports"].append(alias.name)
                else:
                    analysis["imports"].append(node.module or "")
        
        # Find TODOs
        for i, line in enumerate(content.split("\n"), 1):
            if "TODO" in line.upper() or "FIXME" in line.upper():
                analysis["todos"].append({"line": i, "text": line.strip()[:80]})
        
        # Calculate metrics
        analysis["metrics"] = {
            "function_count": len(analysis["functions"]),
            "class_count": len(analysis["classes"]),
            "avg_function_size": sum(f["lines"] for f in analysis["functions"]) / max(1, len(analysis["functions"])),
            "docstring_coverage": sum(1 for f in analysis["functions"] if f["has_docstring"]) / max(1, len(analysis["functions"])),
            "todo_count": len(analysis["todos"]),
        }
        
        return analysis
    
    def analyze_directory(self, path: Path) -> Dict[str, Any]:
        """Analyze all Python files in a directory."""
        if not path.exists():
            return {"error": f"Path not found: {path}"}
        
        files = list(path.rglob("*.py"))
        files = [f for f in files if "__pycache__" not in str(f)]
        
        analysis = {
            "path": str(path),
            "file_count": len(files),
            "files": {},
            "aggregate": {
                "total_lines": 0,
                "total_functions": 0,
                "total_classes": 0,
                "total_todos": 0,
                "complexity_issues": [],
            },
        }
        
        for file in files:
            file_analysis = self.analyze_python_file(file)
            rel_path = str(file.relative_to(path))
            analysis["files"][rel_path] = file_analysis
            
            if "error" not in file_analysis:
                analysis["aggregate"]["total_lines"] += file_analysis["lines"]
                analysis["aggregate"]["total_functions"] += file_analysis["metrics"]["function_count"]
                analysis["aggregate"]["total_classes"] += file_analysis["metrics"]["class_count"]
                analysis["aggregate"]["total_todos"] += file_analysis["metrics"]["todo_count"]
                analysis["aggregate"]["complexity_issues"].extend(
                    [f"{rel_path}: {hint}" for hint in file_analysis.get("complexity_hints", [])]
                )
        
        return analysis
    
    def check_capabilities(self) -> Dict[str, Any]:
        """Check which capabilities ATLAS has."""
        status = {}
        
        for category, capabilities in self.CAPABILITY_CHECKLIST.items():
            status[category] = {}
            for cap_id, description in capabilities.items():
                # Check if capability exists based on code presence
                exists = self._check_capability_exists(cap_id)
                status[category][cap_id] = {
                    "description": description,
                    "exists": exists,
                    "status": "✅" if exists else "❌",
                }
        
        return status
    
    def _check_capability_exists(self, capability: str) -> bool:
        """Check if a specific capability exists."""
        checks = {
            "short_term": (self.workspace / "brain" / "activity.py").exists(),
            "long_term": (self.workspace / "MEMORY.md").exists(),
            "semantic": (self.workspace / "brain" / "linker.py").exists(),
            "extraction": (self.workspace / "brain" / "extractor.py").exists(),
            "rlm": (self.workspace / "brain" / "rlm_integration.py").exists(),
            "planning": (self.workspace / "brain" / "task_planner.py").exists(),
            "reflection": (self.workspace / "brain" / "reflection.py").exists(),
            "vision": True,  # OpenClaw built-in
            "voice": (Path("/workspace/projects/atlas-voice").exists()),
            "screen": True,  # OpenClaw built-in
            "code": True,  # exec tool
            "browse": True,  # browser tool
            "message": True,  # message tool
            "file": True,  # read/write tools
            "heartbeat": (self.workspace / "HEARTBEAT.md").exists(),
            "monitoring": (self.workspace / "tools" / "project_monitor.py").exists(),
            "suggestions": (self.workspace / "brain" / "suggester.py").exists(),
        }
        return checks.get(capability, False)
    
    def identify_improvements(self) -> List[Dict[str, Any]]:
        """Identify potential improvements."""
        improvements = []
        
        # Check capabilities
        caps = self.check_capabilities()
        for category, capabilities in caps.items():
            for cap_id, info in capabilities.items():
                if not info["exists"]:
                    improvements.append({
                        "type": "missing_capability",
                        "priority": "high" if category in ["reasoning", "proactive"] else "medium",
                        "title": f"Add {info['description']}",
                        "category": category,
                        "capability": cap_id,
                    })
        
        # Check code quality
        brain_analysis = self.analyze_directory(self.workspace / "brain")
        if "aggregate" in brain_analysis:
            for issue in brain_analysis["aggregate"]["complexity_issues"]:
                improvements.append({
                    "type": "code_quality",
                    "priority": "low",
                    "title": issue,
                    "category": "refactoring",
                })
            
            if brain_analysis["aggregate"]["total_todos"] > 5:
                improvements.append({
                    "type": "technical_debt",
                    "priority": "medium",
                    "title": f"Address {brain_analysis['aggregate']['total_todos']} TODOs in brain module",
                    "category": "cleanup",
                })
        
        # Check for integration opportunities
        available_skills = list((Path("/workspace/Jarvis/skills")).iterdir())
        skill_names = [s.name for s in available_skills if s.is_dir()]
        
        useful_unintegrated = [
            "sag",  # ElevenLabs TTS
            "spotify-player",  # Spotify control
            "github",  # GitHub integration
        ]
        
        for skill in useful_unintegrated:
            if skill in skill_names:
                improvements.append({
                    "type": "integration",
                    "priority": "medium",
                    "title": f"Integrate {skill} skill more deeply",
                    "category": "skills",
                })
        
        return improvements
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a full self-analysis report."""
        report = {
            "generated_at": datetime.now().isoformat(),
            "capabilities": self.check_capabilities(),
            "improvements": self.identify_improvements(),
            "code_analysis": {},
        }
        
        # Analyze key directories
        for name, path in self.ATLAS_PATHS.items():
            if name in ["brain", "tools", "scripts"]:
                report["code_analysis"][name] = self.analyze_directory(Path(path))
        
        # Calculate overall scores
        total_caps = 0
        existing_caps = 0
        for category, caps in report["capabilities"].items():
            for cap_id, info in caps.items():
                total_caps += 1
                if info["exists"]:
                    existing_caps += 1
        
        report["scores"] = {
            "capability_coverage": round(existing_caps / total_caps * 100, 1) if total_caps else 0,
            "improvement_count": len(report["improvements"]),
            "high_priority_improvements": len([i for i in report["improvements"] if i["priority"] == "high"]),
        }
        
        # Save report
        report_file = self.analysis_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.write_text(json.dumps(report, indent=2))
        
        return report
    
    def format_report(self, report: Dict = None) -> str:
        """Format report as readable markdown."""
        if report is None:
            report = self.generate_report()
        
        lines = [
            "# ATLAS Self-Analysis Report",
            f"*Generated: {report['generated_at']}*",
            "",
            "## Scores",
            f"- **Capability Coverage:** {report['scores']['capability_coverage']}%",
            f"- **Improvements Identified:** {report['scores']['improvement_count']}",
            f"- **High Priority:** {report['scores']['high_priority_improvements']}",
            "",
            "## Capabilities",
        ]
        
        for category, caps in report["capabilities"].items():
            lines.append(f"\n### {category.title()}")
            for cap_id, info in caps.items():
                lines.append(f"- {info['status']} {info['description']}")
        
        lines.append("\n## Recommended Improvements")
        
        # Group by priority
        by_priority = defaultdict(list)
        for imp in report["improvements"]:
            by_priority[imp["priority"]].append(imp)
        
        for priority in ["high", "medium", "low"]:
            if by_priority[priority]:
                emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}[priority]
                lines.append(f"\n### {emoji} {priority.title()} Priority")
                for imp in by_priority[priority]:
                    lines.append(f"- {imp['title']}")
        
        return "\n".join(lines)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="ATLAS Self-Analyzer")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--capabilities", action="store_true", help="Show only capabilities")
    parser.add_argument("--improvements", action="store_true", help="Show only improvements")
    args = parser.parse_args()
    
    analyzer = SelfAnalyzer()
    
    if args.capabilities:
        caps = analyzer.check_capabilities()
        if args.json:
            print(json.dumps(caps, indent=2))
        else:
            for cat, items in caps.items():
                print(f"\n{cat.upper()}")
                for cap_id, info in items.items():
                    print(f"  {info['status']} {info['description']}")
    elif args.improvements:
        improvements = analyzer.identify_improvements()
        if args.json:
            print(json.dumps(improvements, indent=2))
        else:
            for imp in improvements:
                print(f"[{imp['priority'].upper()}] {imp['title']}")
    else:
        report = analyzer.generate_report()
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(analyzer.format_report(report))


if __name__ == "__main__":
    main()
