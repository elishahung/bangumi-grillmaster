"""Main workflow orchestration for video captioning pipeline.

This module provides the main processing function that coordinates all stages
of the video captioning workflow, from fetching metadata to translation.
"""

from project import Project, ProgressStage, VideoSource
from loguru import logger
from settings import settings
from services.elevenlabs import ElevenLabsASR, SrtFormatOptions, convert_file
from services.gemini import Gemini, GeminiTranslationError, TranslationRequest
from services.media import MediaProcessor
from services.ytdlp import (
    download_video,
    get_abema_episode_talents,
    get_tver_episode_talents,
    get_video_info,
)


def submit_project(
    source_str: str,
    translation_hint: str | None = None,
    break_after: ProgressStage | None = None,
) -> None:
    """Submit a new video project for processing.

    This function creates a new project with the given video source and
    optional description, saves it to disk, and immediately starts processing
    through the captioning pipeline.

    Args:
        source_str: The video source, id or url (e.g., 'BV1ZArvBaEqL', 'https://www.bilibili.com/video/BV1ZArvBaEqL').
        translation_hint: Optional description of the video content. If not provided,
            the video's title will be used as description during metadata fetching.
        break_after: Optional progress stage to stop after.

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
    process_project(new_project.id, break_after=break_after)


def _should_stop_after_stage(
    project_id: str,
    break_after: ProgressStage | None,
    completed_stage: ProgressStage,
) -> bool:
    """Return whether workflow should stop after reaching a stage."""
    if break_after != completed_stage:
        return False

    logger.warning(
        f"Breakpoint reached after {completed_stage.value}; "
        f"stopping project processing: {project_id}"
    )
    return True


def process_project(
    project_id: str, break_after: ProgressStage | None = None
) -> None:
    """Process a video project through the complete captioning pipeline.

    This function orchestrates the entire workflow:
    1. Fetch video metadata from source
    2. Download video
    3. Combine downloaded video segments
    4. Extract audio from video
    5. Perform automatic speech recognition (ASR) and write source SRT
    6. Translate subtitles using Gemini
    7. Archive project (optional)

    Each stage is skipped if it has already been completed (idempotent).
    Progress is automatically saved after each stage.

    Args:
        project_id: The unique identifier for the project.
        break_after: Optional progress stage to stop after. If the stage is
            already complete on a resumed project, processing stops before the
            next stage.

    Raises:
        Exception: If any stage of the processing fails.
    """
    logger.info(f"Starting project processing: {project_id}")
    try:
        project = Project.from_source_str(project_id)
        translation_result = None

        # Fetch metadata
        if not project.is_metadata_fetched:
            logger.info(f"Stage: Fetching metadata for {project_id}")
            video_data = get_video_info(project.source_url)
            project.update_from_video_info(video_data)
            if project.source == VideoSource.TVER:
                talents = get_tver_episode_talents(project.id)
                if talents:
                    project.update_from_source_talents(talents)
            if project.source == VideoSource.ABEMA:
                talents = get_abema_episode_talents(project.id)
                if talents:
                    project.update_from_source_talents(talents)
            project.mark_progress(ProgressStage.METADATA_FETCHED)
            logger.success("Stage complete: Metadata fetched")
        else:
            logger.debug("Stage skipped: Metadata already fetched")
        if _should_stop_after_stage(
            project_id, break_after, ProgressStage.METADATA_FETCHED
        ):
            return

        # Download video
        if not project.is_downloaded:
            logger.info(f"Stage: Downloading video for {project_id}")
            download_video(project.source_url, project.project_path)
            project.mark_progress(ProgressStage.DOWNLOADED)
            logger.success("Stage complete: Video downloaded")
        else:
            logger.debug("Stage skipped: Video already downloaded")
        if _should_stop_after_stage(
            project_id, break_after, ProgressStage.DOWNLOADED
        ):
            return

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
        if _should_stop_after_stage(
            project_id, break_after, ProgressStage.VIDEO_PROCESSED
        ):
            return

        # Process audio
        if not project.is_audio_processed:
            logger.info(f"Stage: Extracting audio for {project_id}")
            MediaProcessor.extract_audio(project.video_path, project.audio_path)
            project.mark_progress(ProgressStage.AUDIO_PROCESSED)
            logger.success("Stage complete: Audio extracted")
        else:
            logger.debug("Stage skipped: Audio already extracted")
        if _should_stop_after_stage(
            project_id, break_after, ProgressStage.AUDIO_PROCESSED
        ):
            return

        # Process ASR
        if not project.is_asr_completed:
            logger.info(f"Stage: Running ASR for {project_id}")
            asr = ElevenLabsASR()
            transcription_result = asr.transcribe_to_file(
                project.audio_path, project.asr_path
            )
            if transcription_result.total_cost > 0:
                project.add_cost("elevenlabs", transcription_result.total_cost)
            logger.info(
                f"Stage ASR cost: ${transcription_result.total_cost:.4f} "
                f"for {transcription_result.audio_duration_secs:.2f}s"
            )
            project.mark_progress(ProgressStage.ASR_COMPLETED)
            logger.success("Stage complete: ASR completed")
        else:
            logger.debug("Stage skipped: ASR already completed")
        if _should_stop_after_stage(
            project_id, break_after, ProgressStage.ASR_COMPLETED
        ):
            return

        # Process SRT
        if not project.is_srt_completed:
            logger.info(f"Stage: Converting ASR JSON to SRT for {project_id}")
            convert_file(
                project.asr_path,
                project.srt_path,
                options=SrtFormatOptions(
                    max_characters_per_line=settings.elevenlabs_srt_max_characters_per_line,
                    max_segment_chars=settings.elevenlabs_srt_max_segment_chars,
                    max_segment_duration_s=settings.elevenlabs_srt_max_segment_duration_s,
                    segment_on_silence_longer_than_s=settings.elevenlabs_srt_segment_on_silence_longer_than_s,
                    merge_speaker_turns_gap_s=settings.elevenlabs_srt_merge_speaker_turns_gap_s,
                    max_lines_per_block=settings.elevenlabs_srt_max_lines_per_block,
                ),
            )
            project.mark_progress(ProgressStage.SRT_COMPLETED)
            logger.success("Stage complete: SRT generated")
        else:
            logger.debug("Stage skipped: SRT already generated")
        if _should_stop_after_stage(
            project_id, break_after, ProgressStage.SRT_COMPLETED
        ):
            return

        # Process Translation
        if not project.is_translated:
            logger.info(f"Stage: Translating subtitles for {project_id}")
            gemini = Gemini()
            try:
                translation_result = gemini.translate(
                    TranslationRequest(
                        video_description=project.translation_hint,
                        srt_path=project.srt_path,
                        audio_key=project_id,
                        video_path=project.video_path,
                        audio_path=project.audio_path,
                        output_path=project.translated_path,
                        pre_pass_path=project.pre_pass_path,
                        pre_pass_cache_dir=project.pre_pass_cache_dir,
                        chunks_cache_dir=project.chunks_cache_dir,
                        source_metadata_context=project.source_metadata_context(),
                    )
                )
            except GeminiTranslationError as e:
                if e.summary.total_cost > 0:
                    project.add_cost("gemini", e.summary.total_cost)
                logger.error(
                    f"Stage failed: Translation partial cost "
                    f"${e.summary.total_cost:.4f} "
                    f"(pre-pass ${e.summary.pre_pass_cost:.4f}, "
                    f"completed {e.summary.completed_chunks}/{e.summary.num_chunks}, "
                    f"retries={e.summary.retries})"
                )
                raise
            if translation_result.total_cost > 0:
                project.add_cost("gemini", translation_result.total_cost)
            project.mark_progress(ProgressStage.TRANSLATED)
            logger.success("Stage complete: Translation completed")
        else:
            logger.debug("Stage skipped: Translation already completed")
        if _should_stop_after_stage(
            project_id, break_after, ProgressStage.TRANSLATED
        ):
            return

        logger.success(f"Project processing complete: {project_id}")

        # Archive project
        if settings.archived_path is not None:
            project.archive()
            logger.success(f"Project {project_id} archived successfully")
        else:
            logger.warning("Archived path is not set, skipping archiving")

        logger.info(
            f"Project {project_id} total accumulated API cost: "
            f"${project.total_cost:.4f}"
        )

    except Exception as e:
        logger.error(f"Project processing failed for {project_id}: {e}")
        raise
