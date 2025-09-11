from media_toolkit.core import MediaFile, ImageFile, VideoFile, AudioFile, MediaList, MediaDict, IMediaFile, IMediaContainer
from media_toolkit.core.file_conversion import media_from_file, media_from_any, media_from_numpy, media_from_FileModel

try:
    import importlib.metadata as metadata
except ImportError:
    # For Python < 3.8
    import importlib_metadata as metadata

try:
    __version__ = metadata.version("media-toolkit")
except Exception:
    __version__ = "0.0.0"

__all__ = [
    "MediaFile", "ImageFile", "VideoFile", "AudioFile", "MediaList", "MediaDict", "IMediaFile", "IMediaContainer",
    "media_from_file", "media_from_any", "media_from_numpy", "media_from_FileModel"
]
