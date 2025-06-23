"""
Utility functions for data type detection and validation.
Extracted from the previous media_type_guesser for reuse across the codebase.
"""
import os
from urllib.parse import urlparse


def is_valid_file_path(path: str) -> bool:
    """Efficiently check if string is a valid file path."""
    try:
        return isinstance(path, str) and os.path.isfile(path)
    except (OSError, ValueError, TypeError):
        return False


def is_url(url: str) -> bool:
    """Efficiently check if string is a valid URL."""
    if not isinstance(url, str) or len(url) < 7:  # Minimum: http://
        return False
    
    try:
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https', 'ftp', 'file') and bool(parsed.netloc or parsed.path)
    except Exception:
        return False


def is_starlette_upload_file(data) -> bool:
    """Check if data is a Starlette UploadFile."""
    return (hasattr(data, '__module__') and 
            hasattr(data, '__class__') and
            data.__module__ == 'starlette.datastructures' and 
            data.__class__.__name__ == 'UploadFile')


def is_file_model_dict(data: dict) -> bool:
    """Check if dictionary matches FileModel format."""
    if not isinstance(data, dict):
        if not hasattr(data, "__dict__"):
            return False
        try:
            data = dict(data)
        except Exception:
            return False

    return "file_name" in data and "content" in data


def is_numpy_array_like(data) -> bool:
    """Check if data is a numpy array or array-like object."""
    return (type(data).__name__ == 'ndarray' or 
            hasattr(data, '__array__') or 
            (hasattr(data, 'dtype') and hasattr(data, 'shape')))


def extract_extension(filename: str) -> str:
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
