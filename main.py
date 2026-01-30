"""Command-line interface for the video captioning pipeline.

This module provides a CLI interface to submit and process online videos
for automatic captioning and translation.
"""

import typer
from typing_extensions import Annotated
from loguru import logger
from workflow import submit_project


app = typer.Typer(
    help="Bangumi GrillMaster - Automatic transcription and translation for Bangumi videos",
    add_completion=False,
)


@app.command()
def process(
    source_str: Annotated[
        str,
        typer.Argument(
            help="Video source, id or url (e.g., 'BV1ZArvBaEqL', 'https://www.bilibili.com/video/BV1ZArvBaEqL').",
            show_default=False,
        ),
    ],
    translation_hint: Annotated[
        str | None,
        typer.Argument(
            help="Translation hint for the video. If not provided, uses video title.",
            show_default=False,
        ),
    ] = None,
) -> None:
    """Submit and process a online video for captioning and translation.

    This command will:
    1. Create a new project with the given video source
    2. Download the video from source
    3. Extract audio and generate transcription
    4. Translate subtitles to target language

    Examples:
        # Process a video without translation hint
        python main.py BV1ZArvBaEqL

        # Process a video with translation hint
        python main.py BV1ZArvBaEqL "Python tutorial video"

        # Process a video with description containing spaces
        python main.py BV1ZArvBaEqL "This is a machine learning basics video"
    """
    logger.info(
        f"CLI invoked with source_str={source_str}, translation_hint={translation_hint}"
    )

    try:
        submit_project(source_str=source_str, translation_hint=translation_hint)
        logger.success(f"Successfully completed processing for {source_str}")
    except Exception as e:
        logger.error(f"Failed to process video {source_str}: {e}")
        raise typer.Exit(code=1)


def main() -> None:
    """Entry point for the CLI application."""
    app()


if __name__ == "__main__":
    main()
