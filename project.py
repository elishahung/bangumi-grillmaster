"""Project management for video captioning workflow.

This module defines the Project model and related enums for tracking the progress
of video processing tasks through various stages including download, transcription,
and translation.
"""

from pydantic import BaseModel, Field
from pathlib import Path
import json
import shutil
from enum import Enum
from loguru import logger
from settings import settings
import re
from urllib.parse import urlparse

PROJECT_ROOT_NAME = "projects"
PROJECT_FILE_NAME = "project.json"
VIDEO_FILE_NAME = "video.mp4"
AUDIO_FILE_NAME = "audio.opus"
ASR_FILE_NAME = "asr.json"
SRT_FILE_NAME = "asr.srt"
TRANSLATED_FILE_NAME = "video.srt"


class ProgressStage(str, Enum):
    """Enum representing different stages in the video processing workflow.

    Each value corresponds to a boolean field in the Project model that tracks
    whether that stage has been completed.
    """

    METADATA_FETCHED = "is_metadata_fetched"
    DOWNLOADED = "is_downloaded"
    VIDEO_PROCESSED = "is_video_processed"
    AUDIO_PROCESSED = "is_audio_processed"
    ASR_TASK_SUBMITTED = "is_asr_task_submitted"
    ASR_COMPLETED = "is_asr_completed"
    SRT_COMPLETED = "is_srt_completed"
    TRANSLATED = "is_translated"


class VideoSource(str, Enum):
    """Enum representing supported video source platforms."""

    BILIBILI = "bilibili"
    TVER = "tver"


