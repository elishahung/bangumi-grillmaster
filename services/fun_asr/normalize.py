"""Normalize FunASR JSON output before SRT conversion.

This module handles two main normalization tasks:
1. Merge sentences incorrectly split by "." (e.g., "N.G." -> "N." + "G.")
2. Split overly long sentences at appropriate boundaries
"""

from loguru import logger

from .models import (
    FunASRResult,
    FunASRSentence,
    FunASRWord,
    NormalizedSentence,
    NormalizedTranscript,
)

# Japanese subtitle standard: 40 characters per line
DEFAULT_MAX_CHARS = 40

# Punctuation marks that indicate natural sentence breaks
SPLIT_PUNCTUATION = {"、", "。", "！", "？", "!", "?", "，", ","}

# Maximum time gap (ms) between sentences to consider them as continuation
MAX_MERGE_GAP_MS = 500


# =============================================================================
# Merge Logic: Fix "." split issues
# =============================================================================


def is_english_letter(char: str) -> bool:
    """Check if a character is an English letter (A-Z or a-z)."""
    return char.isascii() and char.isalpha()


def should_merge_with_next(
    current: FunASRSentence, next_sentence: FunASRSentence
) -> bool:
    """
    Determine if current sentence should merge with the next one.

    Conditions for merging:
    1. Current sentence ends with "." punctuation (from words[-1])
    2. The word before "." ends with an English letter (abbreviation like "N.", "Dr.")
    3. One of:
       - Next sentence is very short (likely abbreviation continuation)
       - Time gap between sentences is small
       - Next sentence also ends with "." (chain of abbreviations)

    Args:
        current: The current sentence to check
        next_sentence: The following sentence

    Returns:
        True if sentences should be merged
    """
    if not current.words:
        return False

    last_word = current.words[-1]

    # Check if current ends with "." (but not "。" which is a full stop)
    if last_word.punctuation.strip() != ".":
        return False

    # Check if the word before "." ends with an English letter
    # This filters out cases like "一緒やんか." where Japanese text ends with "."
    word_text = last_word.text.strip()
    if not word_text or not is_english_letter(word_text[-1]):
        return False

    # Check time gap
    time_gap = next_sentence.begin_time - current.end_time
    if time_gap > MAX_MERGE_GAP_MS:
        return False

    # Next sentence must also start with English letter to be part of abbreviation
    if not next_sentence.words:
        return False
    next_first_word = next_sentence.words[0].text.strip()
    if not next_first_word or not is_english_letter(next_first_word[0]):
        return False

    # Check if next sentence is short (likely abbreviation part like "G.")
    next_text = next_sentence.text.strip()
    if len(next_text) <= 5:
        return True

    # Check if next sentence also ends with "." (chain pattern like "N." + "G.")
    if next_sentence.words[-1].punctuation.strip() == ".":
        return True

    return False


def merge_two_sentences(
    first: FunASRSentence, second: FunASRSentence
) -> FunASRSentence:
    """
    Merge two sentences into one.

    Args:
        first: First sentence
        second: Second sentence

    Returns:
        Merged sentence with combined words and updated timing
    """
    merged_words = first.words + second.words
    merged_text = first.text.rstrip() + second.text

    return FunASRSentence(
        begin_time=first.begin_time,
        end_time=second.end_time,
        text=merged_text,
        sentence_id=first.sentence_id,
        speaker_id=first.speaker_id,
        words=merged_words,
    )


