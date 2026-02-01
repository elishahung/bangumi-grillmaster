"""Media processing utilities for audio extraction and video manipulation.

This module provides the MediaProcessor class for handling common media operations
such as extracting audio from video files and combining multiple video files.
"""

from pathlib import Path
import ffmpeg
import tempfile
import os
from loguru import logger


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
