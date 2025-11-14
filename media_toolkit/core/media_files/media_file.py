import io
import os
from typing import Union, BinaryIO, Optional, Tuple
import re

from media_toolkit.core.content_detectors import ContentDetector
from media_toolkit.core.media_files.universal_file import UniversalFile
from media_toolkit.utils.dependency_requirements import requires_numpy
from media_toolkit.utils.data_type_utils import (
    is_valid_file_path, is_url, is_starlette_upload_file, is_file_model_dict
)


try:
    import numpy as np
except ImportError:
    pass


class MediaFile(UniversalFile):
    """
    Universal file handler that works with any media type across the web and SDK.
    Provides standardized conversions for BytesIO, base64, binary data, and various file sources.
    
    Features:
    - Automatic type detection using advanced content detectors
    - Support for files, URLs, base64, bytes, numpy arrays, and upload files
    - Optional temporary file storage for large files
    - Backwards compatible API
    """
    
    def __init__(
            self,
            file_name: str = None,
            content_type: str = None,
            use_temp_file: bool = False,
            temp_dir: str = None
    ):
        """
        Initialize MediaFile with optional metadata and storage configuration.
        
        Args:
            file_name: Initial filename (may be overwritten by from_* methods)
            content_type: Set a content_type. If set, the mediafile might not try to detect the content type.
            use_temp_file: Use temporary file storage for large files
            temp_dir: Directory for temporary files (uses system default if None)
        """
        super().__init__(use_temp_file, temp_dir)
        
        # Add metadata properties that UniversalFile doesn't have
        self.content_type = content_type
        self.file_name = file_name
        self.path = None  # Path if loaded from file, indicates file source

    def from_any(self, data, allow_reads_from_disk: bool = True):
        """
        Universal loader supporting any data type with automatic detection.
        Calls parent method without calling _file_info (parent methods will handle it).
        
        Args:
            data: Input data (file path, URL, base64, bytes, numpy array, file handle, etc.)
            allow_reads_from_disk: Enable file system access (disable in web environments)
            
        Returns:
            Self for method chaining
        """
        # Call parent method - it will route to appropriate leaf method that calls _file_info
        return super().from_any(data, allow_reads_from_disk)

    def from_bytesio_or_handle(
            self,
            buffer: Union[io.BytesIO, BinaryIO, io.BufferedReader],
            copy: bool = True
    ):
        """
        Load content from BytesIO or file handle with optional copying.
        Calls parent method and then performs file info extraction only if not copying.
        
        Args:
            buffer: Source buffer to read from
            copy: If True, reads entire buffer to bytes. If False, keeps reference (not thread-safe)
            
        Returns:
            Self for method chaining
        """
        # Set path for file info extraction before calling parent
        if isinstance(buffer, io.BufferedReader):
            self.path = buffer.name
            
        result = super().from_bytesio_or_handle(buffer, copy)
        # Only call _file_info if not copying (when copying, from_bytes will be called and handle it)
        if not copy:
            self._file_info()
        return result

    def from_file(self, path_or_handle: Union[str, io.BytesIO, io.BufferedReader]):
        """
        Load file from path or handle with automatic type detection.
        Stores path information before calling parent method.
        
        Args:
            path_or_handle: File path string or file handle
            
        Returns:
            Self for method chaining
        """
        # Store path information before calling parent
        if isinstance(path_or_handle, str):
            self.path = path_or_handle
            
        # Call parent method - it will route to appropriate method that calls _file_info
        return super().from_file(path_or_handle)

    def from_bytes(self, data: bytes):
        """Load content from raw bytes and extract file info."""
        result = super().from_bytes(data)
        self._file_info()
        return result

    def from_starlette_upload_file(self, starlette_upload_file):
        """
        Load from Starlette UploadFile with metadata extraction.
        Extracts metadata before calling parent method.
        
        Args:
            starlette_upload_file: Starlette UploadFile object
            
        Returns:
            Self for method chaining
        """
        # Extract metadata before calling parent
        self.file_name = starlette_upload_file.filename
        self.content_type = starlette_upload_file.content_type
        
        # Parent method calls from_bytes internally, which will call _file_info
        return super().from_starlette_upload_file(starlette_upload_file)

    def from_base64(self, base64_str: str):
        """
        Load from base64 encoded string (supports data URI format).
        Extracts media type from data URI if present.
        
        Args:
            base64_str: Base64 string, optionally with data URI prefix
            
        Returns:
            Self for method chaining
        """
        # Extract media type from data URI if present
        _, media_type = self._parse_base64_uri(base64_str)
        if media_type is not None:
            self.content_type = media_type
            
        # Parent method calls from_bytes internally, which will call _file_info
        return super().from_base64(base64_str)

    @requires_numpy()
    def from_np_array(self, np_array: np.array):
        """
        Load from numpy array using numpy's save format.
        Sets appropriate content type and calls parent method.
        
        Args:
            np_array: Numpy array to save
            
        Returns:
            Self for method chaining
        """
        result = super().from_np_array(np_array)
        self.content_type = 'file/npy'  # Set appropriate content type
        self._file_info()
        return result

    def from_dict(self, file_result_json: dict, allow_reads_from_disk: bool = True):
        """
        Load from FileModel dictionary format.
        Extracts metadata before calling parent method.
        
        Args:
            file_result_json: Dictionary with 'file_name', 'content_type', 'content' keys
            
        Returns:
            Self for method chaining
        """
        # Extract metadata before calling parent
        self.file_name = file_result_json["file_name"]
        self.content_type = file_result_json["content_type"]
        
        # Parent method calls from_any internally, which routes to appropriate method
        return super().from_dict(file_result_json, allow_reads_from_disk=allow_reads_from_disk)

    def save(self, path: str = None):
        """
        Save file to disk with automatic directory creation.
        
        Args:
            path: Target path (directory or full path)
        """
        # Add filename if path is directory
        if self.file_name is None:
            self.file_name = "media_file"
            print(f"No filename given. Using {self.file_name}")
        super().save(path)
        
    def _file_info(self):
        """
        Extract basic file metadata - filename from path/temp file.
        Content type detection is handled by subclasses or content detectors.
        Base implementation only handles filename extraction.
        """
        # cases when file_info is called. Documented for better understanding of the flow.
        # from_file -> retrieve info directly from the file path
        # from bytesio -> tempfile
        # from bytes -> tempfile
        # from buffered_reader -> set path -> from bytes -> get info from previously set file_path
        # from np_array -> tempfile
        # from starlette_upload_file -> from_buffered_reader(spooled_temporary) -> info from the spooled_temporary
        # from base64 -> from-bytes -> tempfile
        # from url -> from bytesio

        # Extract filename from path or temp file for metadata hints
        file_name_hint = self.file_name
        if self.path is not None:
            file_name_hint = os.path.basename(self.path)
        elif hasattr(self._content_buffer, "name") and self._content_buffer.name is not None:
            file_name_hint = os.path.basename(self._content_buffer.name)

        if file_name_hint is not None:
            self.file_name = file_name_hint

        # Determine content type using the centralized detector
        if not hasattr(self, 'content_type') or self.content_type is None:
            detection = ContentDetector.detect_from_universal_file(self, file_name=self.file_name)
            self.content_type = detection.content_type

        # Apply defaults if not set
        if self.file_name is None:
            self.file_name = "file"
        
        if self.content_type is None:
            self.content_type = "application/octet-stream"
        
    @property
    def extension(self) -> Optional[str]:
        """
        Get file extension from filename.

        Returns:
            File extension without dot, or None if undetermined
        """
        if self.content_type and "/" in self.content_type:
            return self.content_type.split("/")[-1].lower()

        if self.file_name and "." in self.file_name:
            return self.file_name.rsplit(".", 1)[-1].lower()

        return None

    @staticmethod
    def _is_valid_file_path(path: str):
        """Check if string is a valid file path."""
        return is_valid_file_path(path)

    @staticmethod
    def _is_url(url: str):
        """Check if string is a valid URL."""
        return is_url(url)

    @staticmethod
    def _is_starlette_upload_file(data):
        """Check if data is a Starlette UploadFile."""
        return is_starlette_upload_file(data)

    @staticmethod
    def _is_file_model(data: dict):
        """Check if dictionary matches FileModel format."""
        return is_file_model_dict(data)

    def to_httpx_send_able_tuple(self):
        """Get tuple format suitable for HTTP client libraries."""
        return self.file_name, self.read(), self.content_type

    def to_json(self):
        """
        Serialize to JSON-compatible dictionary.
        
        Returns:
            Dictionary with { "file_name": str, "content_type": str, "content": str }
        """
        return {
            "file_name": self.file_name,
            "content_type": self.content_type,
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
