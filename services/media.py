"""Media processing utilities for audio extraction, chunk slicing, and frames.

This module provides the MediaProcessor class for handling common media operations
such as extracting audio from video files, slicing chunk audio, sampling frames,
and combining multiple video files.
"""

from pathlib import Path
import ffmpeg
import io
import tempfile
import os
import subprocess
from typing import Any
from loguru import logger
from pydantic import BaseModel

WAV_SAMPLE_RATE = 16000


class TimeRange(BaseModel):
    start_seconds: float
    end_seconds: float

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.end_seconds - self.start_seconds)


class MediaProcessor:
    """A utility class for processing media files using ffmpeg.

    This class provides static methods for common media processing tasks including
    audio extraction and video concatenation.
    """

    @staticmethod
    def extract_audio(input_file: Path, output_file: Path) -> Path:
        """Extract audio from a video file and convert it to Opus format.

        The audio is extracted with the following settings:
        - Mono channel (ac=1)
        - 16kHz sample rate (ar=16000)
        - 24k bitrate

        Args:
            input_file: Path to the input video file.

        Returns:
            Path to the output audio file with .opus extension.

        Raises:
            ffmpeg.Error: If the extraction process fails.
        """
        logger.info(f"Extracting audio from video: {input_file}")
        try:
            ffmpeg.input(str(input_file)).output(
                str(output_file),
                ac=1,
                ar="16000",
                audio_bitrate="24k",
            ).run()
            logger.success(f"Successfully extracted audio to: {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"Failed to extract audio from '{input_file}': {e}")
            raise

    @staticmethod
    def combine_videos(input_files: list[Path], output_file: Path) -> None:
        """Combine multiple video files into a single output file.

        If only one input file is provided, it will be renamed to the output file.
        If multiple files are provided, they are concatenated using ffmpeg's concat
        demuxer without re-encoding (using copy codec).

        Note: All input files are deleted after successful combination.

        Args:
            input_files: List of paths to input video files to be combined.
            output_file: Path where the combined video will be saved.

        Raises:
            AssertionError: If the input_files list is empty.
            ffmpeg.Error: If the video combination process fails.
        """
        logger.info(
            f"Combining {len(input_files)} video(s) into: {output_file}"
        )
        assert len(input_files) > 0, "No input files provided"

        try:
            if len(input_files) == 1:
                only_file = input_files[0]
                logger.debug(
                    f"Single input file, renaming {only_file} to {output_file}"
                )
                os.rename(only_file, output_file)
                logger.success(
                    f"Successfully created output file: {output_file}"
                )
                return

            logger.debug(
                f"Creating concat file list for {len(input_files)} videos"
            )
            file_list_content = "\n".join(
                [f"file '{input_file}'" for input_file in sorted(input_files)]
            )

            with tempfile.NamedTemporaryFile(
                suffix=".txt", delete=False
            ) as temp_file:
                temp_file.write(file_list_content.encode())
                temp_file_path = temp_file.name

            logger.debug(f"Concatenating videos using ffmpeg")
            ffmpeg.input(
                f"concat:{temp_file_path}", format="concat", safe=0
            ).output(
                str(output_file),
                c="copy",
                map=0,
                movflags="faststart",
            ).run(
                overwrite_output=True
            )

            logger.debug("Cleaning up temporary and input files")
            os.remove(temp_file_path)
            for input_file in input_files:
                input_file.unlink()

            logger.success(f"Successfully combined videos into: {output_file}")
        except Exception as e:
            logger.error(f"Failed to combine videos: {e}")
            raise

    @staticmethod
    def load_audio_waveform(
        input_file: Path,
        sample_rate: int = WAV_SAMPLE_RATE,
    ) -> Any:
        """Load an audio file as mono float waveform at the target sample rate."""
        try:
            import librosa

            wav, _ = librosa.load(
                str(input_file),
                sr=sample_rate,
                mono=True,
            )
            return wav
        except Exception as librosa_error:
            logger.warning(
                "librosa failed to load audio, falling back to ffmpeg: "
                f"{librosa_error}"
            )

        import soundfile as sf

        command = [
            "ffmpeg",
            "-i",
            str(input_file),
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            "-f",
            "wav",
            "-",
        ]
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout_data, stderr_data = process.communicate()
        if process.returncode != 0:
            raise RuntimeError(
                "FFmpeg failed to load audio: "
                f"{stderr_data.decode('utf-8', errors='ignore')}"
            )

        with io.BytesIO(stdout_data) as data_io:
            wav, _ = sf.read(data_io, dtype="float32")
        return wav

    @staticmethod
    def parse_timecode_line(timecode: str) -> TimeRange:
        """Parse a single SRT timecode line into seconds."""
        start_str, end_str = [part.strip() for part in timecode.split("-->")]
        return TimeRange(
            start_seconds=MediaProcessor._parse_timestamp(start_str),
            end_seconds=MediaProcessor._parse_timestamp(end_str),
        )

    @staticmethod
    def get_media_duration(input_file: Path) -> float:
        """Read media duration in seconds from ffprobe."""
        probe = ffmpeg.probe(str(input_file))
        format_info = probe.get("format", {})
        duration = format_info.get("duration")
        if duration is None:
            raise ValueError(f"Media duration missing: {input_file}")
        return float(duration)

    @staticmethod
    def extract_audio_segment(
        input_file: Path,
        output_file: Path,
        start_seconds: float,
        end_seconds: float,
    ) -> Path:
        """Extract an audio slice with the same target settings as full audio."""
        duration = max(0.0, end_seconds - start_seconds)
        if duration <= 0:
            raise ValueError("Audio segment duration must be positive")

        if output_file.exists():
            logger.debug(f"Reusing cached audio segment: {output_file}")
            return output_file

        output_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"Extracting audio segment {start_seconds:.3f}-{end_seconds:.3f}s "
            f"to {output_file}"
        )
        try:
            (
                ffmpeg.input(str(input_file), ss=start_seconds, t=duration)
                .output(
                    str(output_file),
                    ac=1,
                    ar="16000",
                    audio_bitrate="24k",
                )
                .run(overwrite_output=True, quiet=True)
            )
            return output_file
        except Exception as e:
            logger.error(f"Failed to extract audio segment: {e}")
            raise

    @staticmethod
    def extract_video_frame(
        input_file: Path,
        output_file: Path,
        timestamp_seconds: float,
        max_side: int,
    ) -> Path:
        """Extract a single JPEG frame with longest side constrained."""
        if max_side <= 0:
            raise ValueError("max_side must be positive")
        if output_file.exists():
            logger.debug(f"Reusing cached frame: {output_file}")
            return output_file

        output_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"Extracting frame at {timestamp_seconds:.3f}s to {output_file}"
        )
        scale_filter = (
            f"if(gte(iw,ih),{max_side},-2)",
            f"if(gte(iw,ih),-2,{max_side})",
        )
        try:
            stream = ffmpeg.input(str(input_file), ss=timestamp_seconds)
            (
                stream.filter("scale", *scale_filter)
                .output(
                    str(output_file),
                    vframes=1,
                    format="image2",
                    vcodec="mjpeg",
                    qscale=2,
                )
                .run(overwrite_output=True, quiet=True)
            )
            return output_file
        except Exception as e:
            logger.error(f"Failed to extract frame: {e}")
            raise

    @staticmethod
    def evenly_spaced_timestamps(
        duration_seconds: float, max_frames: int
    ) -> list[float]:
        """Return evenly spaced timestamps inside a media range."""
        if duration_seconds <= 0 or max_frames <= 0:
            return []
        frame_count = max_frames
        interval = duration_seconds / (frame_count + 1)
        return [interval * index for index in range(1, frame_count + 1)]

    @staticmethod
    def absolute_interval_timestamps(
        start_seconds: float,
        end_seconds: float,
        interval_seconds: float,
        include_start: bool,
        include_end: bool,
    ) -> list[float]:
        """Return deterministic absolute timestamps within a time range."""
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        timestamps: set[float] = set()
        if include_start:
            timestamps.add(round(start_seconds, 3))

        first_slot = int(start_seconds // interval_seconds)
        current = first_slot * interval_seconds
        if current < start_seconds:
            current += interval_seconds

        while current < end_seconds or (
            include_end and abs(current - end_seconds) < 1e-6
        ):
            if start_seconds <= current < end_seconds or (
                include_end and current <= end_seconds
            ):
                timestamps.add(round(current, 3))
            current += interval_seconds

        return sorted(timestamps)

    @staticmethod
    def _parse_timestamp(timestamp: str) -> float:
        normalized = timestamp.replace(",", ".")
        hours, minutes, seconds = normalized.split(":")
        return (
            int(hours) * 3600
            + int(minutes) * 60
            + float(seconds)
        )
