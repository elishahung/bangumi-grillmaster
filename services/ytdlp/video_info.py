from .client import get_ytdlp_client
from typing import cast
from pydantic import BaseModel
import re


class YtDlpVideoInfo(BaseModel):
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
    with get_ytdlp_client() as ydl:
        info = ydl.extract_info(input_str, download=False)
        return YtDlpVideoInfo.model_validate(cast(dict, info))
