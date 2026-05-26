from __future__ import annotations

import logging
import os

from schemas.models import ModelTier, RoutingConfig
from schemas.state import AnalysisState

logger = logging.getLogger(__name__)


def select_tier(state: AnalysisState, config: RoutingConfig) -> ModelTier:
    """Select LLM tier based on divergence_score.

    PAID tier escalation is deferred to Phase 6 — falls back to Ollama for now.
    """
    if state.divergence_score > config.divergence_threshold:
        return ModelTier.OLLAMA
    return config.default_tier


async def call_llm(system_prompt: str, user_message: str, tier: ModelTier) -> str:
    """Route to appropriate LLM backend and return raw text response.

    HF_API failure falls back to Ollama automatically.
    PAID tier falls back to Ollama (Phase 6 will implement cap tracking).
    """
    if tier == ModelTier.HF_API:
        try:
            return await _call_hf(system_prompt, user_message)
        except Exception:
            logger.warning("HF API call failed, falling back to Ollama")
            return await _call_ollama(system_prompt, user_message)
    elif tier == ModelTier.OLLAMA:
        return await _call_ollama(system_prompt, user_message)
    else:  # ModelTier.PAID — deferred to Phase 6
        logger.warning("PAID tier not implemented in Phase 4, falling back to Ollama")
        return await _call_ollama(system_prompt, user_message)


async def _call_hf(system_prompt: str, user_message: str) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore[import-untyped]
    from langchain_huggingface import HuggingFaceEndpoint  # type: ignore[import-untyped]

    token = os.getenv("HF_API_TOKEN", "")
    model = os.getenv("HF_DEFAULT_MODEL", "HuggingFaceH4/zephyr-7b-beta")

    llm = HuggingFaceEndpoint(
        repo_id=model,
        huggingfacehub_api_token=token,
        task="text-generation",
        max_new_tokens=512,
    )
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
    response = await llm.ainvoke(messages)  # type: ignore[arg-type]
    content = getattr(response, "content", None)
    return str(content) if content is not None else str(response)


async def _call_ollama(system_prompt: str, user_message: str) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore[import-untyped]
    from langchain_ollama import ChatOllama  # type: ignore[import-untyped]

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_DEFAULT_MODEL", "phi3:mini")

    llm = ChatOllama(base_url=base_url, model=model)
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
    response = await llm.ainvoke(messages)
    return str(response.content)
