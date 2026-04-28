"""yt-dlp service for downloading videos and extracting metadata.

This module provides a unified interface for downloading videos from various
sources using yt-dlp, with integrated logging and metadata extraction.
"""

from .download import download_video
from .info import (
    get_abema_episode_talents,
    get_tver_episode_talents,
    get_video_info,
)

__all__ = [
    "download_video",
    "get_abema_episode_talents",
    "get_tver_episode_talents",
    "get_video_info",
]
