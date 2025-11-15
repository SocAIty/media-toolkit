"""
Centralized file-type metadata used across detection strategies.
"""

# Mapping from file extension (without dot) to target media class
EXTENSION_TO_CLASS = {
    # Image formats - fully supported
    'jpg': 'ImageFile',
    'jpeg': 'ImageFile',
    'png': 'ImageFile',
    'gif': 'ImageFile',
    'bmp': 'ImageFile',
    'tiff': 'ImageFile',
    'tif': 'ImageFile',
    'jfif': 'ImageFile',

    # Image formats - limited support (use MediaFile)
    'ico': 'MediaFile',
    'webp': 'MediaFile',
    'avif': 'MediaFile',
    'heic': 'MediaFile',
    'heif': 'MediaFile',
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

    # 3D Model formats
    'obj': 'MediaFile',
    'glb': 'MediaFile',
    'gltf': 'MediaFile',
    'dae': 'MediaFile',
    'fbx': 'MediaFile',
    '3ds': 'MediaFile',
    'ply': 'MediaFile',
    'stl': 'MediaFile',
    'step': 'MediaFile',
    'iges': 'MediaFile',
    'x3d': 'MediaFile',
    'blend': 'MediaFile',

    # Data formats
    'npy': 'MediaFile',
    'npz': 'MediaFile',
    'pkl': 'MediaFile',
    'pickle': 'MediaFile',

    # Document and text formats
    'pdf': 'MediaFile',
    'txt': 'MediaFile',
    'html': 'MediaFile',
    'htm': 'MediaFile',
    'json': 'MediaFile',
    'js': 'MediaFile',
    'css': 'MediaFile',
    'xml': 'MediaFile',
    'csv': 'MediaFile',

    # Archives
    'zip': 'MediaFile',
    '7z': 'MediaFile',
    'tar': 'MediaFile',
    'gz': 'MediaFile'
}

# MIME type mapping per extension (without dot)
EXTENSION_TO_MIME = {
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

    # 3D Models
    'obj': 'model/obj',
    'glb': 'model/gltf-binary',
    'gltf': 'model/gltf+json',
    'dae': 'model/vnd.collada+xml',
    'fbx': 'application/octet-stream',
    '3ds': 'application/x-3ds',
    'ply': 'application/x-ply',
    'stl': 'model/stl',
    'step': 'application/step',
    'iges': 'model/iges',
    'x3d': 'model/x3d+xml',
    'blend': 'application/x-blender',

    # Data
    'npy': 'application/x-npy',
    'npz': 'application/x-npz',
    'pkl': 'application/x-pickle',
    'pickle': 'application/x-pickle',

    # Documents and text
    'pdf': 'application/pdf',
    'txt': 'text/plain',
    'html': 'text/html',
    'htm': 'text/html',
    'json': 'application/json',
    'js': 'application/javascript',
    'css': 'text/css',
    'xml': 'application/xml',
    'csv': 'text/csv',

    # Archives
    'zip': 'application/zip',
    '7z': 'application/x-7z-compressed',
    'tar': 'application/x-tar',
    'gz': 'application/gzip'
}

# Default extension suggestion given a broad media type
MEDIA_TYPE_DEFAULT_EXTENSION = {
    'image': 'png',
    'video': 'mp4',
    'audio': 'wav',
    'file': 'npy',
    'npy': 'npy'
}


def mime_to_extension(mime_type: str) -> str:
    """
    Convert MIME type back to file extension by reversing the EXTENSION_TO_MIME mapping.

    Args:
        mime_type: MIME type string (e.g., 'image/jpeg')

    Returns:
        File extension without dot (e.g., 'jpg'), or None if not found
    """
    # Create reverse mapping on demand for efficiency
    # This could be cached if performance becomes an issue
    extension_to_mime_reverse = {v: k for k, v in EXTENSION_TO_MIME.items()}
    return extension_to_mime_reverse.get(mime_type)


__all__ = ['EXTENSION_TO_CLASS', 'EXTENSION_TO_MIME', 'MEDIA_TYPE_DEFAULT_EXTENSION', 'mime_to_extension']
