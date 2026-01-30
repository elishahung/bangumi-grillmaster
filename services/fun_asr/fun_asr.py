from http import HTTPStatus
from dashscope.audio.asr import Transcription
from urllib import request
import dashscope
from dashscope.api_entities.dashscope_response import DashScopeAPIResponse
import json
from .srt import convert_file
from .storage import OSSStorage
from settings import settings
from pathlib import Path
from loguru import logger
import time

dashscope.base_http_api_url = settings.dashscope_api_url
dashscope.api_key = settings.dashscope_api_key

logger.debug(f"Initialized ASR model: {settings.fun_asr_model}")
logger.debug(f"Dashscope API URL: {dashscope.base_http_api_url}")


class FunASR:
    """
    Alibaba Cloud FunASR (Speech Recognition) service client.

    This class provides methods for transcribing audio files using
    Alibaba's FunASR service, including uploading files to OSS,
    initiating transcription tasks, and converting results to SRT format.
    """

    MAX_RETRY_COUNT = 3

    def __init__(self):
        """
        Initialize the FunASR client with OSS storage.
        """
        logger.debug("Initializing FunASR client")
        self.storage = OSSStorage()
        logger.info("FunASR client initialized successfully")

    def __ensure_storage_file(self, key: str, file_path: Path) -> None:
        """
        Ensure a file exists in OSS storage, uploading it if necessary.

        Args:
            key: The object key (path) in the OSS bucket.
            file_path: Local path to the file to upload if not exists.

        Raises:
            FileNotFoundError: If the local file does not exist.
            Exception: If the upload or ACL update fails.
        """
        logger.debug(f"Ensuring file exists in OSS: {key}")
        if self.storage.check_file_exists(key):
            logger.info(f"File already exists in OSS: {key}")
            return
        logger.info(f"File not found in OSS, uploading: {key}")
        self.storage.upload_file(file_path, key)
        self.storage.make_file_public(key)

    def submit_transcription_task(self, key: str, file_path: Path):
        logger.info(f"Submitting transcription task for: {file_path}")

        self.__ensure_storage_file(key, file_path)
        file_url = self.storage.get_public_url(key)
        logger.debug(f"File URL for transcription: {file_url}")

        logger.info(
            f"Submitting transcription task with model: {settings.fun_asr_model}"
        )
        task_response = Transcription.async_call(
            model=settings.fun_asr_model,
            file_urls=[
                file_url,
            ],
            language_hints=["ja"],
        )
        task_id = task_response.output.task_id
        logger.info(f"Transcription task submitted. Task ID: {task_id}")
        return task_id

    def process_transcription_task(
        self, key: str, task_id: str, json_path: Path
    ):
        logger.info(f"Processing transcription task: {task_id}")

        # Simple retry: attempt up to 3 times
        transcription_response: DashScopeAPIResponse | None = None
        for attempt in range(self.MAX_RETRY_COUNT):
            try:
                transcription_response = Transcription.wait(task=task_id)
                break
            except Exception as e:
                if attempt == self.MAX_RETRY_COUNT - 1:  # Last attempt
                    raise
                logger.warning(
                    f"Transcription.wait failed (attempt {attempt + 1}/3), retrying..."
                )
                time.sleep(1)
        assert (
            transcription_response is not None
        ), "Failed to get transcription response"

        json_path.parent.mkdir(parents=True, exist_ok=True)
        if transcription_response.status_code == HTTPStatus.OK:
            logger.debug("Transcription task completed successfully")
            transcription = transcription_response.output["results"][0]
            if transcription["subtask_status"] == "SUCCEEDED":
                url = transcription["transcription_url"]
                logger.debug(f"Fetching transcription result from: {url}")
                result = json.loads(request.urlopen(url).read().decode("utf8"))

                logger.info(f"Saving transcription result to: {json_path}")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=4, ensure_ascii=False)
                logger.success(
                    f"Transcription completed and saved to: {json_path}"
                )

                # Clean up the temporary file
                self.storage.delete_file(key)
            else:
                error_msg = f"Transcription failed with status: {transcription['subtask_status']}"
                logger.error(f"{error_msg}: {transcription}")
                raise Exception(error_msg, transcription)
        else:
            error_msg = f"Transcription request failed: {transcription_response.output.message}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def convert_to_srt(self, json_path: Path, srt_path: Path):
        """
        Convert a transcription JSON file to SRT subtitle format.

        Args:
            json_path: Path to the transcription JSON file.
            srt_path: Path where the SRT file will be saved.

        Raises:
            FileNotFoundError: If the JSON file does not exist.
            Exception: If conversion fails.
        """
        logger.info(
            f"Converting transcription to SRT: {json_path} -> {srt_path}"
        )
        try:
            convert_file(json_path, srt_path)
            logger.success(f"Successfully converted to SRT: {srt_path}")
        except Exception as e:
            logger.error(f"Failed to convert to SRT: {e}")
            raise
