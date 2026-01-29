from settings import settings
import alibabacloud_oss_v2 as oss
from pathlib import Path
from loguru import logger


class OSSStorage:
    """
    Alibaba Cloud OSS (Object Storage Service) client wrapper.

    This class provides methods for interacting with Alibaba Cloud OSS,
    including uploading, deleting, and managing file permissions.
    """

    def __init__(self):
        """
        Initialize the OSS client with credentials from environment variables.

        Raises:
            Exception: If credentials are not properly configured in environment.
        """
        logger.debug("Initializing OSS client")
        cfg = oss.config.load_default()
        cfg.credentials_provider = oss.credentials.StaticCredentialsProvider(
            access_key_id=settings.oss_access_key_id,
            access_key_secret=settings.oss_access_key_secret,
        )
        cfg.region = settings.oss_region

        self.client = oss.Client(cfg)
        logger.info(
            f"OSS client initialized successfully for region: {settings.oss_region}"
        )

    @staticmethod
    def get_public_url(key: str) -> str:
        """
        Generate a public URL for an OSS object.

        Args:
            key: The object key (path) in the OSS bucket.

        Returns:
            str: The public URL to access the object.
        """
        url = f"https://{settings.oss_bucket}.oss-{settings.oss_region}.aliyuncs.com/{key}"
        logger.debug(f"Generated public URL for key '{key}': {url}")
        return url

    def make_file_public(self, key: str) -> None:
        """
        Set the ACL of an object to public-read.

        Args:
            key: The object key (path) in the OSS bucket.

        Raises:
            Exception: If the ACL update fails.
        """
        logger.debug(f"Setting ACL to public-read for key: {key}")
        try:
            self.client.put_object_acl(
                oss.PutObjectAclRequest(
                    bucket=settings.oss_bucket,
                    key=key,
                    acl="public-read",
                )
            )
            logger.info(f"Successfully set public-read ACL for: {key}")
        except Exception as e:
            logger.error(f"Failed to set public-read ACL for '{key}': {e}")
            raise

    def check_file_exists(self, key: str) -> bool:
        """
        Check if an object exists in the OSS bucket.

        Args:
            key: The object key (path) in the OSS bucket.

        Returns:
            bool: True if the object exists, False otherwise.

        Raises:
            Exception: If the check operation fails.
        """
        logger.debug(f"Checking if file exists: {key}")
        try:
            result = self.client.is_object_exist(
                bucket=settings.oss_bucket,
                key=key,
            )
            logger.debug(f"File existence check for '{key}': {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to check file existence for '{key}': {e}")
            raise

    def upload_file(self, file_path: Path, key: str) -> None:
        """
        Upload a file to the OSS bucket.

        Args:
            file_path: Local path to the file to upload.
            key: The destination object key (path) in the OSS bucket.

        Raises:
            FileNotFoundError: If the local file does not exist.
            Exception: If the upload operation fails.
        """
        logger.info(f"Uploading file '{file_path}' to OSS key '{key}'")
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            result = self.client.put_object_from_file(
                oss.PutObjectRequest(
                    bucket=settings.oss_bucket,
                    key=key,
                ),
                str(file_path),
            )
            logger.success(f"Successfully uploaded file to: {key}")
        except Exception as e:
            logger.error(f"Failed to upload file '{file_path}' to '{key}': {e}")
            raise

    def delete_file(self, key: str) -> None:
        """
        Delete an object from the OSS bucket.

        Args:
            key: The object key (path) in the OSS bucket to delete.

        Raises:
            Exception: If the delete operation fails.
        """
        logger.info(f"Deleting file from OSS: {key}")
        try:
            self.client.delete_object(
                oss.DeleteObjectRequest(
                    bucket=settings.oss_bucket,
                    key=key,
                )
            )
            logger.success(f"Successfully deleted file: {key}")
        except Exception as e:
            logger.error(f"Failed to delete file '{key}': {e}")
            raise
