from abc import ABC, abstractmethod
from typing import Optional, List, Generic, TypeVar
from media_toolkit.core.media_files.i_media_file import IMediaFile

# Define a type variable for media files
T = TypeVar("T", bound="IMediaFile")


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
    def get_leaf_files(self):
        """
        Get all media files from the container that are not IMediaContainers.
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
