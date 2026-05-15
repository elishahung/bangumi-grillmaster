"""Hand-curated jp-aliases→zh fixed glossary, filtered to per-episode matches."""

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from loguru import logger


FIXED_GLOSSARY_PATH = Path(__file__).parent / "fixed_glossary.json"

# An entry maps a list of JP source aliases (ASR may transcribe the same term
# in several forms) to a single ZH target. The alias list now holds only the
# original correct source spellings; ASR/script/width drift is folded by
# `_normalize_jp` at match time rather than enumerated here.
FixedGlossaryEntry = tuple[list[str], str]


@dataclass(frozen=True)
class TalentUnit:
    """One act: an optional 組合 plus one-or-more members.

    `group` is None for a solo talent. `members` is always non-empty — a unit
    whose members all fail validation is dropped at load time so a dangling
    組合 label never reaches the prompt.
    """

    group: FixedGlossaryEntry | None
    members: tuple[FixedGlossaryEntry, ...]

    def entries(self) -> list[FixedGlossaryEntry]:
        """Group (if any) first, then every member.

        Single source of truth for both prompt-render order and whole-unit
        emission so the two can never diverge.
        """
        out: list[FixedGlossaryEntry] = []
        if self.group is not None:
            out.append(self.group)
        out.extend(self.members)
        return out


@dataclass(frozen=True)
class FixedGlossary:
    """Parsed glossary: grouped talent units plus flat non-person entries."""

    talents: tuple[TalentUnit, ...] = ()
    others: tuple[FixedGlossaryEntry, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.talents or self.others)


def _parse_mapping_block(obj: object, ctx: str) -> FixedGlossaryEntry | None:
    """Validate one {jp:[...], zh:""} block.

    Bad shape → warn and return None so a typo never breaks the pipeline.
    """
    if not isinstance(obj, dict):
        logger.warning(f"[fixed-glossary] Skipping non-object {ctx}: {obj!r}")
        return None
    jp = obj.get("jp")
    zh = obj.get("zh")
    if (
        not isinstance(jp, list)
        or not jp
        or not all(isinstance(a, str) and a for a in jp)
    ):
        logger.warning(
            f"[fixed-glossary] Skipping {ctx} with bad 'jp' field: {obj!r}"
        )
        return None
    if not isinstance(zh, str) or not zh:
        logger.warning(
            f"[fixed-glossary] Skipping {ctx} with bad 'zh' field: {obj!r}"
        )
        return None
    return (list(jp), zh)


def _parse_talent_unit(obj: object, idx: int) -> TalentUnit | None:
    """Validate one talent unit.

    A bad/absent `group` degrades the unit to solo (kept if members valid);
    a unit with zero valid members is dropped entirely.
    """
    if not isinstance(obj, dict):
        logger.warning(
            f"[fixed-glossary] Skipping non-object talents[{idx}]: {obj!r}"
        )
        return None
    group: FixedGlossaryEntry | None = None
    if obj.get("group") is not None:
        group = _parse_mapping_block(obj["group"], f"talents[{idx}].group")
    members_raw = obj.get("members")
    if not isinstance(members_raw, list) or not members_raw:
        logger.warning(
            f"[fixed-glossary] Skipping talents[{idx}] with bad 'members': {obj!r}"
        )
        return None
    members: list[FixedGlossaryEntry] = []
    for j, member in enumerate(members_raw):
        parsed = _parse_mapping_block(member, f"talents[{idx}].members[{j}]")
        if parsed is not None:
            members.append(parsed)
    if not members:
        logger.warning(
            f"[fixed-glossary] Skipping talents[{idx}] with no valid members: {obj!r}"
        )
        return None
    return TalentUnit(group, tuple(members))


