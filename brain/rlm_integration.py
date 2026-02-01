"""
RLM Integration for ATLAS Brain
Extends Brain with Recursive Language Model capabilities for handling
infinite context, deep analysis, and complex reasoning.

Built by ATLAS during autonomous improvement session.
2026-02-01
"""
import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Union

# Add RLM to path
sys.path.insert(0, '/workspace/projects/rlm')

try:
    from rlm import RLM
    from rlm.logger import RLMLogger
    RLM_AVAILABLE = True
except ImportError:
    RLM_AVAILABLE = False
    RLM = None
    RLMLogger = None


class RLMBrain:
    """
    RLM-powered extension for ATLAS Brain.
    
    Provides recursive language model capabilities:
    - Analyze infinitely long documents/conversations
    - Synthesize insights across many files
    - Deep recursive research on complex topics
    - Self-decomposing reasoning for hard problems
    """
    
    def __init__(
        self,
        workspace: str = "/workspace/clawd",
        model: str = "claude-sonnet-4-20250514",
        backend: str = "anthropic",
        verbose: bool = False,
        max_iterations: int = 30,
        max_depth: int = 2,
        log_dir: Optional[str] = None,
    ):
        if not RLM_AVAILABLE:
            raise ImportError(
                "RLM library not available. Ensure /workspace/projects/rlm is installed."
            )
        
        self.workspace = Path(workspace)
        self.model = model
        self.backend = backend
        self.verbose = verbose
        self.max_iterations = max_iterations
        self.max_depth = max_depth
        
        # Setup logging
        self.log_dir = Path(log_dir) if log_dir else self.workspace / "brain_data" / "rlm_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # API key
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        # RLM instances are created per-task for isolation
        self._rlm_cache = {}
        
    def _create_rlm(
        self,
        task_name: str = "default",
        persistent: bool = False,
    ) -> RLM:
        """Create an RLM instance configured for a specific task."""
        logger = RLMLogger(log_dir=str(self.log_dir / task_name))
        
        return RLM(
            backend=self.backend,
            backend_kwargs={
                "api_key": self.api_key,
                "model_name": self.model,
                "max_tokens": 8192,
            },
            environment="local",
            max_iterations=self.max_iterations,
            max_depth=self.max_depth,
            logger=logger,
            verbose=self.verbose,
            persistent=persistent,
        )
    
    def analyze_document(
        self,
        content: str,
        question: str,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a long document using RLM's recursive decomposition.
        
        Args:
            content: The document content (can be arbitrarily long)
            question: What to analyze/find in the document
            context: Optional additional context
            
        Returns:
            Dict with response, usage stats, and execution time
        """
        rlm = self._create_rlm("document_analysis")
        
        prompt = f"""You have access to a document that you need to analyze.

DOCUMENT:
```
{content}
```

{f'ADDITIONAL CONTEXT: {context}' if context else ''}

QUESTION: {question}

INSTRUCTIONS:
- If the document is too long to analyze at once, use recursive decomposition
- Break into sections, analyze each, then synthesize findings
- Be thorough but concise in your final answer
- Use code to process text if helpful (regex, counting, etc.)
"""
        
        try:
            result = rlm.completion(prompt, root_prompt=question)
            return {
                "success": True,
                "response": result.response,
                "usage": result.usage_summary.to_dict() if hasattr(result.usage_summary, 'to_dict') else {},
                "execution_time": result.execution_time,
                "model": result.root_model,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            rlm.close()
    
    def synthesize_memories(
        self,
        file_paths: List[str],
        question: str,
        max_chars_per_file: int = 50000,
    ) -> Dict[str, Any]:
        """
        Synthesize insights from multiple memory/knowledge files.
        
        Args:
            file_paths: List of file paths to analyze
            question: What to synthesize/find across files
            max_chars_per_file: Truncate files to this length
            
        Returns:
            Dict with synthesized insights
        """
        rlm = self._create_rlm("memory_synthesis")
        
        # Load files
        file_contents = []
        for path in file_paths:
            p = Path(path)
            if p.exists():
                content = p.read_text()[:max_chars_per_file]
                file_contents.append(f"=== FILE: {p.name} ===\n{content}\n")
        
        if not file_contents:
            return {"success": False, "error": "No valid files found"}
        
        all_content = "\n".join(file_contents)
        
        prompt = f"""You have access to multiple memory/knowledge files that you need to synthesize.

FILES:
```
{all_content}
```

SYNTHESIS QUESTION: {question}

INSTRUCTIONS:
- Analyze each file for relevant information
- Look for patterns, connections, and themes across files
- Use recursive decomposition if the content is too long
- Synthesize a coherent answer that draws from all sources
- Cite which files contain which information
"""
        
        try:
            result = rlm.completion(prompt, root_prompt=question)
            return {
                "success": True,
                "response": result.response,
                "files_analyzed": len(file_contents),
                "usage": result.usage_summary.to_dict() if hasattr(result.usage_summary, 'to_dict') else {},
                "execution_time": result.execution_time,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            rlm.close()
    
    def deep_research(
        self,
        topic: str,
        depth: str = "standard",
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Conduct deep recursive research on a topic.
        
        Args:
            topic: The topic to research
            depth: Research depth - "quick", "standard", or "deep"
            context: Optional context about why this research matters
            
        Returns:
            Dict with research findings
        """
        rlm = self._create_rlm("deep_research")
        
        depth_instructions = {
            "quick": """
                - Provide a concise overview in 2-3 paragraphs
                - Focus on the most important points
                - No need for exhaustive detail
            """,
            "standard": """
                - Provide a comprehensive analysis
                - Cover key aspects, implications, and connections
                - Use sub-calls to explore complex sub-topics
                - Synthesize into a clear, structured response
            """,
            "deep": """
                - Conduct exhaustive recursive research
                - Break the topic into subtopics, analyze each deeply
                - Consider multiple perspectives and edge cases
                - Explore historical context and future implications
                - Use maximum recursion depth for thorough exploration
                - Synthesize all findings into a comprehensive report
            """,
        }
        
        prompt = f"""RESEARCH TOPIC: {topic}

{f'CONTEXT: {context}' if context else ''}

RESEARCH DEPTH: {depth}

INSTRUCTIONS:
{depth_instructions.get(depth, depth_instructions["standard"])}

You have access to a Python REPL for calculations, data processing, or code analysis.
Use recursive sub-LM calls to explore complex sub-topics in depth.
Synthesize all findings into a well-structured final answer.
"""
        
        try:
            result = rlm.completion(prompt, root_prompt=f"Research: {topic}")
            return {
                "success": True,
                "topic": topic,
                "depth": depth,
                "response": result.response,
                "usage": result.usage_summary.to_dict() if hasattr(result.usage_summary, 'to_dict') else {},
                "execution_time": result.execution_time,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            rlm.close()
    
    def solve_problem(
        self,
        problem: str,
        approach: str = "divide_and_conquer",
    ) -> Dict[str, Any]:
        """
        Solve a complex problem using recursive decomposition.
        
        Args:
            problem: The problem to solve
            approach: "divide_and_conquer", "self_refine", or "pairwise"
            
        Returns:
            Dict with solution
        """
        rlm = self._create_rlm("problem_solving")
        
        approach_prompts = {
            "divide_and_conquer": """
                Use divide-and-conquer:
                1. Break the problem into independent sub-problems
                2. Solve each sub-problem recursively
                3. Combine solutions into final answer
            """,
            "self_refine": """
                Use iterative self-refinement:
                1. Generate initial solution
                2. Critique the solution
                3. Refine based on critique
                4. Repeat until satisfactory
            """,
            "pairwise": """
                Use pairwise comparison:
                1. Generate multiple candidate solutions
                2. Compare solutions pairwise
                3. Select and refine the best
            """,
        }
        
        prompt = f"""PROBLEM: {problem}

APPROACH: {approach}
{approach_prompts.get(approach, approach_prompts["divide_and_conquer"])}

Use the Python REPL for calculations or code.
Use recursive sub-calls for complex sub-problems.
Provide a clear, well-reasoned solution.
"""
        
        try:
            result = rlm.completion(prompt, root_prompt=problem[:500])
            return {
                "success": True,
                "problem": problem,
                "approach": approach,
                "solution": result.response,
                "usage": result.usage_summary.to_dict() if hasattr(result.usage_summary, 'to_dict') else {},
                "execution_time": result.execution_time,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            rlm.close()
    
    def analyze_conversation_history(
        self,
        history_path: str,
        question: str,
    ) -> Dict[str, Any]:
        """
        Analyze a long conversation history file.
        
        Args:
            history_path: Path to conversation history file
            question: What to find/analyze in the history
            
        Returns:
            Dict with analysis results
        """
        path = Path(history_path)
        if not path.exists():
            return {"success": False, "error": f"History file not found: {history_path}"}
        
        content = path.read_text()
        return self.analyze_document(
            content=content,
            question=question,
            context="This is a conversation history between a human and an AI assistant.",
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get RLM integration status."""
        return {
            "available": RLM_AVAILABLE,
            "model": self.model,
            "backend": self.backend,
            "max_iterations": self.max_iterations,
            "max_depth": self.max_depth,
            "log_dir": str(self.log_dir),
            "api_key_set": bool(self.api_key),
        }


# Convenience function for quick access
def create_rlm_brain(**kwargs) -> RLMBrain:
    """Create an RLMBrain instance with default settings."""
    return RLMBrain(**kwargs)


# Test the integration
if __name__ == "__main__":
    print("🧠 Testing RLM Brain Integration...")
    
    try:
        brain = RLMBrain(verbose=True)
        print(f"Status: {brain.get_status()}")
        
        # Quick test
        result = brain.deep_research(
            "What are the key capabilities of Recursive Language Models?",
            depth="quick",
        )
        
        if result["success"]:
            print(f"\n✅ Research completed in {result['execution_time']:.2f}s")
            print(f"Response preview: {result['response'][:500]}...")
        else:
            print(f"\n❌ Error: {result['error']}")
            
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
