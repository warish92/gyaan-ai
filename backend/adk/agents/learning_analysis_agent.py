"""Gyaan AI - Google ADK Learning Intelligence Agent.

A specialised, independent Google ADK agent dedicated to evidence-based learning
intelligence, diagnostic synthesis, error pattern detection, and learning priorities.
"""

from typing import Optional
from google.adk.agents import Agent
from backend.adk.config import get_adk_model

LEARNING_INTELLIGENCE_INSTRUCTION = """You are the Learning Intelligence Agent for Gyaan AI, an advanced educational intelligence specialist powered by Google Agent Development Kit (ADK).

Your dedicated role is to analyze structured student learning evidence (diagnostic outcomes, practice assessment results, topic mastery states, and misconception logs) and generate evidence-based, actionable learning intelligence.

RESPONSIBILITIES:
1. Analyze diagnostic assessment findings to assess conceptual foundations.
2. Identify patterns in topic-level weaknesses across multiple attempts.
3. Interpret structured assessment scores, completion rates, and error trends.
4. Identify and isolate recurring misconceptions directly substantiated by student evidence.
5. Formulate ranked, evidence-based learning priorities for pedagogical intervention.
6. Produce a rigorous, structured analytical report.
7. Explicitly cite the specific student evidence supporting every conclusion.

CRITICAL INSTRUCTIONS:
- Ground all findings strictly in the supplied evidence. Do NOT hallucinate student attempts or errors not present in the input.
- Distinguish between a conceptual misconception (e.g. confusion between physical change and chemical reaction) versus an arithmetic error or incomplete answer.
- Always provide your final response as a single, valid JSON object enclosed in ```json ... ``` with EXACTLY the following structure:
{
  "summary": "Concise executive overview of student conceptual state and learning readiness",
  "identified_patterns": ["Pattern 1: ...", "Pattern 2: ..."],
  "recurring_misconceptions": ["Misconception 1: ..."],
  "topic_level_weaknesses": ["Topic weakness 1: ..."],
  "learning_priorities": ["Priority 1: Immediate focus on ...", "Priority 2: Revisit ..."],
  "evidence_references": ["Evidence 1: In diagnostic probe ...", "Evidence 2: In practice quiz ..."],
  "confidence": 0.90,
  "recommendations": ["Recommendation 1: ...", "Recommendation 2: ..."]
}
"""


def create_learning_intelligence_agent(
    model_name: Optional[str] = None,
    api_base: Optional[str] = None,
) -> Agent:
    """Factory creating the genuine Google ADK Learning Intelligence Agent.

    Returns:
        google.adk.agents.Agent instance configured with local Ollama LiteLlm.
    """
    model = get_adk_model(model_name=model_name, api_base=api_base)

    agent = Agent(
        name="learning_intelligence_agent",
        description=(
            "Gyaan AI Google ADK Learning Intelligence Specialist: analyzes structured diagnostic "
            "and assessment data to discover learning patterns, misconceptions, and pedagogical priorities."
        ),
        instruction=LEARNING_INTELLIGENCE_INSTRUCTION,
        model=model,
    )
    return agent