def load_fixed_glossary(path: Path = FIXED_GLOSSARY_PATH) -> FixedGlossary:
    """Load and validate the fixed glossary file.

    Missing file → empty glossary (feature off). Malformed entries are skipped
    with a warning so a typo never breaks the whole pipeline. An old flat-list
    file degrades safely to an empty glossary instead of crashing.
    """
    if not path.exists():
        logger.info(f"[fixed-glossary] File not found at {path}, skipping")
        return FixedGlossary()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"[fixed-glossary] Failed to parse {path}: {e}")
        return FixedGlossary()
    if not isinstance(raw, dict):
        logger.warning(
            f"[fixed-glossary] Expected object at top level, got {type(raw).__name__}"
        )
        return FixedGlossary()

    talents: list[TalentUnit] = []
    talents_raw = raw.get("talents", [])
    if not isinstance(talents_raw, list):
        logger.warning(
            f"[fixed-glossary] Expected list for 'talents', got "
            f"{type(talents_raw).__name__}; ignoring that section"
        )
    else:
        for i, unit in enumerate(talents_raw):
            parsed_unit = _parse_talent_unit(unit, i)
            if parsed_unit is not None:
                talents.append(parsed_unit)

    others: list[FixedGlossaryEntry] = []
    others_raw = raw.get("others", [])
    if not isinstance(others_raw, list):
        logger.warning(
            f"[fixed-glossary] Expected list for 'others', got "
            f"{type(others_raw).__name__}; ignoring that section"
        )
    else:
        for i, entry in enumerate(others_raw):
            parsed_entry = _parse_mapping_block(entry, f"others[{i}]")
            if parsed_entry is not None:
                others.append(parsed_entry)

    return FixedGlossary(tuple(talents), tuple(others))


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


def _entry_hits(entry: FixedGlossaryEntry, norm_haystack: str) -> bool:
    """True if any alias (normalized) is a substring of the normalized haystack.

    The truthiness guard stops an alias that normalizes to "" (e.g. an
    all-punctuation alias) from matching every haystack via empty substring.
    """
    aliases, _ = entry
    return any(
        (norm_alias := _normalize_jp(alias)) and norm_alias in norm_haystack
        for alias in aliases
    )


def filter_fixed_glossary(
    glossary: FixedGlossary, *texts: str | None
) -> FixedGlossary:
    """Return the subset whose names appear in any of the texts.

    A talent unit is emitted WHOLE (group + every member, unmodified) when
    ANY of its group or member aliases appears, so a bare ambiguous member
    name still arrives with its full 組合 context for the downstream LLM.
    `others` entries match individually, exactly as before. Both the haystack
    and each alias pass through `_normalize_jp` so script/width/space/
    punctuation drift in ASR output still matches curated aliases.
    """
    haystack = "\n".join(t for t in texts if t)
    if not haystack or not glossary:
        return FixedGlossary()
    norm_haystack = _normalize_jp(haystack)

    matched_talents: list[TalentUnit] = []
    for unit in glossary.talents:
        group_hit = unit.group is not None and _entry_hits(
            unit.group, norm_haystack
        )
        member_hit = any(
            _entry_hits(member, norm_haystack) for member in unit.members
        )
        if group_hit or member_hit:
            matched_talents.append(unit)

    matched_others = tuple(
        entry for entry in glossary.others if _entry_hits(entry, norm_haystack)
    )
    return FixedGlossary(tuple(matched_talents), matched_others)


def _format_entry(entry: FixedGlossaryEntry) -> str:
    aliases, zh = entry
    return f"{' / '.join(aliases)} → {zh}"


_FULL_HEADER = (
    "\n【固定詞彙表（完整參照表，未過濾；僅在該名稱實際出現時才套用，"
    "容許 ASR 誤聽，未出現者忽略）】\n"
)
_FILTERED_HEADER = (
    "\n【固定詞彙表（最高優先級，必須採用；同一行的多個別名需全部正規化為同一目標）】\n"
)


def format_fixed_glossary_block(
    glossary: FixedGlossary, *, full_mode: bool
) -> str:
    """Render the glossary as the prompt block (header + grouped sections).

    Owns all glossary→prompt text shaping so pre_pass holds no formatting
    knowledge. Talents are grouped under their 組合 (or 單人) so an ambiguous
    member token carries disambiguation context; `others` stays a flat list.
    A falsy glossary → "" and an empty section is omitted entirely.
    """
    if not glossary:
        return ""
    sections: list[str] = []
    if glossary.talents:
        lines = ["〔藝人/組合〕"]
        for unit in glossary.talents:
            if unit.group is not None:
                lines.append(f"・組合：{_format_entry(unit.group)}")
            else:
                lines.append("・（單人）")
            for member in unit.members:
                lines.append(f"    · {_format_entry(member)}")
        sections.append("\n".join(lines))
    if glossary.others:
        lines = ["〔節目/單元/品牌/術語〕"]
        lines.extend(f"- {_format_entry(entry)}" for entry in glossary.others)
        sections.append("\n".join(lines))
    header = _FULL_HEADER if full_mode else _FILTERED_HEADER
    return header + "\n".join(sections)
