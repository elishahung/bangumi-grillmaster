"""Main workflow orchestration for video captioning pipeline.

This module provides the main processing function that coordinates all stages
of the video captioning workflow, from fetching metadata to translation.
"""

from project import Project, ProgressStage, VideoSource
from services.media import MediaProcessor
from services.fun_asr import FunASR
from services.gemini import Gemini
from services.ytdlp import download_video, get_video_info
from loguru import logger
from settings import settings


def submit_project(
    source_str: str, translation_hint: str | None = None
) -> None:
    """Submit a new video project for processing.

    This function creates a new project with the given video source and
    optional description, saves it to disk, and immediately starts processing
    through the captioning pipeline.

    Args:
        source_str: The video source, id or url (e.g., 'BV1ZArvBaEqL', 'https://www.bilibili.com/video/BV1ZArvBaEqL').
        video_description: Optional description of the video content. If not provided,
            the video's title will be used as description during metadata fetching.

    Note:
        The project will be automatically saved to the projects directory before
        processing begins.
    """
    logger.info(f"Submitting new project: {source_str}")
    new_project = Project.from_source_str(
        source_str=source_str, translation_hint=translation_hint
    )
    new_project.save()
    logger.info(f"Project saved: {source_str}")
    process_project(new_project.id)


def process_project(project_id: str) -> None:
    """Process a video project through the complete captioning pipeline.

    This function orchestrates the entire workflow:
    1. Fetch video metadata from source
    2. Download video
    3. Combine downloaded video segments
    4. Extract audio from video
    5. Perform automatic speech recognition (ASR)
    6. Convert ASR results to SRT format
    7. Translate subtitles using Gemini
    8. Archive project (optional)

    Each stage is skipped if it has already been completed (idempotent).
    Progress is automatically saved after each stage.

    Args:
        project_id: The unique identifier for the project.

    Raises:
        Exception: If any stage of the processing fails.
    """
    logger.info(f"Starting project processing: {project_id}")
    try:
        project = Project.from_source_str(project_id)

        # Fetch metadata
        if not project.is_metadata_fetched:
            logger.info(f"Stage: Fetching metadata for {project_id}")
            video_data = get_video_info(project.source_url)
            project.update_from_video_info(video_data)
            project.mark_progress(ProgressStage.METADATA_FETCHED)
            logger.success("Stage complete: Metadata fetched")
        else:
            logger.debug("Stage skipped: Metadata already fetched")

        # Download video
        if not project.is_downloaded:
            logger.info(f"Stage: Downloading video for {project_id}")
            download_video(project.source_url, project.project_path)
            project.mark_progress(ProgressStage.DOWNLOADED)
            logger.success("Stage complete: Video downloaded")
        else:
            logger.debug("Stage skipped: Video already downloaded")

        # Process video
        if not project.is_video_processed:
            logger.info(f"Stage: Combining video segments for {project_id}")
            MediaProcessor.combine_videos(
                project.downloaded_video_paths,
                project.video_path,
            )
            project.mark_progress(ProgressStage.VIDEO_PROCESSED)
            logger.success("Stage complete: Video processed")
        else:
            logger.debug("Stage skipped: Video already processed")

        # Process audio
        if not project.is_audio_processed:
            logger.info(f"Stage: Extracting audio for {project_id}")
            MediaProcessor.extract_audio(project.video_path, project.audio_path)
            project.mark_progress(ProgressStage.AUDIO_PROCESSED)
            logger.success("Stage complete: Audio extracted")
        else:
            logger.debug("Stage skipped: Audio already extracted")

        # Submit ASR task
        if not project.is_asr_task_submitted:
            logger.info(f"Stage: Submitting ASR task for {project_id}")
            fun_asr = FunASR()
            task_id = fun_asr.submit_transcription_task(
                project.id, project.audio_path
            )
            project.asr_task_id = task_id
            project.mark_progress(ProgressStage.ASR_TASK_SUBMITTED)
            logger.success("Stage complete: ASR task submitted")
        else:
            logger.debug("Stage skipped: ASR task already submitted")

        # Process ASR
        if not project.is_asr_completed:
            assert project.asr_task_id is not None
            logger.info(f"Stage: Running ASR for {project_id}")
            fun_asr = FunASR()
            fun_asr.process_transcription_task(
                project.id, project.asr_task_id, project.asr_path
            )
            project.mark_progress(ProgressStage.ASR_COMPLETED)
            logger.success("Stage complete: ASR completed")
        else:
            logger.debug("Stage skipped: ASR already completed")

        # Process SRT
        if not project.is_srt_completed:
            logger.info(f"Stage: Converting to SRT for {project_id}")
            fun_asr = FunASR()
            fun_asr.convert_to_srt(project.asr_path, project.srt_path)
            project.mark_progress(ProgressStage.SRT_COMPLETED)
            logger.success("Stage complete: SRT generated")
        else:
            logger.debug("Stage skipped: SRT already generated")

        # Process Gemini
        if not project.is_translated:
            logger.info(f"Stage: Translating subtitles for {project_id}")
            gemini = Gemini()
            gemini.translate(
                project.id,
                project.translation_hint,
                project.srt_path,
                project.audio_path,
                project.translated_path,
            )
            project.mark_progress(ProgressStage.TRANSLATED)
            logger.success("Stage complete: Translation completed")
        else:
            logger.debug("Stage skipped: Translation already completed")

        logger.success(f"Project processing complete: {project_id}")

        # Archive project
        if settings.archived_path is not None:
            project.archive()
            logger.success(f"Project {project_id} archived successfully")
        else:
            logger.warning("Archived path is not set, skipping archiving")

    except Exception as e:
        logger.error(f"Project processing failed for {project_id}: {e}")
        raise
