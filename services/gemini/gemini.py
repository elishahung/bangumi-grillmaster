from .storage import GeminiStorage
from google import genai
from settings import settings
from pathlib import Path
from .instruction import instruction
from enum import Enum, auto
from loguru import logger
import hashlib
from pydantic import BaseModel
from .cost import calculate_cost
import time

logger.debug(f"Initialized Gemini model: {settings.gemini_model}")


class GeminiResponseStatus(Enum):
    """
    Enum representing the status of a Gemini API response.

    Attributes:
        COMPLETE: The response is complete and finished normally.
        NOT_COMPLETE: The response was cut off due to max tokens.
    """

    COMPLETE = auto()
    NOT_COMPLETE = auto()


class TranslationResult(BaseModel):
    continuations: int
    total_cost: float


class Gemini:
    """
    Google Gemini AI client for audio translation tasks.

    This class provides methods for translating SRT subtitles using
    Google's Gemini AI, including file management and chat-based
    translation with support for long responses.

    Attributes:
        MAX_CONTINUATIONS: Maximum number of continuation requests allowed.
    """

    MAX_CONTINUATIONS = 10

    def __init__(self):
        """
        Initialize the Gemini client with API credentials and storage.
        """
        logger.debug("Initializing Gemini client")
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.storage = GeminiStorage()
        logger.info(
            f"Gemini client initialized successfully (max continuations: {self.MAX_CONTINUATIONS})"
        )

    @staticmethod
    def convert_key_to_storage_name(key: str) -> str:
        """
        Normalize the key to a format suitable for Gemini storage.
        """
        name_elements = key + settings.gemini_model + settings.gemini_api_key
        storage_name = hashlib.md5(name_elements.encode("utf-8")).hexdigest()
        logger.debug(f"Converted key to storage name: {key} -> {storage_name}")
        return storage_name

    @staticmethod
    def check_response_status(
        response: genai.types.GenerateContentResponse,
    ) -> GeminiResponseStatus:
        """
        Check the completion status of a Gemini API response.

        Args:
            response: The response from Gemini API to check.

        Returns:
            GeminiResponseStatus indicating whether the response is complete or not.

        Raises:
            ValueError: If no candidates found or unknown finish reason.
        """
        candidates = response.candidates
        if not candidates or len(candidates) == 0:
            logger.error("No candidates found in Gemini response")
            raise ValueError("No candidates found in response")

        finish_reason = candidates[0].finish_reason
        logger.debug(f"Response finish reason: {finish_reason}")

        if finish_reason == genai.types.FinishReason.STOP:
            return GeminiResponseStatus.COMPLETE
        elif finish_reason == genai.types.FinishReason.MAX_TOKENS:
            logger.debug("Response incomplete due to max tokens")
            return GeminiResponseStatus.NOT_COMPLETE

        logger.error(f"Unknown finish reason: {finish_reason}")
        raise ValueError(f"Unknown finish reason: {finish_reason}")

    def ensure_file(self, key: str, file_path: Path):
        """
        Ensure a file exists in Gemini storage, uploading it if necessary.

        Args:
            key: The file identifier in Gemini storage.
            file_path: Local path to the file to upload if not exists.

        Returns:
            The Gemini file object.

        Raises:
            FileNotFoundError: If the local file does not exist.
            Exception: If the upload operation fails.
        """
        storage_name = Gemini.convert_key_to_storage_name(key)
        logger.debug(f"Ensuring file exists in Gemini storage: {storage_name}")
        gemini_file = self.storage.get_file(storage_name)
        if gemini_file:
            logger.info(
                f"File already exists in Gemini storage: {storage_name}"
            )
            return gemini_file
        logger.info(
            f"File not found in Gemini storage, uploading: {storage_name}"
        )
        return self.storage.upload_file(storage_name, file_path)

    def translate(
        self,
        key: str,
        video_description: str | None,
        srt_path: Path,
        audio_path: Path,
        output_path: Path,
    ) -> TranslationResult:
        """
        Translate SRT subtitles to Traditional Chinese using Gemini AI.

        This method uploads the audio file (if needed), reads the SRT file,
        creates a chat session with the audio context, and translates the
        subtitles. It handles long responses by requesting continuation.

        Args:
            key: The file identifier in Gemini storage.
            video_description: Optional description of the video for context.
            srt_path: Path to the input SRT file.
            audio_path: Path to the audio file for context.
            output_path: Path where the translated text will be saved.

        Returns:
            int: The number of continuations requested.

        Raises:
            FileNotFoundError: If SRT or audio file does not exist.
            RuntimeError: If maximum continuations exceeded.
            Exception: If translation fails.
        """
        logger.info(f"Starting translation for SRT file: {srt_path}")
        start_time = time.time()

        gemini_file = self.ensure_file(key, audio_path)

        logger.debug(f"Reading SRT file: {srt_path}")
        with open(srt_path, "r", encoding="utf-8") as f:
            srt_text = f.read()
        user_message = self.make_user_message(video_description, srt_text)

        logger.info("Creating Gemini chat session")
        chat = self.create_chat()

        logger.info(
            "Sending initial message with audio and SRT text (If the audio file has not been processed before, this may take longer)"
        )
        chat.send_message(
            message=[
                gemini_file,
                user_message,
            ]
        )

        logger.info("Requesting translation, may take 10-30 minutes...")
        response = chat.send_message(message=[user_message])
        translated_content = response.text or ""

        continuations = 0
        total_cost = calculate_cost(response.usage_metadata)
        while (
            Gemini.check_response_status(response)
            == GeminiResponseStatus.NOT_COMPLETE
        ):
            continuations += 1

            if continuations > self.MAX_CONTINUATIONS:
                error_msg = (
                    f"Exceeded maximum continuations ({self.MAX_CONTINUATIONS})"
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            logger.info(
                f"Response incomplete, requesting continuation (attempt {continuations}/{self.MAX_CONTINUATIONS})"
            )
            response = chat.send_message(message="繼續")

            total_cost += calculate_cost(response.usage_metadata)
            translated_content += "\n<BREAK>\n"
            translated_content += response.text or ""

        logger.info(f"Translation completed with {continuations} continuations")
        logger.info(f"Saving translated content to: {output_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(translated_content)
        logger.success(f"Translation saved successfully to: {output_path}")

        total_inference_time = time.time() - start_time
        logger.info(
            f"Total inference time: {total_inference_time:.2f} seconds ({total_inference_time/60:.2f} minutes)"
        )

        return TranslationResult(
            continuations=continuations,
            total_cost=total_cost,
        )

    def make_user_message(
        self, video_description: str | None, srt_text: str
    ) -> str:
        """
        Construct the user message for translation request.

        Args:
            video_description: Optional video description for context.
            srt_text: The SRT subtitle text to translate.

        Returns:
            str: The formatted message to send to Gemini.
        """
        logger.debug("Constructing user message for translation")
        base_message = "請根據所附資料，將以下 SRT 文本翻譯為繁體中文。"
        if video_description:
            logger.debug(f"Adding video description to message")
            base_message += f"\n節目介紹: {video_description}"

        base_message += f"\nSRT 文本:\n---\n{srt_text}"
        return base_message

    def create_chat(self):
        """
        Create a new chat session with Gemini AI.

        Returns:
            A configured chat session with system instructions,
            safety settings disabled, and high thinking level.
        """
        logger.debug(
            f"Creating chat session with model: {settings.gemini_model}"
        )
        return self.client.chats.create(
            model=settings.gemini_model,
            config=genai.types.GenerateContentConfig(
                system_instruction=instruction,
                safety_settings=[
                    genai.types.SafetySetting(
                        category=genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        threshold=genai.types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    genai.types.SafetySetting(
                        category=genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        threshold=genai.types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    genai.types.SafetySetting(
                        category=genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        threshold=genai.types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    genai.types.SafetySetting(
                        category=genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        threshold=genai.types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                ],
                thinking_config=genai.types.ThinkingConfig(
                    thinking_level=genai.types.ThinkingLevel.HIGH,
                ),
            ),
        )
