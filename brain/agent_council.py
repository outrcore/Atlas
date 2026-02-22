#!/usr/bin/env python3
"""
ATLAS Brain v2 - Phase 4: Agent Council
========================================
Multi-agent debate system for memory curation decisions.

Inspired by:
- Multi-Agent Debate (MAD) frameworks
- Constitutional AI debate principles
- Diverse agent perspectives

Architecture:
- 3-5 agents with different "personalities"
- Each argues for/against keeping memories
- Voting + judge for final decision
- Quality control through adversarial review
"""

import os
import sys
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime


class AgentRole(Enum):
    """Different agent perspectives for memory curation."""
    ARCHIVIST = "archivist"      # Wants to keep everything
    MINIMALIST = "minimalist"    # Aggressive pruning
    ANALYST = "analyst"          # Looks for patterns
    GUARDIAN = "guardian"        # Protects sensitive info
    JUDGE = "judge"              # Final arbiter


@dataclass
class AgentVote:
    """An agent's vote on a memory."""
    agent_role: AgentRole
    should_keep: bool
    confidence: float  # 0.0 - 1.0
    reasoning: str
    suggested_category: str
    importance_score: float


@dataclass
class DebateRound:
    """One round of agent debate."""
    round_number: int
    votes: List[AgentVote]
    consensus: Optional[bool] = None
    agreement_level: float = 0.0


@dataclass
class CouncilDecision:
    """Final decision from the agent council."""
    memory_content: str
    should_keep: bool
    confidence: float
    category: str
    importance: float
    reasoning: str
    vote_breakdown: Dict[str, bool]
    debate_rounds: int