class Project(BaseModel):
    """Represents a video captioning project with progress tracking.

    This class manages project metadata, progress through various processing stages,
    and file paths for all intermediate and final outputs.

    Attributes:
        id: Unique identifier for the project (often a video source).
        name: Human-readable name for the project (defaults to "video").
        translation_hint: Optional translation hint for the project.
        is_metadata_fetched: Whether video metadata has been retrieved.
        is_downloaded: Whether video has been downloaded.
        is_video_processed: Whether video segments have been combined.
        is_audio_processed: Whether audio has been extracted.
        is_asr_task_submitted: Whether speech recognition task has been submitted.
        is_asr_completed: Whether speech recognition has been completed.
        is_srt_completed: Whether SRT subtitle file has been generated.
        is_translated: Whether translation has been completed.
    """

    id: str
    name: str = Field(default="video")
    translation_hint: str | None = None
    asr_task_id: str | None = None

    # Progress
    is_metadata_fetched: bool = False
    is_downloaded: bool = False
    is_video_processed: bool = False
    is_audio_processed: bool = False
    is_asr_task_submitted: bool = False
    is_asr_completed: bool = False
    is_srt_completed: bool = False
    is_translated: bool = False

    @staticmethod
    def parse_source_str(source_str: str) -> str:
        """Parse a video source string to extract the video ID.

        Handles various input formats including direct IDs and full URLs.

        Args:
            source_str: Video source as ID or URL.

        Returns:
            The extracted video ID.

        Raises:
            ValueError: If the URL format is not recognized.
        """
        bv_match = re.search(r"(BV[a-zA-Z0-9]+)", source_str)
        if bv_match:
            return bv_match.group(1)

        # TVer
        if "tver.jp" in source_str:
            path = urlparse(source_str).path
            parts = path.strip("/").split("/")
            if parts:
                return parts[-1]

        if source_str.startswith("https://"):
            raise ValueError(f"Invalid video source: {source_str}")

        return source_str

    @classmethod
    def from_source_str(
        cls, source_str: str, translation_hint: str | None = None
    ) -> "Project":
        """Load an existing project from disk or create a new one.

        Args:
            source_str: The video source, id or url (e.g., 'BV1ZArvBaEqL', 'https://www.bilibili.com/video/BV1ZArvBaEqL').

        Returns:
            A Project instance loaded from the saved JSON file, or a new
            Project if no saved file exists.

        Raises:
            ValidationError: If the saved project data is invalid.
            JSONDecodeError: If the project file is corrupted.
        """
        id = cls.parse_source_str(source_str)

        logger.debug(f"Loading project: {id}")
        json_path = Path(PROJECT_ROOT_NAME) / id / PROJECT_FILE_NAME

        if not json_path.exists():
            logger.info(f"Creating new project: {id}")
            return cls(id=id, translation_hint=translation_hint)

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                project_data = json.load(f)
            project = cls.model_validate(project_data)
            logger.info(f"Loaded existing project: {id} (name: {project.name})")

            if translation_hint is not None:
                logger.warning(
                    f"Translation hint is not supported for existing projects"
                )

            return project
        except Exception as e:
            logger.error(f"Failed to load project {id}: {e}")
            raise

    def save(self) -> None:
        """Save the current project state to disk as JSON.

        The project is saved to project.json in the project directory.
        Creates the directory if it doesn't exist.

        Raises:
            IOError: If the file cannot be written.
        """
        logger.debug(f"Saving project: {self.id}")
        try:
            self.project_path.mkdir(parents=True, exist_ok=True)
            with open(self.json_path, "w", encoding="utf-8") as f:
                f.write(self.model_dump_json(indent=4, ensure_ascii=False))
            logger.debug(f"Project saved: {self.id}")
        except Exception as e:
            logger.error(f"Failed to save project {self.id}: {e}")
            raise

    def mark_progress(self, stage: ProgressStage) -> None:
        """Mark a processing stage as completed and save the project.

        Args:
            stage: The progress stage to mark as complete.

        Raises:
            IOError: If the project cannot be saved.
        """
        field_name = stage.value
        logger.info(f"Project {self.id}: Marking stage complete - {stage.name}")
        setattr(self, field_name, True)
        self.save()

    def archive(self) -> None:
        """Archive the entire project by moving it to the archived directory.

        Moves the project directory to the archived path.

        Raises:
            FileNotFoundError: If the project directory doesn't exist.
            IOError: If the directory cannot be moved.
        """
        if settings.archived_path is None:
            logger.warning("Archived path is not set, skipping archiving")
            return

        archived_root = settings.archived_path
        archived_path = archived_root / self.name

        if not self.project_path.exists():
            logger.error(
                f"Project directory does not exist: {self.project_path}"
            )
            raise FileNotFoundError(
                f"Project directory not found: {self.project_path}"
            )

        # Create archived directory if it doesn't exist
        archived_root.mkdir(parents=True, exist_ok=True)

        # If archived path already exists, remove it first
        if archived_path.exists():
            logger.warning(
                f"Archived project already exists, removing: {archived_path}"
            )
            shutil.rmtree(archived_path)

        logger.info(f"Archiving project {self.id} to {archived_path}")
        shutil.move(str(self.project_path), str(archived_path))
        logger.info(f"Project {self.id} archived successfully")

    # Source management
    @property
    def source(self) -> VideoSource:
        """Determine the video source platform based on the project ID.

        Returns:
            The VideoSource enum value for this project.
        """
        if self.id.startswith("BV"):
            return VideoSource.BILIBILI
        return VideoSource.TVER

    @property
    def source_url(self) -> str:
        """Get the full URL for the video source.

        Returns:
            The complete URL to the video on its source platform.
        """
        if self.source == VideoSource.BILIBILI:
            return f"https://www.bilibili.com/video/{self.id}"
        return f"https://tver.jp/episodes/{self.id}"

    # Files management
    @property
    def project_path(self) -> Path:
        """Get the project directory path.

        Returns:
            Path to the project directory.
        """
        return Path(PROJECT_ROOT_NAME) / self.id

    @property
    def json_path(self) -> Path:
        """Get the path to the project metadata JSON file.

        Returns:
            Path to project.json.
        """
        return self.project_path / PROJECT_FILE_NAME

    @property
    def downloaded_video_paths(self) -> list[Path]:
        """Get all downloaded video segment files.

        Returns:
            List of paths to downloaded MP4 files, excluding the final combined video.
        """
        return [
            video_file
            for video_file in self.project_path.glob("*.mp4")
            if video_file.is_file()
            and video_file.name != VIDEO_FILE_NAME.split(".")[0]
        ]

    @property
    def video_path(self) -> Path:
        """Get the path to the final combined video file.

        Returns:
            Path to video.mp4.
        """
        return self.project_path / VIDEO_FILE_NAME

    @property
    def audio_path(self) -> Path:
        """Get the path to the extracted audio file.

        Returns:
            Path to audio.opus.
        """
        return self.project_path / AUDIO_FILE_NAME

    @property
    def asr_path(self) -> Path:
        """Get the path to the ASR results JSON file.

        Returns:
            Path to asr.json.
        """
        return self.project_path / ASR_FILE_NAME

    @property
    def srt_path(self) -> Path:
        """Get the path to the original subtitle file.

        Returns:
            Path to srt.srt.
        """
        return self.project_path / SRT_FILE_NAME

    @property
    def translated_path(self) -> Path:
        """Get the path to the translated subtitle file.

        Returns:
            Path to translated.srt.
        """
        return self.project_path / TRANSLATED_FILE_NAME


# Runtime check enum values match field names
def check_enum_field_sync():
    """Verify that all ProgressStage enum values correspond to Project fields.

    This function is called at module import time to ensure that the enum
    values stay synchronized with the actual Project model fields.

    Raises:
        ValueError: If a ProgressStage enum value doesn't match a Project field name.
    """
    project_fields = Project.model_fields.keys()
    for stage in ProgressStage:
        if stage.value not in project_fields:
            raise ValueError(
                f"Progress stage {stage.value} does not match project field {stage.value}"
            )


check_enum_field_sync()
