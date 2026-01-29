from google import genai
from settings import settings
from pathlib import Path
from loguru import logger


class GeminiStorage:
    """
    Google Gemini file storage client.

    This class provides methods for uploading and retrieving files
    to/from Google Gemini's file storage service.
    """

    def __init__(self):
        """
        Initialize the Gemini storage client.
        """
        logger.debug("Initializing Gemini storage client")
        self.client = genai.Client(api_key=settings.gemini_api_key)
        logger.info("Gemini storage client initialized successfully")

    def upload_file(self, name: str, file_path: Path):
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
                file=file_path, config=genai.types.UploadFileConfig(name=name)
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
