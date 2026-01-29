import asyncio
from bilibili_api import video
from loguru import logger
from pydantic import BaseModel, HttpUrl, ValidationError
from utils import sanitize_filename


class BilibiliOwner(BaseModel):
    mid: int
    name: str
    face: HttpUrl


class BilibiliVideoData(BaseModel):
    bvid: str
    title: str
    desc: str
    owner: BilibiliOwner

    @property
    def name(self) -> str:
        return sanitize_filename(self.title)


async def get_video_info(bvid: str) -> BilibiliVideoData:
    v = video.Video(bvid=bvid)
    info = await v.get_info()

    try:
        video_data = BilibiliVideoData.model_validate(info)
        return video_data
    except ValidationError as e:
        logger.error(f"Bilibili video data validation error: {e}")
        raise e
