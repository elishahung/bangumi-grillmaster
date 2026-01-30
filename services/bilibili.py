"""Bilibili video information retrieval utilities.

This module provides data models and functions for fetching video information
from Bilibili using the bilibili_api library.
"""

from bilibili_api import video
import re
from loguru import logger
from pydantic import BaseModel, HttpUrl, ValidationError


class BilibiliOwner(BaseModel):
    """Represents a Bilibili video owner/uploader.

    Attributes:
        mid: The unique member ID of the video owner.
        name: The display name of the video owner.
        face: URL to the owner's profile picture.
    """

    mid: int
    name: str
    face: HttpUrl


class BilibiliVideoData(BaseModel):
    """Represents detailed information about a Bilibili video.

    Attributes:
        bvid: The unique BV identifier for the video.
        title: The video title.
        desc: The video description.
        owner: Information about the video owner/uploader.
    """

    bvid: str
    title: str
    desc: str
    owner: BilibiliOwner

    @property
    def filename(self) -> str:
        """Get a sanitized filename-safe version of the video title.

        Returns:
            Sanitized video title suitable for use as a filename.
        """
        return self.sanitize_filename(self.title)

    @staticmethod
    def sanitize_filename(text: str) -> str:
        """Sanitize a filename-safe version of the text."""
        safe_name = re.sub(r"[^\w\s-]", "", text).strip()
        safe_name = re.sub(r"[-\s]+", "_", safe_name)
        return safe_name


async def get_bilibili_video_info(bvid: str) -> BilibiliVideoData:
    """Fetch video information from Bilibili by BV ID.

    Args:
        bvid: The BV identifier of the video to fetch.

    Returns:
        Validated video data including title, description, and owner info.

    Raises:
        ValidationError: If the API response doesn't match expected data schema.
        Exception: If the API request fails.
    """
    logger.info(f"Fetching video info from Bilibili: {bvid}")
    try:
        v = video.Video(bvid=bvid)
        info = await v.get_info()

        logger.debug(f"Validating video data for: {bvid}")
        video_data = BilibiliVideoData.model_validate(info)
        logger.success(f"Successfully fetched video info: {video_data.title}")
        return video_data
    except ValidationError as e:
        logger.error(f"Bilibili video data validation error for {bvid}: {e}")
        raise
    except Exception as e:
        logger.error(
            f"Failed to fetch video info from Bilibili for {bvid}: {e}"
        )
        raise
