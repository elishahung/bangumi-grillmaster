"""Project management for video captioning workflow.

This module defines the Project model and related enums for tracking the progress
of video processing tasks through various stages including download, transcription,
and translation.
"""

from pydantic import BaseModel, Field
from settings import settings
from pathlib import Path
import json
from enum import Enum
from loguru import logger

PROJECT_FILE_NAME = "project.json"
VIDEO_FILE_NAME = "video.mp4"
AUDIO_FILE_NAME = "audio.opus"
ASR_FILE_NAME = "asr.json"
SRT_FILE_NAME = "srt.srt"
TRANSLATED_FILE_NAME = "translated.srt"


class ProgressStage(str, Enum):
    """Enum representing different stages in the video processing workflow.

    Each value corresponds to a boolean field in the Project model that tracks
    whether that stage has been completed.
    """

    METADATA_FETCHED = "is_metadata_fetched"
    DOWNLOADED = "is_downloaded"
    VIDEO_PROCESSED = "is_video_processed"
    AUDIO_PROCESSED = "is_audio_processed"
    ASR_COMPLETED = "is_asr_completed"
    SRT_COMPLETED = "is_srt_completed"
    TRANSLATED = "is_translated"


class Project(BaseModel):
    """Represents a video captioning project with progress tracking.

    This class manages project metadata, progress through various processing stages,
    and file paths for all intermediate and final outputs.

    Attributes:
        id: Unique identifier for the project (often a Bilibili BV ID).
        name: Human-readable name for the project (defaults to "video").
        description: Optional description of the project content.
        is_metadata_fetched: Whether video metadata has been retrieved.
        is_downloaded: Whether video has been downloaded.
        is_video_processed: Whether video segments have been combined.
        is_audio_processed: Whether audio has been extracted.
        is_asr_completed: Whether speech recognition has been completed.
        is_srt_completed: Whether SRT subtitle file has been generated.
        is_translated: Whether translation has been completed.
    """

    id: str
    name: str = Field(default="video")
    description: str | None = None

    # Progress
    is_metadata_fetched: bool = False
    is_downloaded: bool = False
    is_video_processed: bool = False
    is_audio_processed: bool = False
    is_asr_completed: bool = False
    is_srt_completed: bool = False
    is_translated: bool = False

    @classmethod
    def from_id(cls, project_id: str) -> "Project":
        """Load an existing project from disk or create a new one.

        Args:
            project_id: The unique identifier for the project.

        Returns:
            A Project instance loaded from the saved JSON file, or a new
            Project if no saved file exists.

        Raises:
            ValidationError: If the saved project data is invalid.
            JSONDecodeError: If the project file is corrupted.
        """
        logger.debug(f"Loading project: {project_id}")
        json_path = (
            Path(settings.project_root_name) / project_id / PROJECT_FILE_NAME
        )

        if not json_path.exists():
            logger.info(f"Creating new project: {project_id}")
            return cls(id=project_id)

        try:
            with open(json_path, "r") as f:
                project_data = json.load(f)
            project = cls.model_validate(project_data)
            logger.info(
                f"Loaded existing project: {project_id} (name: {project.name})"
            )
            return project
        except Exception as e:
            logger.error(f"Failed to load project {project_id}: {e}")
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

    # Files management
    @property
    def project_path(self) -> Path:
        """Get the project directory path.

        Returns:
            Path to the project directory.
        """
        return Path(settings.project_root_name) / self.id

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
