import io
import os
from dataclasses import dataclass
from typing import Optional, Union

from media_toolkit.core.file_types import EXTENSION_TO_CLASS, EXTENSION_TO_MIME, MEDIA_TYPE_DEFAULT_EXTENSION
from .mimetype_content_detector import MimetypeContentDetector, MimetypeDetection
from .numpy_content_detector import NumpyContentTypeDetector
from .puremagic_content_detector import MagicDetection, PureMagicContentDetector


@dataclass(frozen=True)
class DetectionResult:
    """Normalized result returned by the ContentDetector strategies."""
    media_class: str = 'MediaFile'
    content_type: str = 'application/octet-stream'
    extension: Optional[str] = None


class ContentDetector:
    """
    Facade that orchestrates multiple detection strategies (magic bytes, numpy analysis,
    extension heuristics, mimetype fallbacks) to produce consistent media metadata.
    """

    DEFAULT_MEDIA_CLASS = 'MediaFile'
    DEFAULT_CONTENT_TYPE = 'application/octet-stream'

    @classmethod
    def detect_from_universal_file(
        cls,
        universal_file,
        *,
        file_name: Optional[str] = None,
        extension_hint: Optional[str] = None
    ) -> DetectionResult:
        magic_detection = PureMagicContentDetector.detect_from_universal_file(universal_file)
        return cls._build_detection_result(
            magic_detection=magic_detection,
            file_name=file_name,
            extension_hint=extension_hint
        )

    @classmethod
    def detect_from_path(
        cls,
        file_path: str,
        *,
        extension_hint: Optional[str] = None
    ) -> DetectionResult:
        magic_detection = PureMagicContentDetector.detect_from_path(file_path)
        name_detection = MimetypeContentDetector.detect(file_path)
        return cls._build_detection_result(
            magic_detection=magic_detection,
            file_name=file_path,
            extension_hint=extension_hint,
            name_detection=name_detection
        )

    @classmethod
    def detect_from_url(
        cls,
        url: str,
        *,
        extension_hint: Optional[str] = None
    ) -> DetectionResult:
        name_detection = MimetypeContentDetector.detect(url)
        return cls._build_detection_result(
            magic_detection=MagicDetection(None, None),
            file_name=url,
            extension_hint=extension_hint,
            name_detection=name_detection
        )

    @classmethod
    def detect_from_buffer(
        cls,
        buffer: Union[io.BytesIO, bytes],
        *,
        file_name: Optional[str] = None,
        extension_hint: Optional[str] = None
    ) -> DetectionResult:
        magic_detection = PureMagicContentDetector.detect_from_buffer(buffer)
        return cls._build_detection_result(
            magic_detection=magic_detection,
            file_name=file_name,
            extension_hint=extension_hint
        )

    @classmethod
    def detect_from_numpy(cls, np_array) -> DetectionResult:
        """
        Specialized detection for numpy arrays using the numpy content detector,
        with sane defaults when numpy analysis is unavailable.
        """
        try:
            media_type, extension = NumpyContentTypeDetector.detect_numpy_content_type(np_array)
        except Exception:
            return DetectionResult()

        normalized_extension = cls._normalize_extension(extension) or cls._default_extension_for_media_type(media_type)
        media_class = cls.media_class_for_extension(normalized_extension)
        content_type = cls.mime_type_for_extension(normalized_extension)
        return DetectionResult(media_class, content_type, normalized_extension)

    @classmethod
    def media_class_for_extension(cls, extension: Optional[str]) -> str:
        normalized = cls._normalize_extension(extension)
        if not normalized:
            return cls.DEFAULT_MEDIA_CLASS
        return EXTENSION_TO_CLASS.get(normalized, cls.DEFAULT_MEDIA_CLASS)

    @classmethod
    def mime_type_for_extension(cls, extension: Optional[str]) -> str:
        normalized = cls._normalize_extension(extension)
        if not normalized:
            return cls.DEFAULT_CONTENT_TYPE
        return EXTENSION_TO_MIME.get(normalized, cls.DEFAULT_CONTENT_TYPE)

    @classmethod
    def _build_detection_result(
        cls,
        *,
        magic_detection: MagicDetection,
        file_name: Optional[str],
        extension_hint: Optional[str],
        name_detection: Optional[MimetypeDetection] = None
    ) -> DetectionResult:
        normalized_magic_ext = cls._normalize_extension(magic_detection.extension)
        normalized_hint = cls._normalize_extension(extension_hint)
        inferred_extension = cls._extension_from_name(file_name)
        name_detection = name_detection or MimetypeContentDetector.detect(file_name)
        mimetype_extension = cls._normalize_extension(
            name_detection.extension if name_detection else None
        )

        final_extension = cls._pick_first(
            normalized_magic_ext,
            normalized_hint,
            inferred_extension,
            mimetype_extension
        )

        media_class = cls.media_class_for_extension(final_extension)

        content_type = magic_detection.mime_type
        if not content_type and final_extension:
            content_type = cls.mime_type_for_extension(final_extension)
        if not content_type and name_detection:
            content_type = name_detection.mime_type
        if not content_type:
            content_type = cls.DEFAULT_CONTENT_TYPE

        return DetectionResult(
            media_class or cls.DEFAULT_MEDIA_CLASS,
            content_type or cls.DEFAULT_CONTENT_TYPE,
            final_extension
        )

    @staticmethod
    def _pick_first(*values: Optional[str]) -> Optional[str]:
        for value in values:
            if value:
                return value
        return None

    @staticmethod
    def _extension_from_name(file_name: Optional[str]) -> Optional[str]:
        if not file_name:
            return None
        base_name = os.path.basename(file_name)
        if not base_name:
            return None
        sanitized = base_name.split('?')[0].split('#')[0]
        if not sanitized:
            return None
        _, ext = os.path.splitext(sanitized)
        if not ext:
            return None
        cleaned = ext[1:].lower()
        return cleaned or None

    @staticmethod
    def _normalize_extension(extension: Optional[str]) -> Optional[str]:
        if not extension:
            return None
        extension = extension.strip().lower()
        if extension.startswith('.'):
            extension = extension[1:]
        if not extension or '/' in extension:
            return None
        return extension

    @staticmethod
    def _default_extension_for_media_type(media_type: Optional[str]) -> Optional[str]:
        if not media_type:
            return None
        return MEDIA_TYPE_DEFAULT_EXTENSION.get(media_type.lower())
