"""Main workflow orchestration for video captioning pipeline.

This module provides the main processing function that coordinates all stages
of the video captioning workflow, from fetching metadata to translation.
"""

import asyncio
from project import Project, ProgressStage
from services.media import MediaProcessor
from services.fun_asr import FunASR
from services.gemini import Gemini
from services.bilibili import get_video_info
from services.downloader import download_bilibili_video
from loguru import logger


def submit_project(
    bilibili_id: str, video_description: str | None = None
) -> None:
    """Submit a new video project for processing.
    
    This function creates a new project with the given Bilibili video ID and
    optional description, saves it to disk, and immediately starts processing
    through the captioning pipeline.
    
    Args:
        bilibili_id: The Bilibili video ID (e.g., 'BV1ZArvBaEqL').
        video_description: Optional description of the video content. If not provided,
            the video's title will be used as description during metadata fetching.
    
    Note:
        The project will be automatically saved to the projects directory before
        processing begins.
    """
    logger.info(f"Submitting new project: {bilibili_id}")
    new_project = Project(id=bilibili_id, description=video_description)
    new_project.save()
    logger.info(f"Project saved: {bilibili_id}")
    process_project(new_project.id)


def process_project(project_id: str) -> None:
    """Process a video project through the complete captioning pipeline.

    This function orchestrates the entire workflow:
    1. Fetch video metadata from Bilibili
    2. Download video
    3. Combine downloaded video segments
    4. Extract audio from video
    5. Perform automatic speech recognition (ASR)
    6. Convert ASR results to SRT format
    7. Translate subtitles using Gemini

    Each stage is skipped if it has already been completed (idempotent).
    Progress is automatically saved after each stage.

    Args:
        project_id: The unique identifier for the project (usually Bilibili BV ID).

    Raises:
        Exception: If any stage of the processing fails.
    """
    logger.info(f"Starting project processing: {project_id}")
    try:
        project = Project.from_id(project_id)

        # Fetch metadata
        if not project.is_metadata_fetched:
            logger.info(f"Stage: Fetching metadata for {project_id}")
            video_data = asyncio.run(get_video_info(project.id))
            # If description is not set, use the video title
            if project.description is None:
                project.description = video_data.title
            project.name = video_data.filename
            project.mark_progress(ProgressStage.METADATA_FETCHED)
            logger.success("Stage complete: Metadata fetched")
        else:
            logger.debug("Stage skipped: Metadata already fetched")

        # Download video
        if not project.is_downloaded:
            logger.info(f"Stage: Downloading video for {project_id}")
            download_bilibili_video(project.id, project.project_path)
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
                project.description,
                project.srt_path,
                project.audio_path,
                project.translated_path,
            )
            project.mark_progress(ProgressStage.TRANSLATED)
            logger.success("Stage complete: Translation completed")
        else:
            logger.debug("Stage skipped: Translation already completed")

        logger.success(f"Project processing complete: {project_id}")

    except Exception as e:
        logger.error(f"Project processing failed for {project_id}: {e}")
        raise
