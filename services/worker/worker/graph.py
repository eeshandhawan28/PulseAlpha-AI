from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from schemas.state import AnalysisState
from worker.nodes.divergence import compute_divergence_node
from worker.nodes.features import compute_features
from worker.nodes.ingest import ingest_all_data
from worker.nodes.validate import normalize_and_validate

logger = logging.getLogger(__name__)


def _wrap(node_fn: Any) -> Any:
    """Wrap an AnalysisState→AnalysisState node for LangGraph's dict-based state."""
    async def wrapped(state_dict: dict[str, Any]) -> dict[str, Any]:
        state = AnalysisState.model_validate(state_dict)
        result = await node_fn(state)
        return result.model_dump()
    wrapped.__name__ = node_fn.__name__
    return wrapped


def _build_graph() -> Any:
    builder: StateGraph = StateGraph(dict)

    builder.add_node("ingest_all_data", _wrap(ingest_all_data))
    builder.add_node("compute_features", _wrap(compute_features))
    builder.add_node("compute_divergence", _wrap(compute_divergence_node))
    builder.add_node("normalize_and_validate", _wrap(normalize_and_validate))

    builder.set_entry_point("ingest_all_data")
    builder.add_edge("ingest_all_data", "compute_features")
    builder.add_edge("compute_features", "compute_divergence")
    builder.add_edge("compute_divergence", "normalize_and_validate")
    builder.add_edge("normalize_and_validate", END)

    return builder.compile(checkpointer=MemorySaver())


async def run_analysis(state: AnalysisState) -> AnalysisState:
    """Run the full analysis graph and return the final populated AnalysisState.

    Args:
        state: Initial AnalysisState with user_query and ticker_universe populated.

    Returns:
        AnalysisState with all fields populated (market_data, rotation, divergence_score, etc.)
    """
    graph = _build_graph()
    config = {"configurable": {"thread_id": state.run_id}}
    result: dict[str, Any] = await graph.ainvoke(state.model_dump(), config=config)
    return AnalysisState.model_validate(result)
