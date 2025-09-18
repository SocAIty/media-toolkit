import io
from typing import List, Union, Optional, Any, TypeVar, Generic
from media_toolkit.core.media_files import IMediaFile, MediaFile, media_from_any, media_from_FileModel
from media_toolkit.core.media_containers.i_media_container import IMediaContainer
import os

T = TypeVar('T', bound=IMediaFile)


class MediaList(IMediaContainer, Generic[T]):
    """
    A flexible media file list that handles multiple file types and sources with configurable loading behaviors.
    It will try to convert all values to a IMediaFile object.
    If it can't convert a value to media file it will be stored as is.
    
    Supports:
    - Multiple MediaFile types
    - Lazy loading configurations
    - Basic list operations
    - Batch media processing
    - Generic type restrictions (e.g. MediaList[AudioFile])
    """
    def __init__(
        self,
        files: Optional[List[Union[str, T]]] = None,
        download_files=True,
        read_system_files=True,
        file_name: str = "MediaList",
        use_temp_file: bool = False,
        temp_dir: str = None
    ):
        """
        Initialize MediaList with optional files and configuration.

        Args:
            files: List of files (URLs, paths, MediaFile instances)
            download_files: Flag if "files" provided as "Urls" are downloaded and converted to MediaFile
            read_system_files: Flag if "files" provided as "Paths" are read and converted to MediaFile
            file_name: Name of the file list
            use_temp_file: Flag to use temp file for file processing for newly added files
            temp_dir: Temp directory path for newly added files
        """
        self.file_name = file_name
        self.use_temp_file = use_temp_file
        self.temp_dir = temp_dir

        self.download_files = download_files
        self.read_system_files = read_system_files
        
        # Categorized storage for efficient access
        self._media_files: List[T] = []
        self._url_files: List[str] = []
        self._non_processable_files: List[Union[str, Any]] = []
        self._media_containers: List[IMediaContainer] = []

        if files:
            self.extend(files)

    @property
    def _all_items(self) -> List[Union[str, T]]:
        """Unified view of all files in original order."""
        return self._media_files + self._url_files + self._non_processable_files

    def _process_file(self, file: Union[str, T]) -> Union[str, T]:
        """
        Process a single file and automatically categorize it.
        
        Args:
            file: File to process (URL, path, MediaFile)
        Returns:
            Processed file (MediaFile or original str)
        """
        if isinstance(file, IMediaFile):
            self._media_files.append(file)
            if isinstance(file, IMediaContainer):
                self._media_containers.append(file)
            return file

        # check if is empty
        if file is None or (hasattr(file, '__len__') and len(file) < 1):
            self._non_processable_files.append(file)
            return file
                
        if isinstance(file, str):
            if MediaFile._is_url(file):
                if not self.download_files:
                    self._url_files.append(file)
                    return file
                try:
                    processed_file = media_from_any(file, allow_reads_from_disk=self.read_system_files)
                    self._media_files.append(processed_file)
                    return processed_file
                except Exception:
                    self._non_processable_files.append(file)
                    return file

            if MediaFile._is_valid_file_path(file):
                if not self.read_system_files:
                    self._non_processable_files.append(file)
                    return file
                try:
                    processed_file = media_from_any(file, allow_reads_from_disk=self.read_system_files)
                    self._media_files.append(processed_file)
                    return processed_file
                except Exception:
                    self._non_processable_files.append(file)
                    return file
            
        if MediaFile._is_file_model(file):
            try:
                processed_file = media_from_FileModel(file, allow_reads_from_disk=self.read_system_files)
                self._media_files.append(processed_file)
                return processed_file
            except Exception:
                self._non_processable_files.append(file)
                return file

        try:
            processed_file = media_from_any(file, use_temp_file=self.use_temp_file, temp_dir=self.temp_dir)
            self._media_files.append(processed_file)
            return processed_file
        except Exception:
            self._non_processable_files.append(file)
            return file

    def from_any(self, data: List[Union[str, T]], allow_reads_from_disk: bool = True) -> 'MediaList[T]':
        if data is None:
            return self
        
        if isinstance(data, list):
            for d in data:
                self._process_file(d)
        else:
            self._process_file(data)
        return self

    def get_leaf_files(self) -> Union[List[T], List[int]]:
        """
        Get all media files from the container that are not IMediaContainers and their indices.
        return:
        - List of media files or []
        - List of indices of the leaf files or None
        """
        indices = []
        files = []
        for i, file in enumerate(self._media_files):
            if file not in self._media_containers:
                files.append(file)
                indices.append(i)

        return files, indices

    def get_media_containers(self) -> Union[List[IMediaContainer[T]], List[int]]:
        """
        Get all media containers from the container and their indices.

        """
        indices = []
        containers = []
        for container in self._media_containers:
            containers.append(container)
            indices.append(self._media_files.index(container))

        return containers, indices

    def get_processable_files(
        self,
        ignore_all_potential_errors: bool = False,
        raise_exception: bool = True,
        silent: bool = False
    ) -> 'MediaList[T]':
        """
        Validate that all files can be processed for batch operations. This depends on configuration.
        
        Args:
            ignore_all_potential_errors: Ignore processing errors
            raise_exception: if set false, function will return only processable files and ignore the rest
            silent: Suppress error messages
        Returns:
            List of processable files
        """
        if ignore_all_potential_errors:
            return self._media_files.copy()
        
        processable_files = []
        # Add non-container media files
        for file in self._media_files:
            if file not in self._media_containers:
                processable_files.append(file)
        
        # Process containers separately
        for container in self._media_containers:
            nested_files = container.get_processable_files(raise_exception=False, silent=True)
            if len(nested_files) > 0:
                processable_files.extend(nested_files)

        non_processable_count = len(self._url_files) + len(self._non_processable_files)
        if non_processable_count > 0 and (raise_exception or not silent):
            not_processable_files = self._url_files + self._non_processable_files
            message = f"Files not processed: {not_processable_files}. " \
                      f"Check configuration (download_files={self.download_files}, " \
                      f"read_system_files={self.read_system_files})"
            if raise_exception:
                raise ValueError(message)
            if not silent:
                print(message)

        return MediaList[T](
            files=processable_files,
            download_files=self.download_files,
            read_system_files=self.read_system_files,
            use_temp_file=self.use_temp_file,
            temp_dir=self.temp_dir
        )

    def get_url_files(self) -> List[str]:
        """Get all non processed files that are URLs from the list."""
        return self._url_files.copy()

    def get_file_path_files(self) -> List[str]:
        """Get all non processed files that are file paths from the list."""
        return [
            file for file in self._non_processable_files
            if isinstance(file, str) and MediaFile._is_valid_file_path(file)
        ]

    def get_non_file_params(self, include_urls: bool = True) -> List[Union[str, Any]]:
        """
        Get all non-processed files.
        If include_urls is True, it will include URLs that are not processed.

        Args:
            include_urls: Whether to include URL files in the result
        Returns:
            List of non-processable files and optionally URLs
        """
        non_file_params = self._non_processable_files.copy()
        if include_urls:
            non_file_params.extend(self._url_files)

        # Process containers
        for container in self._media_containers:
            nested_files = container.get_non_file_params(include_urls)
            if len(nested_files) > 0:
                non_file_params.extend(nested_files)
      
        return non_file_params

    def to_base64(self) -> List[str]:
        """Convert all files to base64."""
        return [file.to_base64() for file in self._media_files]

    def to_bytes_io(self) -> List[io.BytesIO]:
        return [file.to_bytes_io() for file in self._media_files]

    def file_size(self, unit: str = "bytes") -> float:
        return sum([file.file_size(unit) for file in self._media_files])

    def to_json(self) -> List[Union[MediaFile, str, Any]]:
        """Convert files to JSON representation."""
        result = []
        # Add processed media files
        result.extend([file.to_json() for file in self._media_files])
        # Add non-processed files as-is
        result.extend(self._url_files)
        result.extend(self._non_processable_files)
        return result

    def to_bytes(self) -> List[bytes]:
        return [file.to_bytes() for file in self._media_files]

    def to_httpx_send_able_tuple(self, param_name: str = None) -> List[tuple]:
        """
        Convert files to httpx-send-able format.
        
        Args:
            param_name: Set this value if you try to send a list of files to an API endpoint as a single parameter
                       This will result in a List of (param_name, (filename, content, content_type)) tuples
                       If none: List of (filename, content, content_type) tuples
        Returns:
            List of (filename, content, content_type) tuples or (param_name, (filename, content, content_type)) tuples
        """
        tuples = []
        # Process media files
        for file in self._media_files:
            file_tuple = file.to_httpx_send_able_tuple()
            if param_name:
                tuples.append((param_name, file_tuple))
            else:
                tuples.append(file_tuple)

        return tuples

    def save(self, directory: Optional[str] = None):
        """
        Save all files to a specified directory.

        Args:
            directory: Target directory. Uses current directory if None.
        """
        directory = directory or os.path.curdir
        os.makedirs(directory, exist_ok=True)

        for file in self._media_files:
            file.save(os.path.join(directory, file.file_name))

    def append(self, file: Union[str, T]):
        """Append a single file to the list."""
        self._process_file(file)

    def extend(self, files: List[Union[str, T]]):
        """Extend the list with multiple files."""
        for file in files:
            self._process_file(file)

    def pop(self, index: int = -1) -> Union[str, T]:
        """Remove and return the file at the specified index."""
        all_files = self._all_items
        if index < 0:
            index = len(all_files) + index
            
        if index < 0 or index >= len(all_files):
            raise IndexError("list index out of range")
            
        file_to_remove = all_files[index]
        
        # Remove from appropriate category list
        if file_to_remove in self._media_files:
            self._media_files.remove(file_to_remove)
            if file_to_remove in self._media_containers:
                self._media_containers.remove(file_to_remove)
        elif file_to_remove in self._url_files:
            self._url_files.remove(file_to_remove)
        elif file_to_remove in self._non_processable_files:
            self._non_processable_files.remove(file_to_remove)
            
        return file_to_remove

    def __iter__(self):
        """Make the class iterable."""
        return iter(self._all_items)

    def __len__(self):
        """Return the number of files in the list."""
        return len(self._media_files) + len(self._url_files) + len(self._non_processable_files)

    def __getitem__(self, index):
        """Allow indexing."""
        return self._all_items[index]

    def __sizeof__(self):
        """Returns the memory size of the instance + actual file/buffer size."""
        size = super().__sizeof__() + self.file_size("bytes")
        return size

    def to_list(self) -> List[Union[str, T]]:
        """Convert MediaList to a list of files."""
        return self._all_items
