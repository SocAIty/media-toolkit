import mimetypes
import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


mimetypes.init()


@dataclass(frozen=True)
class MimetypeDetection:
    extension: Optional[str]
    mime_type: Optional[str]


class MimetypeContentDetector:
    """
    Lightweight detector that uses Python's mimetypes module to guess
    extensions and MIME types from filenames, file paths, or URLs.
    """

    @staticmethod
    def detect(name: Optional[str]) -> 'MimetypeDetection':
        if not name:
            return MimetypeDetection(None, None)

        normalized_name = MimetypeContentDetector._normalize_name(name)
        mime_type, _ = mimetypes.guess_type(normalized_name)

        extension = None
        if mime_type:
            guessed_extension = mimetypes.guess_extension(mime_type)
            if guessed_extension:
                extension = guessed_extension

        if not extension:
            _, ext = os.path.splitext(normalized_name)
            extension = ext if ext else None

        return MimetypeDetection(extension, mime_type)

    @staticmethod
    def _normalize_name(name: str) -> str:
        """
        Remove query parameters/fragments from URLs so mimetypes can guess accurately.
        """
        parsed = urlparse(name)
        if parsed.scheme and parsed.path:
            return parsed.path
        return name


