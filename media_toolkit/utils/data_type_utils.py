"""
Utility functions for data type detection and validation.
Extracted from the previous media_type_guesser for reuse across the codebase.
"""
import os
import re
from urllib.parse import urlparse


def is_valid_file_path(path: str) -> bool:
    """
    Efficiently check if string is a valid file path.
    Returns true if is a valid path and the file exists.
    """
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


def is_likely_base64(s: str) -> bool:
    """
    Check if string is likely a base64 encoded string.
    It does not check if the base64 is valid and does not try to decode it.
    It enforces a minimum length for raw base64 strings to avoid false positives with common words.
    """
    if not isinstance(s, str):
        return False

    s = s.strip()
    
    # Check for Data URI with base64
    if s.lower().startswith("data:"):
        return ";base64," in s[:50].lower()

    # For raw base64, enforce minimum length to avoid false positives like "word", "play"
    # 100 chars is approx 75 bytes, reasonable minimum for a media file
    if len(s) < 100:
        return False
    
    # Base64 length must be a multiple of 4
    if len(s) % 4 != 0:
        return False

    # Match allowed characters and optional padding
    base64_regex = re.compile(r'^[A-Za-z0-9+/]+={0,2}$')
    if not base64_regex.match(s):
        return False

    # Padding rules: if padding is present, it must be at the end
    if '=' in s:
        if s.count('=') > 2 or not s.endswith('=' * s.count('=')):
            return False

    return True
