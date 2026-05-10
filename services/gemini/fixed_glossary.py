"""Hand-curated jp-aliases→zh fixed glossary, filtered to per-episode matches."""

import json
from pathlib import Path

from loguru import logger


FIXED_GLOSSARY_PATH = Path(__file__).parent / "fixed_glossary.json"

# An entry maps a list of JP source aliases (ASR may transcribe the same term
# in several forms) to a single ZH target.
FixedGlossaryEntry = tuple[list[str], str]


def load_fixed_glossary() -> list[FixedGlossaryEntry]:
    """Load and validate the fixed glossary file.

    Missing file → empty list (feature off). Malformed entries are skipped
    with a warning so a typo never breaks the whole pipeline.
    """
    if not FIXED_GLOSSARY_PATH.exists():
        logger.info(
            f"[fixed-glossary] File not found at {FIXED_GLOSSARY_PATH}, skipping"
        )
        return []
    try:
        raw = json.loads(FIXED_GLOSSARY_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"[fixed-glossary] Failed to parse {FIXED_GLOSSARY_PATH}: {e}")
        return []
    if not isinstance(raw, list):
        logger.warning(
            f"[fixed-glossary] Expected list at top level, got {type(raw).__name__}"
        )
        return []
    entries: list[FixedGlossaryEntry] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            logger.warning(f"[fixed-glossary] Skipping non-object entry #{i}: {entry!r}")
            continue
        jp = entry.get("jp")
        zh = entry.get("zh")
        if (
            not isinstance(jp, list)
            or not jp
            or not all(isinstance(a, str) and a for a in jp)
        ):
            logger.warning(
                f"[fixed-glossary] Skipping entry #{i} with bad 'jp' field: {entry!r}"
            )
            continue
        if not isinstance(zh, str) or not zh:
            logger.warning(
                f"[fixed-glossary] Skipping entry #{i} with bad 'zh' field: {entry!r}"
            )
            continue
        entries.append((list(jp), zh))
    return entries


def filter_fixed_glossary(
    entries: list[FixedGlossaryEntry], *texts: str | None
) -> list[FixedGlossaryEntry]:
    """Return entries where at least one JP alias appears in any of the texts.

    Substring match (Japanese has no word boundaries). All aliases of a
    matched entry are preserved so the downstream LLM can normalize every
    listed alias form to the single ZH target.
    """
    haystack = "\n".join(t for t in texts if t)
    if not haystack or not entries:
        return []
    matched: list[FixedGlossaryEntry] = []
    for aliases, zh in entries:
        if any(alias in haystack for alias in aliases):
            matched.append((list(aliases), zh))
    return matched