class Agent:
    """
    An agent with a specific perspective on memory curation.
    
    Each agent has:
    - A role/personality
    - Evaluation criteria
    - Voting logic
    """
    
    def __init__(self, role: AgentRole):
        self.role = role
        self.criteria = self._get_criteria()
    
    def _get_criteria(self) -> Dict[str, Any]:
        """Get evaluation criteria based on role."""
        criteria = {
            AgentRole.ARCHIVIST: {
                "bias": 0.3,  # Positive bias toward keeping
                "threshold": 0.3,  # Low bar for keeping
                "keywords_keep": [
                    "learned", "discovered", "created", "built", "decision",
                    "user", "preference", "important", "remember", "note",
                ],
                "keywords_discard": [],
                "description": "Preserves information for future reference.",
            },
            AgentRole.MINIMALIST: {
                "bias": -0.3,  # Negative bias
                "threshold": 0.7,  # High bar for keeping
                "keywords_keep": [
                    "critical", "essential", "must", "never forget",
                    "api key", "password", "credential",
                ],
                "keywords_discard": [
                    "routine", "checking", "heartbeat", "status",
                    "nothing new", "no changes",
                ],
                "description": "Keeps only what's truly essential.",
            },
            AgentRole.ANALYST: {
                "bias": 0.0,  # Neutral
                "threshold": 0.5,  # Medium bar
                "keywords_keep": [
                    "pattern", "trend", "correlation", "insight",
                    "lesson", "mistake", "success", "failure",
                ],
                "keywords_discard": [
                    "random", "one-off", "temporary",
                ],
                "description": "Identifies patterns and insights worth preserving.",
            },
            AgentRole.GUARDIAN: {
                "bias": 0.1,  # Slight positive bias for safety
                "threshold": 0.4,
                "keywords_keep": [
                    "security", "private", "sensitive", "personal",
                    "api key", "token", "password", "secret",
                    "health", "medical", "financial",
                ],
                "keywords_discard": [],
                "description": "Protects sensitive and personal information.",
            },
            AgentRole.JUDGE: {
                "bias": 0.0,
                "threshold": 0.5,
                "keywords_keep": [],
                "keywords_discard": [],
                "description": "Makes final decisions based on council debate.",
            },
        }
        return criteria[self.role]
    
    def evaluate(self, memory: str, context: Optional[str] = None) -> AgentVote:
        """
        Evaluate a memory from this agent's perspective.
        
        Uses heuristics by default. In production, could call LLM
        with role-specific prompt.
        """
        memory_lower = memory.lower()
        
        # Base score
        score = 0.5 + self.criteria["bias"]
        
        # Adjust for keywords
        for kw in self.criteria["keywords_keep"]:
            if kw in memory_lower:
                score += 0.15
        
        for kw in self.criteria["keywords_discard"]:
            if kw in memory_lower:
                score -= 0.2
        
        # Length consideration
        if len(memory) > 200:
            score += 0.05  # Longer = potentially more detailed
        elif len(memory) < 50:
            score -= 0.1  # Very short = likely trivial
        
        # Clamp score
        score = max(0.0, min(1.0, score))
        
        # Make decision
        should_keep = score >= self.criteria["threshold"]
        
        # Determine category
        category = self._categorize(memory)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(memory, should_keep, score)
        
        return AgentVote(
            agent_role=self.role,
            should_keep=should_keep,
            confidence=abs(score - 0.5) * 2,  # How far from uncertain
            reasoning=reasoning,
            suggested_category=category,
            importance_score=score,
        )
    
    def _categorize(self, memory: str) -> str:
        """Categorize the memory."""
        memory_lower = memory.lower()
        
        if any(x in memory_lower for x in ["api key", "token", "password", "secret"]):
            return "credential"
        elif any(x in memory_lower for x in ["lesson", "learned", "mistake"]):
            return "lesson"
        elif any(x in memory_lower for x in ["decided", "decision", "chose"]):
            return "decision"
        elif any(x in memory_lower for x in ["user", "prefers", "wants", "likes"]):
            return "preference"
        elif any(x in memory_lower for x in ["built", "created", "completed"]):
            return "achievement"
        else:
            return "fact"
    
    def _generate_reasoning(self, memory: str, keep: bool, score: float) -> str:
        """Generate reasoning for the vote."""
        role_name = self.role.value.capitalize()
        
        if self.role == AgentRole.ARCHIVIST:
            if keep:
                return f"{role_name}: This information may be useful for future reference."
            else:
                return f"{role_name}: Even I admit this is too trivial to keep."
        
        elif self.role == AgentRole.MINIMALIST:
            if keep:
                return f"{role_name}: This meets the high bar for essential information."
            else:
                return f"{role_name}: This is clutter that should be pruned."
        
        elif self.role == AgentRole.ANALYST:
            if keep:
                return f"{role_name}: This contains patterns or insights worth preserving."
            else:
                return f"{role_name}: No significant patterns or insights detected."
        
        elif self.role == AgentRole.GUARDIAN:
            if keep:
                return f"{role_name}: This contains sensitive or important personal info."
            else:
                return f"{role_name}: No sensitive information to protect here."
        
        else:
            return f"{role_name}: Score {score:.2f}"


