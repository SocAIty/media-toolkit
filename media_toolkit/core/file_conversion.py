"""
Refactored file conversion utilities using content detectors.
Provides generalized file handling with automatic type detection.
"""
import inspect
from typing import Union, Any, Optional, Type
from media_toolkit.core.IMediaFile import IMediaFile
from media_toolkit.core.universal_file import UniversalFile
from media_toolkit.core.content_detectors import PureMagicContentDetector, NumpyContentTypeDetector
from media_toolkit.utils.data_type_utils import (
    is_numpy_array_like, is_file_model_dict,
    is_valid_file_path
)

# Import directly from core modules to avoid circular imports
from media_toolkit.core.media_file import MediaFile
from media_toolkit.core.image_file import ImageFile
from media_toolkit.core.audio_file import AudioFile
from media_toolkit.core.video.video_file import VideoFile

MediaFileType = Union[MediaFile, ImageFile, AudioFile, VideoFile]


def _resolve_media_class(class_name: str) -> Type[IMediaFile]:
    """Resolve media class name to actual class."""
    class_map = {
        'MediaFile': MediaFile,
        'ImageFile': ImageFile,
        'AudioFile': AudioFile,
        'VideoFile': VideoFile
    }
    return class_map.get(class_name, MediaFile)


def _interpret_type_hint(type_hint) -> Optional[str]:
    """
    Convert type_hint to media class name.
    
    Args:
        type_hint: Can be:
            - IMediaFile subclass instance/class
            - String like "image", "audio", "video", "npy"
            - File extension like "jpg", "mp3", "mp4"
            
    Returns:
        Media class name or None if invalid
    """
    if type_hint is None:
        return None
    
    # Handle class instances or classes
    if inspect.isclass(type_hint) and issubclass(type_hint, IMediaFile):
        return type_hint.__name__
    elif isinstance(type_hint, IMediaFile):
        return type_hint.__class__.__name__
    
    # Handle string hints
    if isinstance(type_hint, str):
        type_hint = type_hint.lower().strip()
        
        # Direct media type mapping
        type_mappings = {
            'image': 'ImageFile',
            'audio': 'AudioFile', 
            'video': 'VideoFile',
            'npy': 'MediaFile',
            'numpy': 'MediaFile',
        }
        
        if type_hint in type_mappings:
            return type_mappings[type_hint]
        
        # Extension-based mapping
        extension_mappings = {
            # Images
            'jpg': 'ImageFile', 'jpeg': 'ImageFile', 'png': 'ImageFile',
            'gif': 'ImageFile', 'bmp': 'ImageFile', 'tiff': 'ImageFile',
            'tif': 'ImageFile', 'ico': 'ImageFile', 'svg': 'ImageFile',
            # Limited support
            'webp': 'MediaFile',
            'avif': 'MediaFile',
            'heic': 'MediaFile',
            'heif': 'MediaFile',
            
            # Audio
            'wav': 'AudioFile', 'mp3': 'AudioFile', 'ogg': 'AudioFile',
            'flac': 'AudioFile', 'aac': 'AudioFile', 'm4a': 'AudioFile',
            'wma': 'AudioFile', 'opus': 'AudioFile', 'aiff': 'AudioFile',
            
            # Video
            'mp4': 'VideoFile', 'avi': 'VideoFile', 'mov': 'VideoFile',
            'mkv': 'VideoFile', 'webm': 'VideoFile', 'flv': 'VideoFile',
            'wmv': 'VideoFile', '3gp': 'VideoFile', 'ogv': 'VideoFile',
            'm4v': 'VideoFile',
        }
        
        return extension_mappings.get(type_hint, None)
    
    return None


def media_from_numpy(
    np_array,
    type_hint=None,
    use_temp_file: bool = False,
    temp_dir: Optional[str] = None
) -> MediaFileType:
    """
    Convert numpy array to appropriate media file with type detection and hint support.
    
    Args:
        np_array: Numpy array to convert
        type_hint: Optional hint for target media type (class, string, or extension)
        use_temp_file: Use temporary file for large files
        temp_dir: Directory for temporary files
        
    Returns:
        Appropriate media file instance
    """
    # First try to use the type hint if provided
    hint_class_name = _interpret_type_hint(type_hint)
    
    if hint_class_name:
        try:
            target_class = _resolve_media_class(hint_class_name)
            instance = target_class(use_temp_file=use_temp_file, temp_dir=temp_dir)
            
            # Try to create from numpy array using the hinted class
            if hasattr(instance, 'from_np_array'):
                return instance.from_np_array(np_array)
            else:
                # Fallback: use UniversalFile method then transfer to target class
                universal = UniversalFile(use_temp_file, temp_dir)
                universal.from_np_array(np_array)
                
                target_instance = target_class(use_temp_file=use_temp_file, temp_dir=temp_dir)
                target_instance.from_bytes(universal.to_bytes())
                return target_instance
                
        except Exception:
            # If hint fails, continue to auto-detection
            pass
    
    # Auto-detect using NumpyContentTypeDetector
    try:
        media_type, extension = NumpyContentTypeDetector.detect_numpy_content_type(np_array)
        detected_class_name = _interpret_type_hint(extension)
        target_class = _resolve_media_class(detected_class_name)
        instance = target_class(use_temp_file=use_temp_file, temp_dir=temp_dir)
        
        # Try to create from numpy array 
        if hasattr(instance, 'from_np_array'):
            return instance.from_np_array(np_array)
        else:
            # Fallback: use UniversalFile method
            universal = UniversalFile(use_temp_file, temp_dir)
            universal.from_np_array(np_array)
            
            instance.from_bytes(universal.to_bytes())
            return instance
            
    except Exception:
        # Final fallback to MediaFile
        fallback = MediaFile(use_temp_file=use_temp_file, temp_dir=temp_dir)
        universal = UniversalFile(use_temp_file, temp_dir)
        universal.from_np_array(np_array)
        fallback.from_bytes(universal.to_bytes())
        return fallback


