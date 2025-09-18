from abc import ABC, abstractmethod
import io
from typing import Dict, Any, Optional, TypeVar
# Define a type variable for media files
T = TypeVar("T", bound="IMediaFile")


class IMediaFile(ABC):
    """
    Abstract base interface defining the core contract for media file handling
    in the Media Toolkit ecosystem.
    """
    @abstractmethod
    def from_any(self, data: Any, allow_reads_from_disk: bool = True) -> 'IMediaFile':
        """
        Load file content from various input sources.

        Args:
            data: Input source (bytes, file path, URL, base64, etc.)
            allow_reads_from_disk: Flag to control disk file reading

        Returns:
            Self, for method chaining
        """
        pass

    @abstractmethod
    def to_bytes(self) -> bytes:
        """Convert file content to raw bytes."""
        pass

    @abstractmethod
    def to_base64(self) -> str:
        """Encode file content to base64."""
        pass

    @abstractmethod
    def to_bytes_io(self) -> io.BytesIO:
        """Convert file content to BytesIO object."""
        pass

    @abstractmethod
    def to_httpx_send_able_tuple(self) -> tuple:
        """
        Prepare file for HTTP transmission.

        Returns:
            Tuple of (filename, content, content_type)
        """
        pass

    @abstractmethod
    def save(self, path: Optional[str] = None):
        """
        Save file to specified path.

        Args:
            path: Destination path. Uses current directory if None.
        """
        pass

    @abstractmethod
    def file_size(self, unit: str = "bytes") -> float:
        """
        Get file size in specified units.

        Args:
            unit: Size unit (bytes, kb, mb, gb)

        Returns:
            File size in specified unit
        """
        pass

    @abstractmethod
    def to_json(self) -> Dict[str, Any]:
        """
        Serialize file to JSON-compatible dictionary.

        Returns:
            Dictionary representation of the file
        """
        pass

    @abstractmethod
    def __sizeof__(self):
        """Get the size of the file in bytes."""
        pass
