import yt_dlp
from yt_dlp.utils import DownloadError
from loguru import logger
from pathlib import Path
from typing import Any, cast
from settings import settings


class YtDlpLoguruAdapter:
    """Redirects yt-dlp standard logging to Loguru."""

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
    if opts is None:
        opts = {}

    ydl_opts = {
        "cookiefile": cookies_txt_path,
        "logger": YtDlpLoguruAdapter(),
        **opts,
    }

    return yt_dlp.YoutubeDL(cast(Any, ydl_opts))
