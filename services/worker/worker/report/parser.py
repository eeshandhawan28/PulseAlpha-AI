from __future__ import annotations

import re

from schemas.report import EvidenceBlock
from schemas.state import Citation

_TAG_PATTERN = re.compile(r"\[SRC:([A-Z0-9_.]+):([a-zA-Z0-9_]+)\]")


def parse_citations(
    report_text: str, blocks: dict[str, EvidenceBlock]
) -> list[Citation]:
    """Extract [SRC:BLOCK:field] tags from report_text into Citation objects.

    Tags referencing unknown block names are silently dropped.
    Citation.claim is the full line containing the tag (with the tag removed).
    url and timestamp are always None in Phase 5.
    """
    citations: list[Citation] = []

    for line in report_text.splitlines():
        matches = _TAG_PATTERN.findall(line)
        if not matches:
            continue

        # Strip all tags from the line to get the clean claim text
        clean_line = _TAG_PATTERN.sub("", line).strip()

        for block_name, _field in matches:
            if block_name not in blocks:
                continue
            citations.append(
                Citation(
                    claim=clean_line,
                    source=block_name,
                    url=None,
                    timestamp=None,
                )
            )

    return citations
