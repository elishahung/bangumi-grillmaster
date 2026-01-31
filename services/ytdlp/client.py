"""yt-dlp client configuration and logging adapter.

This module provides a configured yt-dlp client with loguru integration
for consistent logging across the application.
"""

import yt_dlp
from yt_dlp.utils import DownloadError
from loguru import logger
from pathlib import Path
from typing import Any, cast
from settings import settings


class YtDlpLoguruAdapter:
    """Adapter that redirects yt-dlp's standard logging to loguru.

    yt-dlp expects a logger object with debug, info, warning, and error methods.
    This adapter maps those calls to loguru with a [yt-dlp] prefix for easy filtering.
    """

    def debug(self, msg: str):
        # yt-dlp uses 'debug' for a lot of verbose info.
        # We can map it to loguru's debug.
        if not msg.startswith("[debug] "):
            logger.debug(f"[yt-dlp] {msg}")

    def info(self, msg: str):
        # yt-dlp uses 'info' for standard output (e.g., download progress).
        # Mapping to info helps track progress.
        logger.info(f"[yt-dlp] {msg}")

    def warning(self, msg: str):
        logger.warning(f"[yt-dlp] {msg}")

    def error(self, msg: str):
        logger.error(f"[yt-dlp] {msg}")


cookies_txt_path = (
    str(settings.cookies_txt_path.absolute())
    if settings.cookies_txt_path
    else None
)
if cookies_txt_path:
    logger.debug(f"Using cookies from: {cookies_txt_path}")


def get_ytdlp_client(opts: dict | None = None):
    """Create a configured yt-dlp client instance.

    Creates a YoutubeDL instance with loguru logging integration and
    optional cookie authentication from settings.

    Args:
        opts: Additional yt-dlp options to merge with defaults.

    Returns:
        A configured yt_dlp.YoutubeDL instance.
    """
    if opts is None:
        opts = {}

    ydl_opts = {
        "cookiefile": cookies_txt_path,
        "logger": YtDlpLoguruAdapter(),
        **opts,
    }

    return yt_dlp.YoutubeDL(cast(Any, ydl_opts))
