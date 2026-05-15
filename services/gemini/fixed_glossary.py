"""Hand-curated jp-aliases→zh fixed glossary, filtered to per-episode matches."""

import json
import unicodedata
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


_KANA_SHIFT = 0x60  # Katakana U+30A1..U+30F6 -> Hiragana by subtracting 0x60
_STRIP_CHARS = str.maketrans(
    "", "", "ー〜～・･ 　\t\n!！?？.。,、:：/／「」『』()（）"
)


def _normalize_jp(text: str) -> str:
    """Fold script/width/space/punctuation so ASR variants match curated aliases.

    NFKC alone does NOT fold katakana<->hiragana, so an explicit kana fold is
    applied after it. Deliberately NOT phonetic: it does not equate the
    long-vowel mark with small-vowel variants. Lossy phonetic folding is
    false-positive-prone and is the "full" mode's responsibility, not this
    deterministic filter's.
    """
    text = unicodedata.normalize("NFKC", text)
    text = "".join(
        chr(ord(c) - _KANA_SHIFT) if "ァ" <= c <= "ヶ" else c for c in text
    )
    return text.translate(_STRIP_CHARS).casefold()


def filter_fixed_glossary(
    entries: list[FixedGlossaryEntry], *texts: str | None
) -> list[FixedGlossaryEntry]:
    """Return entries where at least one JP alias appears in any of the texts.

    Normalized substring match (Japanese has no word boundaries): both the
    haystack and each alias are passed through `_normalize_jp` so script/width/
    space/punctuation drift in ASR output still matches curated aliases. All
    aliases of a matched entry are preserved so the downstream LLM can
    normalize every listed alias form to the single ZH target.
    """
    haystack = "\n".join(t for t in texts if t)
    if not haystack or not entries:
        return []
    norm_haystack = _normalize_jp(haystack)
    matched: list[FixedGlossaryEntry] = []
    for aliases, zh in entries:
        # The truthiness guard stops an alias that normalizes to "" (e.g. an
        # all-punctuation alias) from matching every haystack via empty substr.
        if any(
            (norm_alias := _normalize_jp(alias)) and norm_alias in norm_haystack
            for alias in aliases
        ):
            matched.append((list(aliases), zh))
    return matched
