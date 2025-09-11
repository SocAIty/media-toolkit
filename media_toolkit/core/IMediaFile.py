from abc import ABC, abstractmethod
import io
from typing import Dict, Any, Optional, List, Generic, TypeVar
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


class IMediaContainer(IMediaFile, Generic[T], ABC):
    """
    Abstract base interface defining the core contract for media container handling
    in the Media Toolkit ecosystem.
    """
    @abstractmethod
    def get_processable_files(self):
        """
        Get all processable files from the container.
        """
        pass

    @abstractmethod
    def get_url_files(self):
        """
        Get all non processed files that are URLs from the container.
        """
        pass
    
    @abstractmethod
    def get_file_path_files(self):
        """
        Get all non processed files that are file paths from the container.
        """
        pass

    @abstractmethod
    def get_non_file_params(self):
        """
        Get all non-file parameters from the container.
        """
        pass
    
    @abstractmethod
    def to_httpx_send_able_tuple(self) -> List[tuple]:
        """
        Convert the container to httpx format.
        """
        pass
    
    @abstractmethod
    def save(self, path: Optional[str] = None):
        """
        Save the container to specified path.
        """
        pass

    @abstractmethod
    def __len__(self):
        """
        Get the length of the container.
        """
        pass
    
    @abstractmethod
    def __iter__(self):
        """
        Iterate over the container.
        """
        pass
    
    @abstractmethod
    def __sizeof__(self):
        """
        Get the size of the container (including file sizes).
        """
        pass
