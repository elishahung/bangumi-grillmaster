from google import genai
from settings import settings
from pathlib import Path
from loguru import logger
import hashlib
import asyncio
from pydantic import BaseModel


class GeminiFileRef(BaseModel):
    key: str
    file_path: Path
    mime_type: str


class GeminiStorage:
    """
    Google Gemini file storage client.

    This class provides methods for uploading and retrieving files
    to/from Google Gemini's file storage service.
    """

    def __init__(self, client: genai.Client):
        """
        Initialize the Gemini storage client.
        """
        logger.debug("Initializing Gemini storage client")
        self.client = client
        self._file_semaphore: asyncio.Semaphore | None = None
        self._file_semaphore_limit: int | None = None
        logger.info("Gemini storage client initialized successfully")

    def _get_file_semaphore(self) -> asyncio.Semaphore:
        concurrency = max(1, settings.gemini_file_concurrency)
        if (
            self._file_semaphore is None
            or self._file_semaphore_limit != concurrency
        ):
            self._file_semaphore = asyncio.Semaphore(concurrency)
            self._file_semaphore_limit = concurrency
        return self._file_semaphore

    @staticmethod
    def convert_key_to_storage_name(key: str) -> str:
        """
        Normalize the key to a format suitable for Gemini storage.
        """
        name_elements = key + settings.gemini_model + settings.gemini_api_key
        storage_name = hashlib.md5(name_elements.encode("utf-8")).hexdigest()
        logger.debug(f"Converted key to storage name: {key} -> {storage_name}")
        return storage_name

    def upload_file(self, name: str, file_path: Path, mime_type: str):
        """
        Upload a file to Gemini file storage.

        Args:
            name: The name/identifier for the uploaded file.
            file_path: Local path to the file to upload.

        Returns:
            The uploaded file object from Gemini API.

        Raises:
            FileNotFoundError: If the local file does not exist.
            Exception: If the upload operation fails.
        """
        logger.info(
            f"Uploading file to Gemini storage: {file_path} (name: {name})"
        )
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            uploaded_file = self.client.files.upload(
                file=file_path,
                config=genai.types.UploadFileConfig(
                    name=name, mime_type=mime_type
                ),
            )
            logger.success(f"Successfully uploaded file to Gemini: {name}")
            return uploaded_file
        except Exception as e:
            logger.error(f"Failed to upload file '{file_path}' to Gemini: {e}")
            raise

    def get_file(self, name: str):
        """
        Retrieve a file from Gemini file storage.

        Args:
            name: The name/identifier of the file to retrieve.

        Returns:
            The file object from Gemini API if it exists, None otherwise.

        Raises:
            Exception: If the retrieval operation fails.
        """
        logger.debug(f"Retrieving file from Gemini storage: {name}")
        try:
            gemini_file = self.client.files.get(name=name)
            if gemini_file:
                logger.debug(f"File found in Gemini storage: {name}")
            else:
                logger.debug(f"File not found in Gemini storage: {name}")
            return gemini_file
        except Exception as e:
            logger.warning(f"Failed to retrieve file '{name}' from Gemini: {e}")
            return None

    def ensure_file(self, key: str, file_path: Path, mime_type: str):
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
        storage_name = self.convert_key_to_storage_name(key)
        logger.debug(f"Ensuring file exists in Gemini storage: {storage_name}")
        gemini_file = self.get_file(storage_name)
        if gemini_file:
            logger.info(
                f"File already exists in Gemini storage: {storage_name}"
            )
            return gemini_file
        logger.info(
            f"File not found in Gemini storage, uploading: {storage_name}"
        )
        return self.upload_file(storage_name, file_path, mime_type)

    async def ensure_files(
        self, refs: list[GeminiFileRef]
    ) -> list[genai.types.File]:
        """Ensure multiple files exist in Gemini storage concurrently in input order."""
        if not refs:
            return []

        concurrency = max(1, settings.gemini_file_concurrency)
        semaphore = self._get_file_semaphore()
        logger.info(
            f"Ensuring {len(refs)} Gemini file(s) with concurrency={concurrency}"
        )

        async def ensure_one(ref: GeminiFileRef):
            async with semaphore:
                return await asyncio.to_thread(
                    self.ensure_file,
                    ref.key,
                    ref.file_path,
                    ref.mime_type,
                )

        return await asyncio.gather(*(ensure_one(ref) for ref in refs))
