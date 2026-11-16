"""Gyaan AI - Google Agent Development Kit (ADK) Configuration.

Centralizes all settings, model parameters, and local Ollama integrations
for Google ADK agents and runners.
"""

import os
from typing import Optional
from google.adk.models.lite_llm import LiteLlm

# Model and Endpoint Settings
DEFAULT_ADK_MODEL = "ollama_chat/qwen2.5:1.5b"
DEFAULT_OLLAMA_API_BASE = "http://127.0.0.1:11434"
DEFAULT_APP_NAME = "gyaan_ai_adk"
DEFAULT_TIMEOUT_SECONDS = 90
DEFAULT_TEMPERATURE = 0.2

ADK_MODEL_NAME = os.getenv("ADK_MODEL_NAME", DEFAULT_ADK_MODEL)
ADK_OLLAMA_API_BASE = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_API_BASE)
ADK_APP_NAME = os.getenv("ADK_APP_NAME", DEFAULT_APP_NAME)
ADK_TIMEOUT_SECONDS = int(os.getenv("ADK_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
ADK_TEMPERATURE = float(os.getenv("ADK_TEMPERATURE", str(DEFAULT_TEMPERATURE)))


def get_adk_model(
    model_name: Optional[str] = None,
    api_base: Optional[str] = None,
    temperature: Optional[float] = None,
) -> LiteLlm:
    """Factory creating a genuine Google ADK LiteLlm model pointing to local Ollama.

    Args:
        model_name: Model identifier (defaults to ollama_chat/qwen2.5:3b).
        api_base: Ollama HTTP endpoint (defaults to http://127.0.0.1:11434).
        temperature: Sampling temperature for deterministic analytical reasoning.

    Returns:
        Configured LiteLlm instance compatible with Google ADK agents and runners.
    """
    effective_model = model_name or ADK_MODEL_NAME
    effective_base = api_base or ADK_OLLAMA_API_BASE
    effective_temp = temperature if temperature is not None else ADK_TEMPERATURE

    return LiteLlm(
        model=effective_model,
        api_base=effective_base,
        temperature=effective_temp,
    )