def merge_dotted_sentences(
    sentences: list[FunASRSentence],
) -> tuple[list[FunASRSentence], int]:
    """
    Merge sentences that were incorrectly split by "." punctuation.

    Handles cases like:
    - "N." + "G." -> "N.G."
    - "Dr." + "Smith" -> "Dr.Smith"

    Args:
        sentences: List of sentences to process

    Returns:
        Tuple of (merged sentences list, number of merges performed)
    """
    if not sentences:
        return [], 0

    result: list[FunASRSentence] = []
    merge_count = 0
    i = 0

    while i < len(sentences):
        current = sentences[i]

        # Keep merging while conditions are met
        while i + 1 < len(sentences) and should_merge_with_next(
            current, sentences[i + 1]
        ):
            next_sentence = sentences[i + 1]
            logger.debug(
                f"Merging sentences: '{current.text}' + '{next_sentence.text}'"
            )
            current = merge_two_sentences(current, next_sentence)
            merge_count += 1
            i += 1

        result.append(current)
        i += 1

    return result, merge_count


# =============================================================================
# Split Logic: Handle overly long sentences
# =============================================================================


def has_split_punctuation(words: list[FunASRWord]) -> bool:
    """Check if any word (except the last) has punctuation that can be used for splitting.

    If punctuation only exists at the last word, it cannot be used as a split point,
    so we should use length-based splitting instead.
    """
    if len(words) <= 1:
        return False
    # Only check words[:-1] because last word's punctuation can't be a split point
    return any(w.punctuation.strip() in SPLIT_PUNCTUATION for w in words[:-1])


def split_by_punctuation(
    sentence: FunASRSentence, max_chars: int
) -> list[NormalizedSentence]:
    """
    Split long sentence at punctuation marks (Case A).

    When text exceeds max_chars, backtracks to the nearest punctuation
    mark to create a natural split point.

    Args:
        sentence: The sentence to split
        max_chars: Maximum characters per segment

    Returns:
        List of normalized sentence segments
    """
    segments: list[NormalizedSentence] = []
    current_words: list[FunASRWord] = []
    current_text = ""
    # Track last valid split point: (word_count, text_at_that_point)
    last_split_point: tuple[int, str] | None = None

    for word in sentence.words:
        word_text = word.text + word.punctuation
        current_words.append(word)
        current_text += word_text

        # Mark potential split point when we encounter punctuation
        if word.punctuation.strip() in SPLIT_PUNCTUATION:
            last_split_point = (len(current_words), current_text)

        # When exceeding max_chars, backtrack to last split point
        if len(current_text) >= max_chars and last_split_point is not None:
            split_word_count, split_text = last_split_point
            words_to_segment = current_words[:split_word_count]

            segment = NormalizedSentence(
                begin_time=words_to_segment[0].begin_time,
                end_time=words_to_segment[-1].end_time,
                text=split_text.strip(),
            )
            segments.append(segment)

            # Keep remaining words for next segment
            current_words = current_words[split_word_count:]
            current_text = "".join(
                w.text + w.punctuation for w in current_words
            )
            last_split_point = None

    # Handle remaining words
    if current_words:
        segment = NormalizedSentence(
            begin_time=current_words[0].begin_time,
            end_time=current_words[-1].end_time,
            text=current_text.strip(),
        )
        segments.append(segment)

    return segments


def split_by_length(
    sentence: FunASRSentence, max_chars: int
) -> list[NormalizedSentence]:
    """
    Split long sentence by character count (Case B - balanced distribution).

    Calculates the optimal number of segments and distributes text evenly
    across them, splitting at word boundaries.

    Args:
        sentence: The sentence to split
        max_chars: Maximum characters per segment

    Returns:
        List of normalized sentence segments
    """
    if not sentence.words:
        return [
            NormalizedSentence(
                begin_time=sentence.begin_time,
                end_time=sentence.end_time,
                text=sentence.text.strip(),
            )
        ]

    # Calculate total length and number of segments needed
    total_text = "".join(w.text + w.punctuation for w in sentence.words)
    total_chars = len(total_text)

    if total_chars <= max_chars:
        return [
            NormalizedSentence(
                begin_time=sentence.begin_time,
                end_time=sentence.end_time,
                text=total_text.strip(),
            )
        ]

    # Calculate optimal segment count and target chars per segment
    num_segments = (total_chars + max_chars - 1) // max_chars  # ceil division
    target_chars = total_chars / num_segments

    segments: list[NormalizedSentence] = []
    current_words: list[FunASRWord] = []
    current_text = ""
    segments_created = 0

    for word in sentence.words:
        word_text = word.text + word.punctuation
        current_words.append(word)
        current_text += word_text

        # Split when we reach target chars (not the last segment)
        if (
            len(current_text) >= target_chars
            and segments_created < num_segments - 1
        ):
            segment = NormalizedSentence(
                begin_time=current_words[0].begin_time,
                end_time=current_words[-1].end_time,
                text=current_text.strip(),
            )
            segments.append(segment)
            segments_created += 1
            current_words = []
            current_text = ""

    # Handle remaining words (last segment)
    if current_words:
        segment = NormalizedSentence(
            begin_time=current_words[0].begin_time,
            end_time=current_words[-1].end_time,
            text=current_text.strip(),
        )
        segments.append(segment)

    return segments


