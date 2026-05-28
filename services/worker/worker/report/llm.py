from __future__ import annotations

import logging
import os

from schemas.models import ModelTier

logger = logging.getLogger(__name__)


async def call_report_llm(prompt: str, system_prompt: str, tier: ModelTier) -> str:
    """Route report generation LLM call to HF/Ollama/PAID backend.

    HF_API failure falls back to Ollama. PAID falls back to Ollama (Phase 6).
    """
    if tier == ModelTier.HF_API:
        try:
            return await _call_hf(system_prompt, prompt)
        except Exception:
            logger.warning("HF API call failed for report, falling back to Ollama")
            return await _call_ollama(system_prompt, prompt)
    elif tier == ModelTier.OLLAMA:
        return await _call_ollama(system_prompt, prompt)
    else:  # ModelTier.PAID — deferred to Phase 6
        logger.warning("PAID tier not implemented in Phase 5, falling back to Ollama")
        return await _call_ollama(system_prompt, prompt)


async def _call_hf(system_prompt: str, user_message: str) -> str:
    from huggingface_hub import AsyncInferenceClient

    token = os.getenv("HF_API_TOKEN", "")
    model_name = os.getenv("HF_DEFAULT_MODEL", "Qwen/Qwen2.5-7B-Instruct")

    client = AsyncInferenceClient(api_key=token)
    result = await client.chat_completion(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=2048,
    )
    return str(result.choices[0].message.content)


async def _call_ollama(system_prompt: str, user_message: str) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_ollama import ChatOllama

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name = os.getenv("OLLAMA_DEFAULT_MODEL", "phi3:mini")

    llm = ChatOllama(base_url=base_url, model=model_name)
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
    response = await llm.ainvoke(messages)
    return str(response.content)
