"""
PureMagic-based content type detector for media files.
Uses magic bytes detection to identify file types from file content.
"""
import io
from typing import Optional, Union, Tuple

import puremagic


class PureMagicContentDetector:
    """
    Content type detector using puremagic for magic bytes analysis.
    Works with UniversalFile/FileContentBuffer to detect file types from content.
    """
    
    # Mapping from puremagic extensions to media classes
    _EXTENSION_TO_CLASS = {
        # Image formats - fully supported
        'jpg': 'ImageFile',
        'jpeg': 'ImageFile',
        'png': 'ImageFile',
        'gif': 'ImageFile',  # Only single frame in cv2
        'bmp': 'ImageFile',
        'tiff': 'ImageFile',
        'tif': 'ImageFile',
        'jfif': 'ImageFile',

        # Image formats - limited support (use MediaFile).
        # Consider install of pillow
        'ico': 'MediaFile',
        'webp': 'MediaFile',  # Not fully supported in ImageFile yet
        'avif': 'MediaFile',  # AVIF not widely supported yet
        'heic': 'MediaFile',  # HEIC requires special libraries
        'heif': 'MediaFile',  # HEIF requires special libraries
        'svg': 'MediaFile',
        
        # Audio formats
        'wav': 'AudioFile',
        'mp3': 'AudioFile',
        'ogg': 'AudioFile',
        'flac': 'AudioFile',
        'aac': 'AudioFile',
        'm4a': 'AudioFile',
        'wma': 'AudioFile',
        'opus': 'AudioFile',
        'aiff': 'AudioFile',
        
        # Video formats
        'mp4': 'VideoFile',
        'avi': 'VideoFile',
        'mov': 'VideoFile',
        'mkv': 'VideoFile',
        'webm': 'VideoFile',
        'flv': 'VideoFile',
        'wmv': 'VideoFile',
        '3gp': 'VideoFile',
        'ogv': 'VideoFile',
        'm4v': 'VideoFile',
        
        # Data formats
        'npy': 'MediaFile',
        'npz': 'MediaFile',
        'pkl': 'MediaFile',
        'pickle': 'MediaFile',
        
        # Generic formats
        'txt': 'MediaFile',
        'csv': 'MediaFile', 
        'json': 'MediaFile',
        'xml': 'MediaFile',
        'pdf': 'MediaFile',
        'zip': 'MediaFile',
        '7z': 'MediaFile',
        'tar': 'MediaFile',
        'gz': 'MediaFile'
    }
    
    @classmethod
    def detect_from_universal_file(cls, universal_file) -> Tuple[str, str, Optional[str]]:
        """
        Detect content type from UniversalFile using puremagic.
        
        Args:
            universal_file: UniversalFile instance with content buffer
            
        Returns:
            Tuple of (media_class_name, content_type, file_extension)
        """
        try:
            # Use puremagic to detect file type
            matches = puremagic.magic_stream(universal_file._content_buffer)
            
            if not matches or len(matches) == 0:
                return 'MediaFile', 'application/octet-stream', None

            # Get the best match (highest confidence)
            best_match = matches[0]
            extension = best_match.extension.lower().replace('.', '') if best_match.extension else None
            mime_type = best_match.mime_type if hasattr(best_match, 'mime_type') else None
            
            # Map extension to media class
            media_class = cls._EXTENSION_TO_CLASS.get(extension, 'MediaFile')
            
            # Use detected mime type or construct from extension
            if mime_type:
                content_type = mime_type
            elif extension:
                content_type = cls._extension_to_mime_type(extension)
            else:
                content_type = 'application/octet-stream'
                
            return media_class, content_type, extension
                
        except Exception:
            # Fallback if puremagic fails
            pass
            
        return 'MediaFile', 'application/octet-stream', None
    
    @classmethod
    def detect_from_buffer(cls, buffer: Union[io.BytesIO, bytes]) -> Tuple[str, str, Optional[str]]:
        """
        Detect content type from bytes or buffer using puremagic.
        
        Args:
            buffer: BytesIO buffer or raw bytes
            
        Returns:
            Tuple of (media_class_name, content_type, file_extension)
        """
        try:
            if isinstance(buffer, bytes):
                content_bytes = buffer[:1024]  # First 1KB
            elif hasattr(buffer, 'read'):
                current_pos = buffer.tell() if hasattr(buffer, 'tell') else 0
                buffer.seek(0)
                content_bytes = buffer.read(1024)
                buffer.seek(current_pos)
            else:
                return 'MediaFile', 'application/octet-stream', None
                
            if not content_bytes:
                return 'MediaFile', 'application/octet-stream', None
                
            # Use puremagic to detect file type
            matches = puremagic.magic_string(content_bytes)
            
            if matches:
                # Get the best match (highest confidence)
                best_match = matches[0]
                extension = best_match.extension.lower() if best_match.extension else None
                mime_type = best_match.mime_type if hasattr(best_match, 'mime_type') else None
                
                # Map extension to media class
                media_class = cls._EXTENSION_TO_CLASS.get(extension, 'MediaFile')
                
                # Use detected mime type or construct from extension
                if mime_type:
                    content_type = mime_type
                elif extension:
                    content_type = cls._extension_to_mime_type(extension)
                else:
                    content_type = 'application/octet-stream'
                    
                return media_class, content_type, extension
                
        except Exception:
            pass
            
        return 'MediaFile', 'application/octet-stream', None
    
    @staticmethod
    def _extension_to_mime_type(extension: str) -> str:
        """Convert file extension to MIME type."""
        extension_mime_map = {
            # Images
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'bmp': 'image/bmp',
            'tiff': 'image/tiff',
            'tif': 'image/tiff',
            'ico': 'image/x-icon',
            'svg': 'image/svg+xml',
            'webp': 'image/webp',
            'avif': 'image/avif',
            'heic': 'image/heic',
            'heif': 'image/heif',
            'jfif': 'image/jpeg',
            
            # Audio
            'wav': 'audio/wav',
            'mp3': 'audio/mpeg',
            'ogg': 'audio/ogg',
            'flac': 'audio/flac',
            'aac': 'audio/aac',
            'm4a': 'audio/mp4',
            'wma': 'audio/x-ms-wma',
            'opus': 'audio/opus',
            'aiff': 'audio/aiff',
            
            # Video
            'mp4': 'video/mp4',
            'avi': 'video/x-msvideo',
            'mov': 'video/quicktime',
            'mkv': 'video/x-matroska',
            'webm': 'video/webm',
            'flv': 'video/x-flv',
            'wmv': 'video/x-ms-wmv',
            '3gp': 'video/3gpp',
            'ogv': 'video/ogg',
            'm4v': 'video/x-m4v',
            
            # Data
            'npy': 'file/npy',
            'npz': 'file/npz',
            'pkl': 'file/pickle',
            'pickle': 'file/pickle',
            'zip': 'file/zip',
            '7z': 'file/7z',
            'tar': 'file/tar',
            'gz': 'file/gzip'
        }
        
        return extension_mime_map.get(extension.lower(), 'application/octet-stream')