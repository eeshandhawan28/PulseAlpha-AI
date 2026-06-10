from __future__ import annotations

from schemas.report import EvidenceBlock
from schemas.state import Citation

_DEFAULT_THRESHOLD = 0.5
_LOW_CONFIDENCE_SUFFIX = " ⚠ low-confidence source"


def apply_confidence_flags(
    citations: list[Citation],
    blocks: dict[str, EvidenceBlock],
    threshold: float = _DEFAULT_THRESHOLD,
) -> list[Citation]:
    """Return a new list of Citations with low-confidence sources flagged.

    For each citation where blocks[source].confidence < threshold,
    appends ' ⚠ low-confidence source' to citation.claim.
    Citations referencing unknown blocks are left unchanged.
    Original citations are not mutated.
    """
    result: list[Citation] = []
    for citation in citations:
        block = blocks.get(citation.source)
        if block is not None and block.confidence < threshold:
            flagged = citation.model_copy(update={"claim": citation.claim + _LOW_CONFIDENCE_SUFFIX})
            result.append(flagged)
        else:
            result.append(citation)
    return result