class AgentCouncil:
    """
    Council of agents that debate memory curation decisions.
    
    Process:
    1. Each agent evaluates the memory independently
    2. Votes are tallied
    3. If no consensus, agents debate (future: LLM debate)
    4. Judge makes final decision if needed
    """
    
    def __init__(
        self,
        agents: Optional[List[AgentRole]] = None,
        consensus_threshold: float = 0.7,  # % agreement needed
        max_rounds: int = 2,
    ):
        if agents is None:
            agents = [
                AgentRole.ARCHIVIST,
                AgentRole.MINIMALIST,
                AgentRole.ANALYST,
                AgentRole.GUARDIAN,
            ]
        
        self.agents = [Agent(role) for role in agents]
        self.judge = Agent(AgentRole.JUDGE)
        self.consensus_threshold = consensus_threshold
        self.max_rounds = max_rounds
    
    def _calculate_consensus(self, votes: List[AgentVote]) -> Tuple[bool, float]:
        """Calculate if consensus was reached and agreement level."""
        if not votes:
            return False, 0.0
        
        keep_votes = sum(1 for v in votes if v.should_keep)
        total = len(votes)
        
        keep_ratio = keep_votes / total
        
        # Consensus is reached if > threshold agree on either side
        if keep_ratio >= self.consensus_threshold:
            return True, keep_ratio
        elif (1 - keep_ratio) >= self.consensus_threshold:
            return True, 1 - keep_ratio
        else:
            return False, max(keep_ratio, 1 - keep_ratio)
    
    def _weighted_decision(self, votes: List[AgentVote]) -> Tuple[bool, float]:
        """
        Make weighted decision based on votes.
        
        Weights:
        - Guardian: 1.5x for sensitive content
        - Analyst: 1.2x for pattern-related
        - Others: 1.0x
        """
        weighted_keep = 0.0
        weighted_discard = 0.0
        
        for vote in votes:
            weight = 1.0
            
            # Adjust weights based on role and content
            if vote.agent_role == AgentRole.GUARDIAN:
                if vote.suggested_category == "credential":
                    weight = 2.0  # Guardian's opinion matters most for credentials
                else:
                    weight = 1.2
            elif vote.agent_role == AgentRole.ANALYST:
                if vote.suggested_category in ["lesson", "decision"]:
                    weight = 1.3
            
            # Apply confidence as additional weight
            effective_weight = weight * (0.5 + vote.confidence * 0.5)
            
            if vote.should_keep:
                weighted_keep += effective_weight
            else:
                weighted_discard += effective_weight
        
        total = weighted_keep + weighted_discard
        if total == 0:
            return True, 0.5  # Default to keep if no votes
        
        confidence = abs(weighted_keep - weighted_discard) / total
        return weighted_keep > weighted_discard, confidence
    
    async def deliberate(
        self, 
        memory: str,
        context: Optional[str] = None,
    ) -> CouncilDecision:
        """
        Run the council deliberation process.
        
        Returns final decision with reasoning.
        """
        rounds: List[DebateRound] = []
        
        # Round 1: Initial votes
        votes = [agent.evaluate(memory, context) for agent in self.agents]
        consensus, agreement = self._calculate_consensus(votes)
        
        rounds.append(DebateRound(
            round_number=1,
            votes=votes,
            consensus=consensus,
            agreement_level=agreement,
        ))
        
        # If no consensus and more rounds allowed, could add LLM debate here
        # For now, we just use weighted voting
        
        # Final decision
        should_keep, confidence = self._weighted_decision(votes)
        
        # Get most common category
        categories = [v.suggested_category for v in votes]
        category = max(set(categories), key=categories.count)
        
        # Average importance
        importance = sum(v.importance_score for v in votes) / len(votes)
        
        # Compile reasoning
        reasonings = [f"- {v.reasoning}" for v in votes]
        combined_reasoning = "\n".join(reasonings)
        
        # Vote breakdown
        breakdown = {
            v.agent_role.value: v.should_keep
            for v in votes
        }
        
        return CouncilDecision(
            memory_content=memory[:200],
            should_keep=should_keep,
            confidence=confidence,
            category=category,
            importance=importance,
            reasoning=combined_reasoning,
            vote_breakdown=breakdown,
            debate_rounds=len(rounds),
        )
    
    async def batch_deliberate(
        self,
        memories: List[str],
        context: Optional[str] = None,
    ) -> List[CouncilDecision]:
        """Deliberate on multiple memories."""
        decisions = []
        for memory in memories:
            decision = await self.deliberate(memory, context)
            decisions.append(decision)
        return decisions


async def test_council():
    """Test the agent council."""
    print("🏛️ Testing Agent Council - Phase 4\n")
    
    test_memories = [
        "User's Perplexity API key is YOUR_PERPLEXITY_API_KEY",
        "Ran heartbeat check, everything normal.",
        "LESSON LEARNED: Don't spawn too many agents at once, causes rate limiting.",
        "User prefers a specific voice like Alfred from Batman.",
        "Checked git status, no changes.",
        "Built the memory promotion system using human-like consolidation hierarchy.",
        "Random thought about the weather.",
    ]
    
    council = AgentCouncil()
    
    print("Deliberating on memories...\n")
    print("-" * 70)
    
    for memory in test_memories:
        decision = await council.deliberate(memory)
        
        status = "✅ KEEP" if decision.should_keep else "❌ DISCARD"
        print(f"\n📝 Memory: {memory[:60]}...")
        print(f"   Decision: {status} (confidence: {decision.confidence:.0%})")
        print(f"   Category: {decision.category}")
        print(f"   Votes: {decision.vote_breakdown}")
    
    print("\n" + "-" * 70)
    print("\n✨ Council deliberation complete!")


if __name__ == "__main__":
    asyncio.run(test_council())
