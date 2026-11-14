# Google Agent Development Kit (ADK) Module

This module integrates Google's **Agent Development Kit (ADK)** into Gyaan AI as a genuine second agentic framework alongside the existing CrewAI architecture.

## Architecture

- **`config.py`**: Model configuration and endpoint parameters for local Ollama (`qwen2.5:3b` at `http://127.0.0.1:11434` via `LiteLlm`).
- **`agents/learning_analysis_agent.py`**: The canonical Google ADK **Learning Intelligence Agent** (`google.adk.agents.Agent`).
- **`services/adk_runner.py`**: Orchestrates `google.adk.runners.Runner`, `InMemorySessionService`, per-student session isolation, evidence formatting, and structured output parsing.
- **`schemas/adk_messages.py`**: Validated Pydantic contracts for learning intelligence requests, diagnostic evidence, assessment evidence, and analytical responses.
- **`api.py`**: FastAPI router exposing `/api/v1/adk/health` and `/api/v1/adk/learning-analysis`.

## Role Separation

- **CrewAI**: Remains responsible for the active classroom workflows (Teacher Agent, Diagnostic Agent, Curriculum Agent, Resource Agent, Assessment Agent, Progress Agent, Mentor Agent, and Orchestrator).
- **Google ADK**: Provides specialized higher-order learning intelligence, pattern discovery, cross-assessment analysis, and misconception synthesis.
