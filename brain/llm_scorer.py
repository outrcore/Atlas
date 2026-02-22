#!/usr/bin/env python3
"""
ATLAS Brain v2 - Phase 2: LLM-Based Memory Scoring
===================================================
Uses Claude to intelligently evaluate memory importance instead of
simple keyword matching. Much smarter categorization and scoring.

Research basis:
- Prompt-based scoring (0-10 scale)
- Context-aware importance evaluation
- Emotional impact assessment
- Utility and relevance ranking
"""

import os
import json
import asyncio
import httpx
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class LLMScore:
    """Result of LLM-based memory evaluation."""
    importance: float  # 0.0 - 1.0
    emotion: float  # 0.0 - 1.0
    utility: float  # 0.0 - 1.0
    category: str
    summary: str  # One-line summary
    should_keep: bool
    reasoning: str
    entities: List[str]
    related_topics: List[str]


class LLMScorer:
    """
    Uses Claude via OpenClaw Gateway to score memories.
    
    Advantages over keyword matching:
    - Understands context and nuance
    - Can identify implicit importance
    - Better categorization
    - Extracts entities and relationships
    """
    
    def __init__(
        self,
        gateway_url: str = "http://localhost:4747",
        timeout: float = 30.0,
        batch_size: int = 5,  # Score this many at once to save API calls
    ):
        self.gateway_url = gateway_url
        self.timeout = timeout
        self.batch_size = batch_size
        
        # Scoring prompt template
        self.scoring_prompt = """You are a memory curator for an AI assistant named ATLAS.

Your job is to evaluate memories and decide what's worth keeping long-term.

CONTEXT:
- ATLAS serves the user
- ATLAS wakes up fresh each session, so persistent memory is crucial
- Memory space is limited - only keep what truly matters

EVALUATION CRITERIA:
1. IMPORTANCE (0-10): How significant is this information?
   - 10: Critical (credentials, major decisions, key preferences)
   - 7-9: High (lessons learned, project milestones, personal info)
   - 4-6: Medium (useful facts, minor events)
   - 1-3: Low (routine activities, trivial details)
   - 0: Noise (should discard)

2. EMOTIONAL WEIGHT (0-10): How emotionally significant?
   - High emotion = more memorable (positive or negative)

3. UTILITY (0-10): How likely to be useful in the future?
   - Will ATLAS need this information again?

4. CATEGORY: One of:
   - credential (API keys, passwords, tokens)
   - preference (likes, dislikes, opinions)
   - user_info (facts about the user)
   - decision (choices made, reasoning)
   - lesson (things learned, mistakes)
   - project (work on specific projects)
   - event (significant happenings)
   - fact (general useful information)
   - todo (action items, follow-ups)
   - discard (not worth keeping)

MEMORIES TO EVALUATE:
{memories}

Respond with a JSON array. For each memory:
{{
  "index": <0-based index>,
  "importance": <0-10>,
  "emotion": <0-10>,
  "utility": <0-10>,
  "category": "<category>",
  "summary": "<one-line summary, max 100 chars>",
  "should_keep": <true/false>,
  "reasoning": "<brief explanation>",
  "entities": ["<person>", "<project>", "<tool>", ...],
  "related_topics": ["<topic1>", "<topic2>", ...]
}}

Be strict - if in doubt, mark should_keep as false. Quality over quantity."""

    async def _call_gateway(self, prompt: str) -> Optional[str]:
        """
        Call Claude for LLM scoring.
        
        Tries multiple methods:
        1. OpenClaw Gateway API (if available)
        2. Direct Anthropic API (if ANTHROPIC_API_KEY set)
        3. Returns None (hybrid scorer falls back to heuristics)
        """
        # Method 1: Try OpenClaw Gateway
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.gateway_url}/v1/chat/completions",
                    json={
                        "model": "anthropic/claude-sonnet-4-6",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 4096,
                        "temperature": 0.3,
                    },
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
        except Exception:
            pass
        
        # Method 2: Try direct Anthropic API
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        json={
                            "model": "claude-sonnet-4-6",
                            "max_tokens": 4096,
                            "messages": [{"role": "user", "content": prompt}],
                        },
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json"
                        }
                    )
                    if response.status_code == 200:
                        data = response.json()
                        return data["content"][0]["text"]
            except Exception:
                pass
        
        # Method 3: LLM not available, HybridScorer will use heuristics
        # Silently fall back - don't spam logs
        return None

    def _parse_scores(self, response: str, count: int) -> List[Optional[LLMScore]]:
        """Parse LLM response into LLMScore objects."""
        scores = [None] * count
        
        try:
            # Find JSON array in response
            start = response.find('[')
            end = response.rfind(']') + 1
            
            if start == -1 or end == 0:
                print("[llm_scorer] No JSON array found in response")
                return scores
            
            json_str = response[start:end]
            items = json.loads(json_str)
            
            for item in items:
                idx = item.get("index", -1)
                if 0 <= idx < count:
                    scores[idx] = LLMScore(
                        importance=item.get("importance", 5) / 10.0,
                        emotion=item.get("emotion", 2) / 10.0,
                        utility=item.get("utility", 5) / 10.0,
                        category=item.get("category", "fact"),
                        summary=item.get("summary", "")[:100],
                        should_keep=item.get("should_keep", False),
                        reasoning=item.get("reasoning", ""),
                        entities=item.get("entities", [])[:10],
                        related_topics=item.get("related_topics", [])[:5],
                    )
                    
        except json.JSONDecodeError as e:
            print(f"[llm_scorer] JSON parse error: {e}")
        except Exception as e:
            print(f"[llm_scorer] Parse error: {e}")
            
        return scores

    async def score_memories(
        self, 
        memories: List[str],
        context: Optional[str] = None,
    ) -> List[Optional[LLMScore]]:
        """
        Score a list of memories using Claude.
        
        Args:
            memories: List of memory strings to evaluate
            context: Optional additional context
            
        Returns:
            List of LLMScore objects (None if scoring failed)
        """
        if not memories:
            return []
        
        all_scores: List[Optional[LLMScore]] = []
        
        # Process in batches to manage token usage
        for i in range(0, len(memories), self.batch_size):
            batch = memories[i:i + self.batch_size]
            
            # Format memories for prompt
            formatted = "\n\n".join(
                f"[Memory {j}]\n{mem}" 
                for j, mem in enumerate(batch)
            )
            
            prompt = self.scoring_prompt.format(memories=formatted)
            
            if context:
                prompt = f"ADDITIONAL CONTEXT:\n{context}\n\n{prompt}"
            
            response = await self._call_gateway(prompt)
            
            if response:
                batch_scores = self._parse_scores(response, len(batch))
                all_scores.extend(batch_scores)
            else:
                # If API fails, return None for this batch
                all_scores.extend([None] * len(batch))
            
            # Small delay between batches to avoid rate limiting
            if i + self.batch_size < len(memories):
                await asyncio.sleep(0.5)
        
        return all_scores

    async def score_single(
        self, 
        memory: str,
        context: Optional[str] = None,
    ) -> Optional[LLMScore]:
        """Score a single memory."""
        scores = await self.score_memories([memory], context)
        return scores[0] if scores else None


