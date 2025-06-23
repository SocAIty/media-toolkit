"""
Comprehensive media type detection system with fast MIME type detection,
extensible design patterns, and backwards compatibility.
"""

import os
import mimetypes
from typing import Optional, NamedTuple, Any
from urllib.parse import urlparse


class MediaTypeInfo(NamedTuple):
    """Container for comprehensive media type information."""
    media_class_name: str  # 'MediaFile', 'ImageFile', 'AudioFile', 'VideoFile'
    content_type: str      # 'image/png', 'video/mp4', 'file/npy', etc.
    file_extension: Optional[str] = None  # 'png', 'mp4', 'npy', etc.
    is_supported: bool = True  # Whether format is fully supported


class MediaTypeGuesser:
    """
    Ultra-fast and comprehensive media type detection system.
    
    Features:
    - Lightning-fast detection using native mimetypes first
    - Comprehensive extension-based fallback detection
    - Optional deep content inspection for edge cases
    - Support for specialized formats (numpy arrays, etc.)
    - Fully decoupled from MediaFile implementations
    - Extensible design for future media types
    """
    
    # Core extension mappings optimized for performance
    _EXTENSION_MAPPINGS = {
        # Image formats - fully supported
        'jpg': ('ImageFile', 'image/jpeg'),
        'jpeg': ('ImageFile', 'image/jpeg'),
        'png': ('ImageFile', 'image/png'),
        'gif': ('ImageFile', 'image/gif'),
        'bmp': ('ImageFile', 'image/bmp'),
        'tiff': ('ImageFile', 'image/tiff'),
        'tif': ('ImageFile', 'image/tiff'),
        'ico': ('ImageFile', 'image/x-icon'),
        'svg': ('ImageFile', 'image/svg+xml'),
        
        # Image formats - limited support (use MediaFile)
        'webp': ('MediaFile', 'image/webp'),  # Not fully supported in ImageFile yet
        'avif': ('MediaFile', 'image/avif'),
        'heic': ('MediaFile', 'image/heic'),
        'heif': ('MediaFile', 'image/heif'),
        
        # Audio formats
        'wav': ('AudioFile', 'audio/wav'),
        'mp3': ('AudioFile', 'audio/mpeg'),
        'ogg': ('AudioFile', 'audio/ogg'),
        'flac': ('AudioFile', 'audio/flac'),
        'aac': ('AudioFile', 'audio/aac'),
        'm4a': ('AudioFile', 'audio/mp4'),
        'wma': ('AudioFile', 'audio/x-ms-wma'),
        'opus': ('AudioFile', 'audio/opus'),
        'aiff': ('AudioFile', 'audio/aiff'),
        
        # Video formats
        'mp4': ('VideoFile', 'video/mp4'),
        'avi': ('VideoFile', 'video/x-msvideo'),
        'mov': ('VideoFile', 'video/quicktime'),
        'mkv': ('VideoFile', 'video/x-matroska'),
        'webm': ('VideoFile', 'video/webm'),
        'flv': ('VideoFile', 'video/x-flv'),
        'wmv': ('VideoFile', 'video/x-ms-wmv'),
        '3gp': ('VideoFile', 'video/3gpp'),
        'ogv': ('VideoFile', 'video/ogg'),
        'm4v': ('VideoFile', 'video/x-m4v'),
        
        # Numpy and scientific data formats
        'npy': ('MediaFile', 'file/npy'),
        'npz': ('MediaFile', 'file/npz'),
        'pickle': ('MediaFile', 'file/pickle'),
        'pkl': ('MediaFile', 'file/pickle'),
        
        # Text and document formats
        'txt': ('MediaFile', 'text/plain'),
        'csv': ('MediaFile', 'text/csv'),
        'json': ('MediaFile', 'application/json'),
        'xml': ('MediaFile', 'application/xml'),
        'yaml': ('MediaFile', 'application/x-yaml'),
        'yml': ('MediaFile', 'application/x-yaml'),
        'pdf': ('MediaFile', 'application/pdf'),
        'md': ('MediaFile', 'text/markdown'),
        
        # Archive formats
        'zip': ('MediaFile', 'application/zip'),
        'tar': ('MediaFile', 'application/x-tar'),
        'gz': ('MediaFile', 'application/gzip'),
        'bz2': ('MediaFile', 'application/x-bzip2'),
        '7z': ('MediaFile', 'application/x-7z-compressed'),
        'rar': ('MediaFile', 'application/x-rar-compressed'),
    }
    
    # Optimize MIME type to class mapping for ultra-fast lookup
    _MIME_TYPE_MAPPINGS = {
        # Image types
        'image/jpeg': 'ImageFile',
        'image/png': 'ImageFile', 
        'image/gif': 'ImageFile',
        'image/bmp': 'ImageFile',
        'image/tiff': 'ImageFile',
        'image/x-icon': 'ImageFile',
        'image/svg+xml': 'ImageFile',
        'image/webp': 'MediaFile',  # Limited support
        'image/avif': 'MediaFile',  # Limited support
        'image/heic': 'MediaFile',  # Limited support
        'image/heif': 'MediaFile',  # Limited support
        
        # Audio types
        'audio/wav': 'AudioFile',
        'audio/mpeg': 'AudioFile',
        'audio/ogg': 'AudioFile',
        'audio/flac': 'AudioFile',
        'audio/aac': 'AudioFile',
        'audio/mp4': 'AudioFile',
        'audio/x-ms-wma': 'AudioFile',
        'audio/opus': 'AudioFile',
        'audio/aiff': 'AudioFile',
        
        # Video types
        'video/mp4': 'VideoFile',
        'video/x-msvideo': 'VideoFile',
        'video/quicktime': 'VideoFile',
        'video/x-matroska': 'VideoFile',
        'video/webm': 'VideoFile',
        'video/x-flv': 'VideoFile',
        'video/x-ms-wmv': 'VideoFile',
        'video/3gpp': 'VideoFile',
        'video/ogg': 'VideoFile',
        'video/x-m4v': 'VideoFile',
    }
    
    @classmethod
    def guess_media_type(
        cls,
        data: Any,
        filename: Optional[str] = None,
        use_deep_inspection: bool = False
    ) -> MediaTypeInfo:
        """
        Ultra-fast comprehensive media type detection with multiple strategies.
        
        Detection Strategy (optimized for speed):
        1. Native mimetypes.guess_type() - fastest
        2. Extension-based lookup - very fast
        3. Content-based patterns - moderate speed
        4. Deep content inspection - slower, optional
        
        Args:
            data: Input data (file path, URL, base64, bytes, dict, etc.)
            filename: Optional filename hint for detection
            use_deep_inspection: Enable slower but more accurate content analysis
            
        Returns:
            MediaTypeInfo with detected class, content-type, and extension
        """
        # Strategy 1: Direct file path detection (leverage native mimetypes)
        if isinstance(data, str) and cls._is_valid_file_path(data):
            return cls._detect_from_file_path(data)
        
        # Strategy 2: URL detection
        if isinstance(data, str) and cls._is_url(data):
            return cls._detect_from_url(data)
        
        # Strategy 3: FileModel/dict detection
        if isinstance(data, dict) and cls._is_file_model_dict(data):
            return cls._detect_from_file_model(data)
        
        # Strategy 4: Starlette upload file
        if cls._is_starlette_upload_file(data):
            return cls._detect_from_starlette_upload_file(data)
        
        # Strategy 5: Use filename hint with native mimetypes
        if filename:
            info = cls._detect_from_filename(filename)
            if info.content_type != 'application/octet-stream':
                return info
        
        # Strategy 6: Content pattern detection (numpy arrays, etc.)
        if hasattr(data, '__array__') or (hasattr(data, 'dtype') and hasattr(data, 'shape')):
            return MediaTypeInfo('MediaFile', 'file/npy', 'npy', True)
        
        # Strategy 7: Deep content inspection (if enabled)
        if use_deep_inspection:
            content_info = cls._detect_from_content_inspection(data)
            if content_info.content_type != 'application/octet-stream':
                return content_info
        
        # Strategy 8: Fallback to generic MediaFile
        return MediaTypeInfo('MediaFile', 'application/octet-stream', None, True)
    
    @classmethod
    def _detect_from_file_path(cls, file_path: str) -> MediaTypeInfo:
        """Ultra-fast detection using native mimetypes and extension fallback."""
        # Native mimetypes detection (fastest)
        mime_type, _ = mimetypes.guess_type(file_path)
        extension = cls._extract_extension(file_path)
        
        if mime_type and mime_type in cls._MIME_TYPE_MAPPINGS:
            media_class = cls._MIME_TYPE_MAPPINGS[mime_type]
            return MediaTypeInfo(
                media_class_name=media_class,
                content_type=mime_type,
                file_extension=extension,
                is_supported=cls._is_format_supported(media_class, extension)
            )
        
        # Fast extension-based fallback
        if extension and extension.lower() in cls._EXTENSION_MAPPINGS:
            class_name, content_type = cls._EXTENSION_MAPPINGS[extension.lower()]
            return MediaTypeInfo(
                media_class_name=class_name,
                content_type=content_type,
                file_extension=extension.lower(),
                is_supported=cls._is_format_supported(class_name, extension.lower())
            )
        
        # Unknown file type
        return MediaTypeInfo('MediaFile', 'application/octet-stream', extension, True)
    
    @classmethod
    def _detect_from_url(cls, url: str) -> MediaTypeInfo:
        """Detect media type from URL path."""
        try:
            parsed_url = urlparse(url)
            path = parsed_url.path
            if path:
                # Extract filename from URL path
                filename = os.path.basename(path)
                if filename:
                    return cls._detect_from_filename(filename)
        except Exception:
            pass
        
        return MediaTypeInfo('MediaFile', 'application/octet-stream', None, True)
    
    @classmethod
    def _detect_from_filename(cls, filename: str) -> MediaTypeInfo:
        """Fast filename-based detection using native mimetypes first."""
        if not filename:
            return MediaTypeInfo('MediaFile', 'application/octet-stream', None, True)
        
        # Try native mimetypes first (fastest and most accurate)
        mime_type, _ = mimetypes.guess_type(filename)
        extension = cls._extract_extension(filename)
        
        if mime_type and mime_type in cls._MIME_TYPE_MAPPINGS:
            media_class = cls._MIME_TYPE_MAPPINGS[mime_type]
            return MediaTypeInfo(
                media_class_name=media_class,
                content_type=mime_type,
                file_extension=extension,
                is_supported=cls._is_format_supported(media_class, extension)
            )
        
        # Extension-based fallback
        if extension and extension.lower() in cls._EXTENSION_MAPPINGS:
            class_name, content_type = cls._EXTENSION_MAPPINGS[extension.lower()]
            return MediaTypeInfo(
                media_class_name=class_name,
                content_type=content_type,
                file_extension=extension.lower(),
                is_supported=cls._is_format_supported(class_name, extension.lower())
            )
        
        return MediaTypeInfo('MediaFile', 'application/octet-stream', extension, True)
    
    @classmethod
    def _detect_from_file_model(cls, file_model: dict) -> MediaTypeInfo:
        """Detect media type from FileModel dictionary."""
        content_type = file_model.get("content_type", "")
        filename = file_model.get("file_name", "")

    # FileModel specific mappings
        filemodel_mappings = {
            "octet-stream": ('MediaFile', 'application/octet-stream'),
            "image": ('ImageFile', 'image/jpeg'),  # default image
            "audio_file": ('AudioFile', 'audio/wav'),  # default audio
            "video": ('VideoFile', 'video/mp4'),  # default video
        }
        
        if content_type.lower() in filemodel_mappings:
            class_name, normalized_content_type = filemodel_mappings[content_type.lower()]
            extension = cls._extract_extension(filename) if filename else None
            return MediaTypeInfo(
                media_class_name=class_name,
                content_type=normalized_content_type,
                file_extension=extension,
                is_supported=True
            )
        
        # Standard MIME type handling
        if content_type and content_type in cls._MIME_TYPE_MAPPINGS:
            media_class = cls._MIME_TYPE_MAPPINGS[content_type]
            extension = cls._extract_extension(filename) if filename else None
            return MediaTypeInfo(
                media_class_name=media_class,
                content_type=content_type,
                file_extension=extension,
                is_supported=cls._is_format_supported(media_class, extension)
            )
        
        # Fallback to filename detection
        if filename:
            return cls._detect_from_filename(filename)
        
        return MediaTypeInfo('MediaFile', 'application/octet-stream', None, True)
    
    @classmethod
    def _detect_from_starlette_upload_file(cls, upload_file) -> MediaTypeInfo:
        """Detect media type from Starlette UploadFile."""
        content_type = getattr(upload_file, 'content_type', None)
        filename = getattr(upload_file, 'filename', None)
        
        if content_type and content_type in cls._MIME_TYPE_MAPPINGS:
            media_class = cls._MIME_TYPE_MAPPINGS[content_type]
            extension = cls._extract_extension(filename) if filename else None
            return MediaTypeInfo(
                media_class_name=media_class,
                content_type=content_type,
                file_extension=extension,
                is_supported=cls._is_format_supported(media_class, extension)
            )
        
        if filename:
            return cls._detect_from_filename(filename)
        
        return MediaTypeInfo('MediaFile', 'application/octet-stream', None, True)
    
    @classmethod
    def _detect_from_content_inspection(cls, data) -> MediaTypeInfo:
        """
        Deep content inspection using magic bytes and patterns.
        Only used when high accuracy is needed and speed is less critical.
        """
        try:
            # Extract magic bytes for analysis
            magic_bytes = cls._extract_magic_bytes(data)
            if not magic_bytes:
                return MediaTypeInfo('MediaFile', 'application/octet-stream', None, True)
            
            # Magic byte patterns for common formats
            magic_patterns = {
                # Image formats
                b'\x89PNG\r\n\x1a\n': ('ImageFile', 'image/png', 'png'),
                b'\xff\xd8\xff': ('ImageFile', 'image/jpeg', 'jpg'),
                b'GIF8': ('ImageFile', 'image/gif', 'gif'),
                b'BM': ('ImageFile', 'image/bmp', 'bmp'),
                b'RIFF': None,  # Needs deeper analysis (could be AVI or WAV)
                b'II*\x00': ('ImageFile', 'image/tiff', 'tiff'),
                b'MM\x00*': ('ImageFile', 'image/tiff', 'tiff'),
                
                # Video formats
                b'\x00\x00\x00\x18ftypmp4': ('VideoFile', 'video/mp4', 'mp4'),
                b'\x00\x00\x00\x14ftypqt': ('VideoFile', 'video/quicktime', 'mov'),
                
                # Numpy arrays
                b'\x93NUMPY': ('MediaFile', 'file/npy', 'npy'),
                
                # Archives
                b'PK\x03\x04': ('MediaFile', 'application/zip', 'zip'),
            }
            
            # Check magic patterns
            for pattern, result in magic_patterns.items():
                if magic_bytes.startswith(pattern):
                    if result is None:
                        # Handle special cases requiring deeper analysis
                        continue
                    class_name, content_type, extension = result
                    return MediaTypeInfo(
                        media_class_name=class_name,
                        content_type=content_type,
                        file_extension=extension,
                        is_supported=cls._is_format_supported(class_name, extension)
                    )
            
            # Special handling for RIFF format (AVI vs WAV)
            if magic_bytes.startswith(b'RIFF') and len(magic_bytes) >= 12:
                format_type = magic_bytes[8:12]
                if format_type == b'WAVE':
                    return MediaTypeInfo('AudioFile', 'audio/wav', 'wav', True)
                elif format_type == b'AVI ':
                    return MediaTypeInfo('VideoFile', 'video/x-msvideo', 'avi', True)
                    
        except Exception:
            pass
        
        return MediaTypeInfo('MediaFile', 'application/octet-stream', None, True)
    
    @classmethod
    def _extract_magic_bytes(cls, data, max_bytes: int = 32) -> bytes:
        """Extract magic bytes from various data types."""
        try:
            if isinstance(data, bytes):
                return data[:max_bytes]
            elif hasattr(data, 'read'):
                # File-like object
                current_pos = data.tell() if hasattr(data, 'tell') else 0
                data.seek(0)
                magic_bytes = data.read(max_bytes)
                data.seek(current_pos)
                return magic_bytes
            elif hasattr(data, '__iter__') and not isinstance(data, str):
                # Convert iterable to bytes
                return bytes(list(data)[:max_bytes])
        except Exception:
            pass
        
        return b''
    
    @classmethod
    def _extract_extension(cls, filename: str) -> Optional[str]:
        """Extract file extension efficiently."""
        if not filename or not isinstance(filename, str):
            return None
        
        # Handle URLs by extracting path component
        if '://' in filename:
            try:
                filename = urlparse(filename).path
            except Exception:
                pass
        
        # Extract extension
        if '.' in filename:
            return filename.rsplit('.', 1)[-1].lower()
        return None
    
    @classmethod
    def _is_format_supported(cls, media_class: str, extension: Optional[str]) -> bool:
        """
        Check if format is fully supported by the media class.
        Allows graceful degradation for partially supported formats.
        """
        # Known limitations
        limited_support_combinations = {
            ('ImageFile', 'webp'),  # WebP requires special handling
            ('ImageFile', 'avif'),  # AVIF not widely supported yet
            ('ImageFile', 'heic'),  # HEIC requires special libraries
            ('ImageFile', 'heif'),  # HEIF requires special libraries
        }
        
        return (media_class, extension) not in limited_support_combinations
    
    @staticmethod
    def _is_valid_file_path(path: str) -> bool:
        """Efficiently check if string is a valid file path."""
        try:
            return isinstance(path, str) and os.path.isfile(path)
        except (OSError, ValueError, TypeError):
            return False
    
    @staticmethod
    def _is_url(url: str) -> bool:
        """Efficiently check if string is a valid URL."""
        if not isinstance(url, str) or len(url) < 7:  # Minimum: http://
            return False
        
        try:
            parsed = urlparse(url)
            return parsed.scheme in ('http', 'https', 'ftp', 'file') and bool(parsed.netloc or parsed.path)
        except Exception:
            return False
    
    @staticmethod
    def _is_starlette_upload_file(data) -> bool:
        """Check if data is a Starlette UploadFile."""
        return (hasattr(data, '__module__') and 
                hasattr(data, '__class__') and
                data.__module__ == 'starlette.datastructures' and 
                data.__class__.__name__ == 'UploadFile')
    
    @staticmethod
    def _is_file_model_dict(data: dict) -> bool:
        """Check if dictionary matches FileModel format."""
        if not isinstance(data, dict):
            if not hasattr(data, "__dict__"):
                return False
            try:
                data = dict(data)
            except Exception:
                return False

        return "file_name" in data and "content" in data


# Convenience functions
def guess_media_class_name(data: Any, **kwargs) -> str:
    """Get media class name from any data type."""
    info = MediaTypeGuesser.guess_media_type(data, **kwargs)
    return info.media_class_name


def guess_content_type(data: Any, **kwargs) -> str:
    """Get content type from any data type."""
    info = MediaTypeGuesser.guess_media_type(data, **kwargs)
    return info.content_type


def guess_file_extension(data: Any, **kwargs) -> Optional[str]:
    """Get file extension from any data type."""
    info = MediaTypeGuesser.guess_media_type(data, **kwargs)
    return info.file_extension


def guess_media_type_info(data: Any, **kwargs) -> MediaTypeInfo:
    """Get comprehensive media type information."""
    return MediaTypeGuesser.guess_media_type(data, **kwargs)


def guess_media_class_from_any(data: Any) -> str:
    """DEPRECATED: Use guess_media_class_name() instead."""
    return guess_media_class_name(data)
