"""Hand-curated jp-aliases→zh fixed glossary (standalone service)."""

from .fixed_glossary import (
    FixedGlossary,
    FixedGlossaryEntry,
    TalentUnit,
    _normalize_jp,
    filter_fixed_glossary,
    format_fixed_glossary_block,
    load_fixed_glossary,
)

__all__ = [
    "FixedGlossary",
    "FixedGlossaryEntry",
    "TalentUnit",
    "filter_fixed_glossary",
    "format_fixed_glossary_block",
    "load_fixed_glossary",
    "_normalize_jp",
]
