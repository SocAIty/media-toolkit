"""
PureMagic-based content type detector for media files.
Uses magic bytes detection to identify file types from file content.
"""
import io
from dataclasses import dataclass
from typing import Optional, Union

import puremagic


@dataclass(frozen=True)
class MagicDetection:
    extension: Optional[str]
    mime_type: Optional[str]


class PureMagicContentDetector:
    """
    Thin wrapper around puremagic that extracts extension and mime type guesses.
    Higher-level mapping and fallbacks are handled by ContentDetector.
    """

    @classmethod
    def detect_from_universal_file(cls, universal_file) -> MagicDetection:
        try:
            matches = puremagic.magic_stream(universal_file._content_buffer)
            best_match = cls._best_match(matches)
            return cls._build_detection(best_match)
        except Exception:
            return MagicDetection(None, None)

    @classmethod
    def detect_from_path(cls, file_path: str) -> MagicDetection:
        try:
            matches = puremagic.magic_file(file_path)
            best_match = cls._best_match(matches)
            return cls._build_detection(best_match)
        except Exception:
            return MagicDetection(None, None)

    @classmethod
    def detect_from_buffer(cls, buffer: Union[io.BytesIO, bytes]) -> MagicDetection:
        try:
            content_bytes = cls._extract_bytes(buffer)
            if not content_bytes:
                return MagicDetection(None, None)

            matches = puremagic.magic_string(content_bytes)
            best_match = cls._best_match(matches)
            return cls._build_detection(best_match)
        except Exception:
            return MagicDetection(None, None)

    @staticmethod
    def _best_match(matches):
        if not matches:
            return None
        return matches[0]

    @staticmethod
    def _build_detection(match) -> MagicDetection:
        if match is None:
            return MagicDetection(None, None)

        extension = getattr(match, 'extension', None)
        normalized_extension = PureMagicContentDetector._clean_extension(extension)
        mime_type = getattr(match, 'mime_type', None)
        return MagicDetection(normalized_extension, mime_type)

    @staticmethod
    def _extract_bytes(buffer: Union[io.BytesIO, bytes]) -> Optional[bytes]:
        if isinstance(buffer, bytes):
            return buffer[:1024]
        if hasattr(buffer, 'read'):
            current_pos = buffer.tell() if hasattr(buffer, 'tell') else 0
            buffer.seek(0)
            content_bytes = buffer.read(1024)
            buffer.seek(current_pos)
            return content_bytes
        return None

    @staticmethod
    def _clean_extension(extension: Optional[str]) -> Optional[str]:
        if not extension:
            return None
        extension = extension.lower().strip()
        if extension.startswith('.'):
            extension = extension[1:]
        return extension or None


