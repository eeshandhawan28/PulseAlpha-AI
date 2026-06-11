from __future__ import annotations

import json
import logging
import os
from contextlib import nullcontext
from typing import Any

from schemas.models import ModelTier, RoutingConfig
from schemas.state import AnalysisState

logger = logging.getLogger(__name__)


# ── OpenInference semantic-convention keys ────────────────────────────────
_SPAN_KIND = "openinference.span.kind"
_INPUT_VALUE = "input.value"
_OUTPUT_VALUE = "output.value"
_MODEL_NAME = "llm.model_name"
_PROMPT_TOKENS = "llm.token_count.prompt"
_COMPLETE_TOKENS = "llm.token_count.completion"
_TOTAL_TOKENS = "llm.token_count.total"


def _llm_span(name: str) -> Any:
    """Return an OTEL span context manager typed as an LLM span, or nullcontext."""
    try:
        from opentelemetry import trace
        from opentelemetry.trace import SpanKind

        tracer = trace.get_tracer("pulsealpha.llm")
        return tracer.start_as_current_span(name, kind=SpanKind.CLIENT)
    except ImportError:
        return nullcontext()


def _set(span: Any, **kv: Any) -> None:
    try:
        for k, v in kv.items():
            span.set_attribute(k, v)
    except Exception:
        pass


def select_tier(state: AnalysisState, config: RoutingConfig) -> ModelTier:
    """Select LLM tier based on divergence_score."""
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
    from huggingface_hub import AsyncInferenceClient

    token = os.getenv("HF_API_TOKEN", "")
    model_name = os.getenv("HF_DEFAULT_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    with _llm_span("llm.hf_api") as span:
        _set(
            span,
            **{
                _SPAN_KIND: "LLM",
                _MODEL_NAME: model_name,
                _INPUT_VALUE: json.dumps(messages),
            },
        )
        client = AsyncInferenceClient(api_key=token)
        result = await client.chat_completion(
            model=model_name,
            messages=messages,
            max_tokens=512,
        )
        content = str(result.choices[0].message.content)

        # token counts (available when the API returns usage)
        usage = getattr(result, "usage", None)
        if usage:
            _set(
                span,
                **{
                    _PROMPT_TOKENS: getattr(usage, "prompt_tokens", 0),
                    _COMPLETE_TOKENS: getattr(usage, "completion_tokens", 0),
                    _TOTAL_TOKENS: getattr(usage, "total_tokens", 0),
                },
            )

        _set(span, **{_OUTPUT_VALUE: content})
        return content


async def _call_ollama(system_prompt: str, user_message: str) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_ollama import ChatOllama

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name = os.getenv("OLLAMA_DEFAULT_MODEL", "phi3:mini")
    messages_payload = json.dumps(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]
    )

    with _llm_span("llm.ollama") as span:
        _set(
            span,
            **{
                _SPAN_KIND: "LLM",
                _MODEL_NAME: model_name,
                _INPUT_VALUE: messages_payload,
            },
        )
        llm = ChatOllama(base_url=base_url, model=model_name)
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
        response = await llm.ainvoke(messages)
        content = str(response.content)

        # token counts from Ollama response metadata
        meta = getattr(response, "response_metadata", {}) or {}
        usage = getattr(response, "usage_metadata", None)
        if usage:
            _set(
                span,
                **{
                    _PROMPT_TOKENS: getattr(usage, "input_tokens", 0),
                    _COMPLETE_TOKENS: getattr(usage, "output_tokens", 0),
                    _TOTAL_TOKENS: getattr(usage, "total_tokens", 0),
                },
            )
        elif meta:
            prompt_eval = meta.get("prompt_eval_count", 0) or 0
            eval_count = meta.get("eval_count", 0) or 0
            _set(
                span,
                **{
                    _PROMPT_TOKENS: prompt_eval,
                    _COMPLETE_TOKENS: eval_count,
                    _TOTAL_TOKENS: prompt_eval + eval_count,
                },
            )

        _set(span, **{_OUTPUT_VALUE: content})
        return content
