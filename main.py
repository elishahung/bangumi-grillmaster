"""Command-line interface for the video captioning pipeline.

This module provides a CLI interface to submit and process Bilibili videos
for automatic captioning and translation.
"""

import typer
from typing_extensions import Annotated
from loguru import logger
from workflow import submit_project


app = typer.Typer(
    help="Bangumi GrillMaster - Automatic transcription and translation for Bilibili Bangumi videos",
    add_completion=False,
)


@app.command()
def process(
    bilibili_id: Annotated[
        str,
        typer.Argument(
            help="Bilibili video ID (e.g., BV1ZArvBaEqL)",
            show_default=False,
        ),
    ],
    description: Annotated[
        str | None,
        typer.Argument(
            help="Video description for context. If not provided, uses video title.",
            show_default=False,
        ),
    ] = None,
) -> None:
    """Submit and process a Bilibili video for captioning and translation.

    This command will:
    1. Create a new project with the given Bilibili video ID
    2. Download the video from Bilibili
    3. Extract audio and generate transcription
    4. Translate subtitles to target language

    Examples:
        # Process a video without description
        python main.py BV1ZArvBaEqL

        # Process a video with custom description (positional)
        python main.py BV1ZArvBaEqL "Python tutorial video"

        # Process a video with description containing spaces
        python main.py BV1ZArvBaEqL "This is a machine learning basics video"
    """
    logger.info(
        f"CLI invoked with bilibili_id={bilibili_id}, description={description}"
    )

    try:
        submit_project(bilibili_id=bilibili_id, video_description=description)
        logger.success(f"Successfully completed processing for {bilibili_id}")
    except Exception as e:
        logger.error(f"Failed to process video {bilibili_id}: {e}")
        raise typer.Exit(code=1)


def main() -> None:
    """Entry point for the CLI application."""
    app()


if __name__ == "__main__":
    main()
