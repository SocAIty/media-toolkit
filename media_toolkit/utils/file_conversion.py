import inspect
from typing import Union, Any, Optional, Type
from media_toolkit.core import IMediaFile
from media_toolkit.utils.media_type_guesser import (
    guess_media_class_name,
    guess_media_type_info,
    MediaTypeGuesser
)

# Type alias for cleaner code - import here to resolve forward references
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from media_toolkit import MediaFile, ImageFile, AudioFile, VideoFile

MediaFileType = Union['MediaFile', 'ImageFile', 'AudioFile', 'VideoFile']


def _get_media_classes():
    """Lazy import to avoid circular dependencies."""
    from media_toolkit import MediaFile, ImageFile, AudioFile, VideoFile
    return {
        'MediaFile': MediaFile,
        'ImageFile': ImageFile,
        'AudioFile': AudioFile,
        'VideoFile': VideoFile
    }


def _resolve_media_class(class_name: str) -> Type[IMediaFile]:
    """Resolve media class name to actual class."""
    class_map = _get_media_classes()
    return class_map.get(class_name, class_map['MediaFile'])


def _create_media_instance(
    target_class: Type[IMediaFile], 
    use_temp_file: bool = False, 
    temp_dir: Optional[str] = None
) -> IMediaFile:
    """Helper to create media instance with common parameters."""
    return target_class(use_temp_file=use_temp_file, temp_dir=temp_dir)


def media_from_file(file_path: str) -> MediaFileType:
    """Create appropriate media file instance from file path with automatic type detection."""
    class_name = guess_media_class_name(file_path)
    target_class = _resolve_media_class(class_name)
    return target_class().from_file(file_path)


def media_from_any(
    file,
    media_file_type: Optional[Type[IMediaFile]] = None,
    use_temp_file: bool = False,
    temp_dir: Optional[str] = None,
    allow_reads_from_disk: bool = False
) -> MediaFileType:
    """
    Convert any file input to appropriate media file with automatic type detection.

    Args:
        file: Input data (file path, URL, base64, bytes, numpy array, file handle, etc.)
        media_file_type: Force specific type, otherwise auto-detected
        use_temp_file: Use temporary file for large files
        temp_dir: Directory for temporary files
        allow_reads_from_disk: Allow reading from disk (disable in web environments)

    Returns:
        Appropriate media file instance (ImageFile, AudioFile, VideoFile, or MediaFile)
    """
    # Return as-is if already a media file
    if isinstance(file, IMediaFile):
        return file

    # Determine target class
    if media_file_type and inspect.isclass(media_file_type) and issubclass(media_file_type, IMediaFile):
        target_class = media_file_type
    else:
        try:
            # Use improved media type detection
            media_info = guess_media_type_info(file)
            target_class = _resolve_media_class(media_info.media_class_name)
        except Exception:
            class_map = _get_media_classes()
            target_class = class_map['MediaFile']

    # Create and load media file
    try:
        instance = _create_media_instance(target_class, use_temp_file, temp_dir)
        return instance.from_any(file, allow_reads_from_disk=allow_reads_from_disk)
    except Exception as e:
        # Fallback to MediaFile if guessed type fails
        class_map = _get_media_classes()
        if target_class != class_map['MediaFile']:
            try:
                fallback = _create_media_instance(class_map['MediaFile'], use_temp_file, temp_dir)
                return fallback.from_any(file, allow_reads_from_disk=allow_reads_from_disk)
            except Exception:
                pass
        raise e


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
    if not MediaTypeGuesser._is_file_model_dict(file_result):
        if default_return_if_not_file_result is not None:
            return default_return_if_not_file_result
        raise ValueError("file_result must contain 'file_name' and 'content' keys")

    # Security check
    content = file_result.get('content', file_result)
    if not allow_reads_from_disk and MediaTypeGuesser._is_valid_file_path(content):
        raise ValueError("Reading files from disk is not allowed (security risk)")

    # Create appropriate media file using improved detection
    try:
        media_info = guess_media_type_info(file_result)
        target_class = _resolve_media_class(media_info.media_class_name)
        return target_class().from_dict(file_result)
    except Exception:
        # Fallback to MediaFile
        class_map = _get_media_classes()
        return class_map['MediaFile']().from_dict(file_result)
