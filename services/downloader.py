"""Bilibili video downloader utilities.

This module provides functions for downloading videos from Bilibili using
the yt-dlp library, wrapped with Loguru logging for consistent output.
"""

import yt_dlp
from yt_dlp.utils import DownloadError
from loguru import logger
from pathlib import Path
from typing import Any, cast


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


def download_bilibili_video(
    input_str: str, output_path: Path, cookies_path: Path | None = None
) -> None:
    """Downloads a Bilibili video using yt-dlp with project-based directory structure.

    This function handles URL parsing, configures the output template to folder
    structures (projects/{id}/...), and delegates the download to yt-dlp.

    Args:
        input_str: The Bilibili video identifier. Can be a full URL
                   (e.g., 'https://www.bilibili.com/video/BV1xx...')
                   or just the BV ID (e.g., 'BV1xx...').
        cookies_path: The file path to the Netscape-formatted cookies file.
                      Defaults to None.

    Returns:
        None.

    Raises:
        FileNotFoundError: If the provided cookies file does not exist (warning only).
        yt_dlp.utils.DownloadError: If the video cannot be downloaded.
        Exception: For any other unforeseen errors during execution.
    """

    # Log the entry point
    logger.info(f"Initiating download task for input: {input_str}")

    # Input parsing: Detect if it's an ID or URL
    if "bilibili.com" not in input_str:
        # Assuming input is a BV ID
        url = f"https://www.bilibili.com/video/{input_str}"
        logger.debug(f"Input detected as ID. Converted to URL: {url}")
    else:
        url = input_str

    # Check cookies existence
    if cookies_path:
        logger.info(f"Using cookies file: {cookies_path}")

    # Configure yt-dlp options
    ydl_opts = {
        "cookiefile": cookies_path.absolute() if cookies_path else None,
        "outtmpl": f"{output_path}/%(playlist_index|0)s.%(ext)s",
        "logger": YtDlpLoguruAdapter(),
        "merge_output_format": "mp4",
        "format": "bestvideo+bestaudio/best",
    }

    # Execute download
    try:
        logger.info(f"Starting yt-dlp process for: {url}")

        with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
            # extract_info with download=True performs the download
            info_dict = ydl.extract_info(url, download=True)

            # Safely get title for logging
            video_title = (
                info_dict.get("title", "Unknown Title")
                if info_dict
                else "Unknown"
            )

        logger.success(f"Successfully downloaded: {video_title}")

    except DownloadError as e:
        logger.error(f"yt-dlp download failed for {url}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during download execution: {e}")
        raise
