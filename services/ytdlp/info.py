"""Video metadata extraction using yt-dlp.

This module provides functionality to extract video metadata without
downloading the actual video content.
"""

from .client import get_ytdlp_client
from typing import cast
from pydantic import BaseModel
from loguru import logger
import re


class YtDlpVideoInfo(BaseModel):
    """Video metadata model extracted from yt-dlp.

    Attributes:
        id: The unique video identifier from the source platform.
        title: The video title.
        description: The video description text.
    """
    id: str
    title: str
    description: str

    @property
    def filename(self) -> str:
        return self.sanitize_filename(self.title)

    @staticmethod
    def sanitize_filename(text: str) -> str:
        """Sanitize a filename-safe version of the text."""
        safe_name = re.sub(r"[^\w\s-]", "", text).strip()
        safe_name = re.sub(r"[-\s]+", "_", safe_name)
        return safe_name


def get_video_info(input_str: str) -> YtDlpVideoInfo:
    """Extract video metadata without downloading.

    Uses yt-dlp to fetch video information including title, description,
    and other metadata from the source platform.

    Args:
        input_str: Video URL or identifier to extract info from.

    Returns:
        YtDlpVideoInfo containing the extracted metadata.

    Raises:
        Exception: If metadata extraction fails.
    """
    logger.info(f"Extracting video info for: {input_str}")
    try:
        with get_ytdlp_client() as ydl:
            info = ydl.extract_info(input_str, download=False)
            video_info = YtDlpVideoInfo.model_validate(cast(dict, info))
            logger.success(f"Successfully extracted info: {video_info.title}")
            return video_info
    except Exception as e:
        logger.error(f"Failed to extract video info for {input_str}: {e}")
        raise