def split_long_sentence(
    sentence: FunASRSentence, max_chars: int
) -> list[NormalizedSentence]:
    """
    Split a long sentence into smaller segments.

    Dispatcher that chooses the appropriate splitting strategy:
    - Case A: If punctuation is available, split at punctuation marks
    - Case B: Otherwise, split by average character distribution

    Args:
        sentence: The sentence to split
        max_chars: Maximum characters per segment

    Returns:
        List of normalized sentence segments
    """
    text_length = len(sentence.text)

    # No need to split if within limit
    if text_length <= max_chars:
        return [
            NormalizedSentence(
                begin_time=sentence.begin_time,
                end_time=sentence.end_time,
                text=sentence.text.strip(),
            )
        ]

    # Choose strategy based on punctuation availability
    is_split_by_punctuation = has_split_punctuation(sentence.words)
    target_length = int(max_chars * 0.8)

    if is_split_by_punctuation:
        splitted_sentences = split_by_punctuation(sentence, target_length)
    else:
        splitted_sentences = split_by_length(sentence, target_length)

    logging_prefix = (
        "Splitting by punctuation"
        if is_split_by_punctuation
        else "Splitting by length"
    )
    logger.debug(
        f"{logging_prefix} to {len(splitted_sentences)} segments: '{sentence.text[:30]}...'"
    )
    return splitted_sentences


# =============================================================================
# Main Normalization Functions
# =============================================================================


def normalize_transcript(
    data: FunASRResult,
    channel_id: int = 0,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> NormalizedTranscript:
    """
    Normalize a FunASR result into simplified format.

    Steps:
    1. Find the transcript for the specified channel
    2. Merge sentences incorrectly split by "."
    3. Split overly long sentences
    4. Return normalized transcript

    Args:
        data: Parsed FunASR result
        channel_id: Which audio channel to process (default: 0)
        max_chars: Maximum characters per sentence segment

    Returns:
        Normalized transcript ready for SRT conversion

    Raises:
        ValueError: If the specified channel is not found
    """
    # Find the target channel
    transcript = None
    for t in data.transcripts:
        if t.channel_id == channel_id:
            transcript = t
            break

    if transcript is None:
        raise ValueError(f"Channel {channel_id} not found in transcripts")

    # Step 1: Merge dotted sentences
    merged_sentences, merge_count = merge_dotted_sentences(transcript.sentences)

    # Step 2: Split long sentences
    normalized_sentences: list[NormalizedSentence] = []
    split_count = 0
    for sentence in merged_sentences:
        segments = split_long_sentence(sentence, max_chars)
        if len(segments) > 1:
            split_count += 1
        normalized_sentences.extend(segments)

    # Log summary
    if merge_count > 0:
        logger.info(f"Merged {merge_count} dotted sentence pairs")
    if split_count > 0:
        logger.info(f"Split {split_count} long sentences")

    return NormalizedTranscript(
        channel_id=channel_id,
        sentences=normalized_sentences,
    )
