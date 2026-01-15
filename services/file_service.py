import io
import base64
import requests
from typing import Optional, Dict, Tuple
from pypdf import PdfReader

from config import Config


class FileService:
    """Service for downloading and parsing files from Slack."""

    IMAGE_TYPES = ["jpg", "jpeg", "png", "gif", "webp", "bmp"]
    IMAGE_MIMETYPES = ["image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"]

    def __init__(self):
        self.bot_token = Config.SLACK_BOT_TOKEN

    def download_file(self, file_url: str) -> Optional[bytes]:
        """Download a file from Slack using bot token authentication."""
        try:
            headers = {"Authorization": f"Bearer {self.bot_token}"}
            response = requests.get(file_url, headers=headers)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"Error downloading file: {e}")
            return None

    def is_image(self, file_info: Dict) -> bool:
        """Check if a file is an image."""
        file_type = file_info.get("filetype", "").lower()
        mimetype = file_info.get("mimetype", "").lower()
        return file_type in self.IMAGE_TYPES or mimetype in self.IMAGE_MIMETYPES

    def get_image_for_vision(self, file_info: Dict) -> Optional[Tuple[str, str]]:
        """Download image and return as base64 with media type for Claude vision.

        Returns: Tuple of (base64_data, media_type) or None if failed.
        """
        url = file_info.get("url_private_download") or file_info.get("url_private")
        if not url:
            return None

        content = self.download_file(url)
        if not content:
            return None

        # Determine media type
        mimetype = file_info.get("mimetype", "").lower()
        if not mimetype or mimetype not in self.IMAGE_MIMETYPES:
            file_type = file_info.get("filetype", "").lower()
            mimetype_map = {
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "png": "image/png",
                "gif": "image/gif",
                "webp": "image/webp",
                "bmp": "image/bmp",
            }
            mimetype = mimetype_map.get(file_type, "image/jpeg")

        # Encode as base64
        base64_data = base64.standard_b64encode(content).decode("utf-8")
        return base64_data, mimetype

    def extract_text_from_pdf(self, file_content: bytes) -> Optional[str]:
        """Extract text content from a PDF file."""
        try:
            pdf_file = io.BytesIO(file_content)
            reader = PdfReader(pdf_file)

            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            return "\n\n".join(text_parts) if text_parts else None
        except Exception as e:
            print(f"Error extracting PDF text: {e}")
            return None

    def extract_text_from_file(self, file_info: Dict) -> Optional[str]:
        """Extract text from a file based on its type."""
        file_type = file_info.get("filetype", "").lower()
        mimetype = file_info.get("mimetype", "").lower()

        # Get the private download URL
        url = file_info.get("url_private_download") or file_info.get("url_private")
        if not url:
            return None

        # Download the file
        content = self.download_file(url)
        if not content:
            return None

        # Handle different file types
        if file_type == "pdf" or "pdf" in mimetype:
            return self.extract_text_from_pdf(content)
        elif file_type in ["txt", "text", "md", "markdown"]:
            return content.decode("utf-8", errors="ignore")
        elif file_type in ["doc", "docx"]:
            # For Word docs, we'd need python-docx, returning None for now
            return None
        else:
            # Try to decode as text for unknown types
            try:
                return content.decode("utf-8", errors="ignore")
            except Exception:
                return None

    def get_file_summary_context(self, file_info: Dict) -> str:
        """Get context string about a file for summarization."""
        name = file_info.get("name", "Unknown file")
        file_type = file_info.get("filetype", "unknown")
        size = file_info.get("size", 0)

        size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.1f} MB"

        return f"File: {name} ({file_type}, {size_str})"
