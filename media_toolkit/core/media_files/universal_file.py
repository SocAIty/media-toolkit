import base64
import io
import os
import re
from typing import Union, BinaryIO, Tuple, Optional

from media_toolkit.core.media_files.i_media_file import IMediaFile
from media_toolkit.core.media_files.file_content_buffer import FileContentBuffer
from media_toolkit.utils.dependency_requirements import requires_numpy
from media_toolkit.utils.download_helper import download_file
from media_toolkit.utils.data_type_utils import is_valid_file_path, is_url, is_starlette_upload_file, is_likely_base64

try:
    import numpy as np
except ImportError:
    pass


class UniversalFile(IMediaFile):
    """
    Universal file handler that works with any file type across the web and SDK.
    Provides standardized conversions for BytesIO, base64, binary data, and various file sources.
    
    This is a pure data handling class without any metadata (file_name, content_type, etc).
    
    Features:
    - Support for files, URLs, base64, bytes, numpy arrays, and upload files
    - Optional temporary file storage for large files
    - Pure data operations without content type detection or metadata
    """
    
    def __init__(
            self,
            use_temp_file: bool = False,
            temp_dir: str = None
    ):
        """
        Initialize UniversalFile with storage configuration only.
        
        Args:
            use_temp_file: Use temporary file storage for large files
            temp_dir: Directory for temporary files (uses system default if None)
        """
        self._content_buffer = FileContentBuffer(use_temp_file=use_temp_file, temp_dir=temp_dir)

    def from_any(self, data, allow_reads_from_disk: bool = True, **kwargs):
        """
        Universal loader supporting any data type with automatic detection.
        
        Args:
            data: Input data (file path, URL, base64, bytes, numpy array, file handle, etc.)
            allow_reads_from_disk: Enable file system access (disable in web environments)
            **kwargs: Additional arguments for other methods like headers for the from_url method.
            
        Returns:
            Self for method chaining
        """
        if data is None:
            return None

        # Return as-is if already a UniversalFile or subclass
        if isinstance(data, UniversalFile):
            return data

        # Route to appropriate handler based on data type
        try:
            if isinstance(data, (io.BufferedReader, io.BytesIO)):
                self.from_bytesio_or_handle(data)
            elif isinstance(data, str):
                if is_valid_file_path(data):
                    if not allow_reads_from_disk:
                        raise ValueError(f"Reads from disk disabled {data}.")
                    else:
                        self.from_file(data)
                elif is_url(data):
                    self.from_url(data, headers=kwargs.get("headers", None))
                elif is_likely_base64(data):
                    self.from_base64(data)
                else:
                    raise ValueError(f"Could not parse as file path, URL, or base64: {data}. Your string is likely not a valid file.")
                   
            elif isinstance(data, bytes):
                self.from_bytes(data)
            elif type(data).__name__ == 'ndarray' or hasattr(data, '__array__') or (hasattr(data, 'dtype') and hasattr(data, 'shape')):
                # Numpy array or array-like
                self.from_np_array(data)
            elif is_starlette_upload_file(data):
                self.from_starlette_upload_file(data)
            else:
                raise ValueError(f"Unsupported data type: {type(data)}")
        except Exception as e:
            raise ValueError(f"MediaFile.from_any failed: type {type(data)}: {e}")

        return self

    def from_bytesio_or_handle(
            self,
            buffer: Union[io.BytesIO, BinaryIO, io.BufferedReader],
            copy: bool = True
    ):
        """
        Load content from BytesIO or file handle with optional copying.
        
        Args:
            buffer: Source buffer to read from
            copy: If True, reads entire buffer to bytes. If False, keeps reference (not thread-safe)
            
        Returns:
            Self for method chaining
        """
        if not isinstance(buffer, (io.BytesIO, io.BufferedReader)):
            raise ValueError(f"Buffer must be BytesIO or BufferedReader, got {type(buffer)}")

        self._reset_buffer()
        buffer.seek(0)

        if not copy:
            self._content_buffer.overwrite_buffer(buffer)
        else:
            self.from_bytes(buffer.read())
            buffer.seek(0)

        return self

    def from_bytesio(self, buffer: Union[io.BytesIO, BinaryIO], copy: bool = True):
        """Backwards compatible alias for from_bytesio_or_handle."""
        return self.from_bytesio_or_handle(buffer=buffer, copy=copy)

    def from_file(self, path_or_handle: Union[str, io.BytesIO, io.BufferedReader]):
        """
        Load file from path or handle.
        
        Args:
            path_or_handle: File path string or file handle
            
        Returns:
            Self for method chaining
        """
        if isinstance(path_or_handle, (io.BufferedReader, io.BytesIO)):
            self.from_bytesio_or_handle(path_or_handle)
        elif isinstance(path_or_handle, str):
            if not os.path.exists(path_or_handle):
                raise FileNotFoundError(f"File {path_or_handle} not found.")

            with open(path_or_handle, 'rb') as file:
                self.from_bytesio_or_handle(file)

        return self

    def from_bytes(self, data: bytes):
        """Load content from raw bytes."""
        self._reset_buffer()
        self._content_buffer.write(data)
        self._content_buffer.seek(0)
        return self

    def from_starlette_upload_file(self, starlette_upload_file):
        """
        Load from Starlette UploadFile with basic data extraction.
        
        Args:
            starlette_upload_file: Starlette UploadFile object
            
        Returns:
            Self for method chaining
        """
        content = starlette_upload_file.file.read()
        if starlette_upload_file.size == 0:
            raise ValueError("UploadFile is empty.")

        self.from_bytes(content)
        return self

    def from_base64(self, base64_str: str):
        """
        Load from base64 encoded string (supports data URI format).
        
        Args:
            base64_str: Base64 string, optionally with data URI prefix
            
        Returns:
            Self for method chaining
        """
        decoded, _ = self._decode_base_64_if_is(base64_str)

        if decoded is not None:
            return self.from_bytes(decoded)
        else:
            err_str = base64_str if len(base64_str) <= 50 else base64_str[:50] + "..."
            raise ValueError(f"Could not decode base64 string: {err_str}")

    def from_np_array(self, np_array: np.array):
        """
        Load from numpy array using numpy's save format.
        
        Args:
            np_array: Numpy array to save
            
        Returns:
            Self for method chaining
        """
        self._reset_buffer()
        np.save(self._content_buffer, np_array)
        self._content_buffer.seek(0)
        return self

    def from_dict(self, file_result_json: dict, allow_reads_from_disk: bool = True):
        """
        Load from FileModel dictionary format.
        
        Args:
            file_result_json: Dictionary with 'content' key
            
        Returns:
            Self for method chaining
        """
        return self.from_any(file_result_json["content"], allow_reads_from_disk=allow_reads_from_disk)

    def from_url(self, url: str, headers: dict = None):
        """
        Download and load file from URL.
        
        Args:
            url: HTTP/HTTPS URL to download
            
        Returns:
            Self for method chaining
        """
        file, original_file_name = download_file(url, headers=headers)
        self.file_name = original_file_name
        return self.from_bytesio_or_handle(file, copy=False)

    @requires_numpy()
    def to_np_array(self, shape=None, dtype=np.uint8):
        """
        Convert to numpy array with optional reshaping.
        
        Args:
            shape: Target shape (None for flat array)
            dtype: Data type for array
            
        Returns:
            Numpy array
        """
        bytes_data = self.to_bytes()
        
        # Check if saved with np.save (has NUMPY magic bytes)
        if bytes_data.startswith(b"\x93NUMPY"):
            self._content_buffer.seek(0)
            return np.load(self._content_buffer, allow_pickle=False)

        # Convert raw bytes to array
        shape = shape or (1, len(bytes_data))
        dtype = dtype or np.uint8

        arr_flat = np.frombuffer(bytes_data, dtype=dtype)
        return arr_flat.reshape(shape)

    def to_bytes(self) -> bytes:
        """Get file content as bytes."""
        return self.read()

    def read(self, number_of_bytes: int = None) -> bytes:
        """Read file content as bytes."""
        res = self._content_buffer.read(number_of_bytes)
        return res

    def to_bytes_io(self) -> io.BytesIO:
        """Get file content as BytesIO object."""
        return self._content_buffer.to_bytes_io()

    def to_base64(self):
        """Encode file content as base64 string."""
        return base64.b64encode(self.to_bytes()).decode('ascii')

    def to_httpx_send_able_tuple(self):
        """Get tuple format suitable for HTTP client libraries."""
        # Return with generic defaults since we don't have metadata
        return "file", self.read(), "application/octet-stream"

    def _reset_buffer(self):
        """Reset internal buffer to empty state."""
        self._content_buffer.seek(0)
        self._content_buffer.truncate(0)

    def save(self, path: str = None):
        """
        Save file to disk.
        
        Args:
            path: Target file path (must include filename)
        """
        if path is None:
            path = os.path.curdir

        # Add filename if path is directory
        if os.path.isdir(path):
            if self.file_name is None:
                self.file_name = "universal_file"
                print(f"No filename given. Using {self.file_name}")
            path = os.path.join(path, self.file_name)

        dir_name = os.path.dirname(path)
        if dir_name is not None and dir_name != "":
            os.makedirs(dir_name, exist_ok=True)
            
        with open(path, 'wb') as file:
            file.write(self.read())

    def file_size(self, unit="bytes") -> int:
        """
        Get file size in specified unit.
        
        Args:
            unit: 'bytes', 'kb', 'mb', or 'gb'
            
        Returns:
            File size in specified unit
        """
        size_bytes = self._content_buffer.getbuffer().nbytes
        
        unit_multipliers = {
            "bytes": 1,
            "kb": 1000,
            "mb": 1000000,
            "gb": 1000000000
        }
        
        multiplier = unit_multipliers.get(unit.lower(), 1)
        return size_bytes / multiplier if multiplier != 1 else size_bytes

    def __bytes__(self):
        """Support bytes() conversion."""
        return self.to_bytes()

    def __array__(self):
        """Support numpy array conversion."""
        return self.to_np_array()

    def to_json(self):
        """
        Serialize to JSON-compatible dictionary.
        
        Returns:
            Dictionary with content only
        """
        return {
            "content": self.to_base64()
        }

    @staticmethod
    def _parse_base64_uri(data: str) -> Tuple[str, Optional[str]]:
        """
        Parse base64 string with optional data URI format.
        
        Args:
            data: Base64 string with optional data URI prefix
            
        Returns:
            Tuple of (base64_content, media_type)
        """
        # Data URI pattern: data:[<media type>][;base64],<data>
        data_uri_pattern = r'^data:(?P<mediatype>[\w/\-\.]+)?(?:;base64)?,(?P<base64>.*)'
        
        match = re.match(data_uri_pattern, data)
        if match:
            media_type = match.group('mediatype')
            base64_content = match.group('base64')
            return base64_content, media_type

        return data, None

    @staticmethod
    def _decode_base_64_if_is(data: Union[bytes, str]) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Validate and decode base64 data.
        
        Args:
            data: Potential base64 data (string or bytes)
            
        Returns:
            Tuple of (decoded_bytes, media_type) or (None, None) if invalid
        """
        media_type = None
        
        if isinstance(data, str):
            # Parse data URI format if present
            data, media_type = UniversalFile._parse_base64_uri(data)
            data = data.encode()

        # Validate base64 by decode/re-encode round trip
        try:
            # Decode the data
            decoded = base64.b64decode(data, validate=True)
            # Re-encode the decoded data
            back_encoded = base64.b64encode(decoded)
            # Compare with the original encoded data
            if back_encoded == data:
                return decoded, media_type
        except Exception:
            pass

        return None, None
    
    def __sizeof__(self):
        """Get total memory size including file content."""
        cls_size = super().__sizeof__()
        cls_size = cls_size if cls_size is not None else 0
        file_size = self.file_size("bytes")
        return cls_size + file_size