def media_from_any(
    data: Any,
    type_hint=None,
    use_temp_file: bool = False,
    temp_dir: Optional[str] = None,
    allow_reads_from_disk: bool = True
) -> MediaFileType:
    """
    Convert any file input to appropriate media file with automatic type detection and hint support.

    Args:
        data: Input data (file path, URL, base64, bytes, numpy array, file handle, etc.)
        type_hint: Optional hint for target media type (class, string, or extension)
        use_temp_file: Use temporary file for large files
        temp_dir: Directory for temporary files
        allow_reads_from_disk: Allow reading from disk (disable in web environments)

    Returns:
        Appropriate media file instance (ImageFile, AudioFile, VideoFile, or MediaFile)
    """
    # Return as-is if already a media file
    if isinstance(data, IMediaFile):
        return data

    # Handle numpy arrays specially
    if is_numpy_array_like(data):
        return media_from_numpy(data, type_hint, use_temp_file, temp_dir)

    # Handle FileModel dictionaries with type hint preference
    if is_file_model_dict(data):
        if type_hint:
            # Use type_hint to override content_type
            hint_class_name = _interpret_type_hint(type_hint)
            if hint_class_name:
                try:
                    target_class = _resolve_media_class(hint_class_name)
                    instance = target_class(use_temp_file=use_temp_file, temp_dir=temp_dir)
                    return instance.from_dict(data)
                except Exception:
                    pass
        
        # Fallback to content_type in FileModel
        content_type = data.get('content_type', '').lower()
        if 'image' in content_type:
            target_class_name = 'ImageFile'
        elif 'audio' in content_type:
            target_class_name = 'AudioFile'
        elif 'video' in content_type:
            target_class_name = 'VideoFile'
        else:
            target_class_name = 'MediaFile'
            
        target_class = _resolve_media_class(target_class_name)
        instance = target_class(use_temp_file=use_temp_file, temp_dir=temp_dir)
        return instance.from_dict(data)

    # Load data into UniversalFile first
    universal = UniversalFile(use_temp_file, temp_dir)
    universal.from_any(data, allow_reads_from_disk=allow_reads_from_disk)

    # Determine target class using type hint first, then content detection
    target_class_name = None
    
    if type_hint:
        target_class_name = _interpret_type_hint(type_hint)
    
    # If no valid hint, use magic content detection
    if not target_class_name:
        try:
            detected_class_name, content_type, extension = PureMagicContentDetector.detect_from_universal_file(universal)
            target_class_name = detected_class_name
        except Exception:
            target_class_name = 'MediaFile'

    # Create target instance and transfer content
    target_class = _resolve_media_class(target_class_name)
    
    try:
        instance = target_class(use_temp_file=use_temp_file, temp_dir=temp_dir)
        instance.from_bytes(universal.to_bytes())
        return instance
    except Exception:
        pass
        
    # Fallback to MediaFile if target class fails. Will throw an error if the file is not a valid media file.
    fallback = MediaFile(use_temp_file=use_temp_file, temp_dir=temp_dir)
    fallback.from_bytes(universal.to_bytes())
    return fallback


# Legacy compatibility functions
def media_from_file(file_path: str) -> MediaFileType:
    """Create appropriate media file instance from file path with automatic type detection."""
    return media_from_any(file_path)


def media_from_FileModel(
    file_result: dict,
    allow_reads_from_disk: bool = False,
    default_return_if_not_file_result: Any = None
) -> MediaFileType:
    """
    Convert FileModel dictionary to appropriate media file.

    Args:
        file_result: Dictionary with 'content_type', 'content', and 'file_name'
        allow_reads_from_disk: Allow reading from disk (security risk)
        default_return_if_not_file_result: Default return for invalid input

    Returns:
        Appropriate media file instance
    """
    # Handle non-dict inputs
    if not isinstance(file_result, dict):
        if hasattr(file_result, "__dict__"):
            try:
                file_result = dict(file_result)
            except Exception:
                return default_return_if_not_file_result
        else:
            return default_return_if_not_file_result

    # Validate FileModel format
    if not is_file_model_dict(file_result):
        if default_return_if_not_file_result is not None:
            return default_return_if_not_file_result
        raise ValueError("file_result must contain 'file_name' and 'content' keys")

    # Security check
    content = file_result.get('content', file_result)
    if not allow_reads_from_disk and is_valid_file_path(content):
        raise ValueError("Reading files from disk is not allowed (security risk)")

    return media_from_any(file_result, allow_reads_from_disk=allow_reads_from_disk)
