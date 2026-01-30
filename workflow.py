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
from loguru import logger


def process_project(project_id: str) -> None:
    """Process a video project through the complete captioning pipeline.

    This function orchestrates the entire workflow:
    1. Fetch video metadata from Bilibili
    2. Download video (not yet implemented)
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
            if project.description is None:
                project.description = video_data.title
            project.name = video_data.filename
            project.mark_progress(ProgressStage.METADATA_FETCHED)
            logger.success("Stage complete: Metadata fetched")
        else:
            logger.debug("Stage skipped: Metadata already fetched")

        # Download not implemented yet
        logger.debug("Stage skipped: Download not implemented yet")

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

        # Process ASR
        if not project.is_asr_completed:
            logger.info(f"Stage: Running ASR for {project_id}")
            fun_asr = FunASR()
            fun_asr.transcribe(project.id, project.audio_path, project.asr_path)
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
