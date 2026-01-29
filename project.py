from pydantic import BaseModel


class Project(BaseModel):
    id: str
    name: str

    # Progress
    is_downloaded: bool = False
    is_video_processed: bool = False
    is_audio_processed: bool = False
    is_audio_uploaded: bool = False
    is_caption_generated: bool = False
    is_caption_translated: bool = False