class HybridScorer:
    """
    Combines LLM scoring with fast heuristics.
    
    Strategy:
    1. Fast heuristic pre-filter (remove obvious noise)
    2. LLM scoring for borderline cases
    3. Combined weighted score for final ranking
    """
    
    def __init__(
        self,
        llm_weight: float = 0.7,  # How much to trust LLM vs heuristics
        use_llm_threshold: float = 0.4,  # Only call LLM if heuristic score is ambiguous
    ):
        self.llm_scorer = LLMScorer()
        self.llm_weight = llm_weight
        self.use_llm_threshold = use_llm_threshold
    
    def _quick_heuristic(self, memory: str) -> float:
        """Fast keyword-based scoring for pre-filtering."""
        score = 0.3  # Base score
        
        memory_lower = memory.lower()
        
        # High importance signals
        if any(x in memory_lower for x in [
            "api key", "token", "password", "secret", "credential",
            "important", "critical", "remember", "don't forget",
            "lesson", "learned", "mistake", "decision",
            "user wants", "user said", "user prefers",
            "goal", "objective", "milestone",
        ]):
            score = max(score, 0.8)
        
        # Medium importance signals
        elif any(x in memory_lower for x in [
            "built", "created", "implemented", "fixed", "completed",
            "discovered", "realized", "understood", "learned",
            "preference", "likes", "dislikes",
            "project", "feature", "update",
        ]):
            score = max(score, 0.6)
        
        # Low importance signals
        elif any(x in memory_lower for x in [
            "checking", "looking at", "running",
            "heartbeat", "status check",
            "no changes", "nothing new",
        ]):
            score = min(score, 0.2)
        
        # Length bonus (detailed = potentially important)
        if len(memory) > 300:
            score += 0.1
        
        return min(score, 1.0)
    
    async def score_with_fallback(
        self,
        memories: List[str],
        context: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Score memories with hybrid approach.
        
        Returns list of dicts with:
        - content: original memory
        - heuristic_score: fast score
        - llm_score: LLMScore object (if called)
        - final_score: weighted combination
        - category: from LLM or heuristic
        - should_keep: final decision
        """
        results = []
        
        # First pass: heuristic scoring
        heuristic_scores = [self._quick_heuristic(m) for m in memories]
        
        # Identify which need LLM scoring (ambiguous range)
        needs_llm = []
        needs_llm_indices = []
        
        for i, (mem, h_score) in enumerate(zip(memories, heuristic_scores)):
            if self.use_llm_threshold < h_score < 0.8:
                # Ambiguous - let LLM decide
                needs_llm.append(mem)
                needs_llm_indices.append(i)
        
        # Get LLM scores for ambiguous memories
        llm_scores: List[Optional[LLMScore]] = []
        if needs_llm:
            llm_scores = await self.llm_scorer.score_memories(needs_llm, context)
        
        # Combine scores
        llm_idx = 0
        for i, (mem, h_score) in enumerate(zip(memories, heuristic_scores)):
            result = {
                "content": mem,
                "heuristic_score": h_score,
                "llm_score": None,
                "final_score": h_score,
                "category": "fact",
                "should_keep": h_score >= 0.6,
            }
            
            if i in needs_llm_indices:
                llm_score = llm_scores[llm_idx] if llm_idx < len(llm_scores) else None
                llm_idx += 1
                
                if llm_score:
                    result["llm_score"] = asdict(llm_score)
                    
                    # Weighted combination
                    llm_combined = (
                        llm_score.importance * 0.5 +
                        llm_score.emotion * 0.25 +
                        llm_score.utility * 0.25
                    )
                    
                    result["final_score"] = (
                        self.llm_weight * llm_combined +
                        (1 - self.llm_weight) * h_score
                    )
                    result["category"] = llm_score.category
                    result["should_keep"] = llm_score.should_keep
            
            # Override: very high heuristic always keeps
            if h_score >= 0.8:
                result["should_keep"] = True
            # Override: very low heuristic always discards
            elif h_score <= 0.2:
                result["should_keep"] = False
            
            results.append(result)
        
        return results


async def test_scorer():
    """Test the LLM scorer."""
    test_memories = [
        "User's Perplexity API key is YOUR_PERPLEXITY_API_KEY",
        "Ran heartbeat check, everything normal.",
        "User has health goals the AI should support.",
        "Built the memory promotion system using human-like consolidation.",
        "Checked git status, no changes.",
        "LESSON LEARNED: Don't spawn too many agents at once, causes rate limiting.",
        "User has set performance goals for the AI.",
    ]
    
    print("Testing HybridScorer...\n")
    
    scorer = HybridScorer()
    results = await scorer.score_with_fallback(test_memories)
    
    for r in results:
        content = r["content"][:60] + "..." if len(r["content"]) > 60 else r["content"]
        print(f"Memory: {content}")
        print(f"  Heuristic: {r['heuristic_score']:.2f}")
        print(f"  Final: {r['final_score']:.2f}")
        print(f"  Category: {r['category']}")
        print(f"  Keep: {r['should_keep']}")
        if r['llm_score']:
            print(f"  LLM Summary: {r['llm_score']['summary']}")
        print()


if __name__ == "__main__":
    asyncio.run(test_scorer())
