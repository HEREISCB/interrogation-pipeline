"""Multi-field fuzzy dedup. Mirrors handoff Section 7.2."""

from interrogation_pipeline.dedup.fuzzy import (
    CaseLike,
    is_duplicate,
    parse_state,
    parse_year,
    similarity,
)

__all__ = ["CaseLike", "is_duplicate", "similarity", "parse_state", "parse_year"]
