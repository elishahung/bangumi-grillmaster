"""Pydantic models for FunASR JSON parsing and normalized output.

This module defines two sets of models:
1. FunASR* models: Parse the raw JSON output from Alibaba FunASR API
2. Normalized* models: Simplified format for SRT conversion
"""

from typing import Optional
from pydantic import BaseModel


# =============================================================================
# FunASR Input Models (raw API response)
# =============================================================================


class FunASRWord(BaseModel):
    """A single word segment from FunASR output."""

    begin_time: int
    end_time: int
    text: str
    punctuation: str = ""


class FunASRSentence(BaseModel):
    """A sentence segment from FunASR output."""

    begin_time: int
    end_time: int
    text: str
    sentence_id: int
    speaker_id: Optional[int] = None
    words: list[FunASRWord]


class FunASRTranscript(BaseModel):
    """A transcript for a single audio channel."""

    channel_id: int
    content_duration_in_milliseconds: int
    text: str
    sentences: list[FunASRSentence]


class FunASRProperties(BaseModel):
    """Audio properties from FunASR output."""

    audio_format: str
    channels: list[int]
    original_sampling_rate: int
    original_duration_in_milliseconds: int


class FunASRResult(BaseModel):
    """Complete FunASR API response."""

    file_url: str
    properties: FunASRProperties
    transcripts: list[FunASRTranscript]


# =============================================================================
# Normalized Output Models (simplified for SRT conversion)
# =============================================================================


class NormalizedSentence(BaseModel):
    """A normalized sentence segment ready for SRT conversion."""

    begin_time: int
    end_time: int
    text: str


class NormalizedTranscript(BaseModel):
    """A normalized transcript containing simplified sentences."""

    channel_id: int
    sentences: list[NormalizedSentence]
