import io
from typing import List, Union, Optional, Any
from media_toolkit.core.media_file import MediaFile
from media_toolkit.core.IMediaFile import IMediaFile
import os


class MediaList(IMediaFile):
    """
    A flexible media file list that handles multiple file types and sources with configurable loading behaviors.

    Supports:
    - Multiple MediaFile types
    - Lazy loading configurations
    - Basic list operations
    - Batch media processing
    """
    def __init__(
        self,
        files: Optional[List[Union[str, MediaFile]]] = None,
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
        self.media_files: List[Union[str, MediaFile]] = []

        if files:
            self.extend(files)

    def _process_file(self, file: Union[str, MediaFile]) -> Union[str, MediaFile]:
        """
        Process a single file based on configuration.
        Args:
            file: File to process (URL, path, MediaFile)
        Returns:
            Processed file (MediaFile or original str)
        Raises:
            ValueError for configuration-blocked file processing
        """
        if isinstance(file, MediaFile):
            return file

        if MediaFile._is_url(file):
            if not self.download_files:
                return file
            return MediaFile(use_temp_file=self.use_temp_file, temp_dir=self.temp_dir).from_url(file)

        if MediaFile._is_valid_file_path(file):
            if not self.read_system_files:
                return file
            return MediaFile(use_temp_file=self.use_temp_file, temp_dir=self.temp_dir).from_file(file)

        return MediaFile(use_temp_file=self.use_temp_file, temp_dir=self.temp_dir).from_any(file)

    def from_any(self, data: List[Union[str, MediaFile]], allow_reads_from_disk: bool = True) -> 'MediaList':
        if isinstance(data, list):
            self.extend([self._process_file(d) for d in data])
        elif isinstance(data, MediaFile):
            self.media_files.append(self._process_file(data))
        return self

    def get_processable_files(
        self,
        ignore_all_potential_errors: bool = False,
        raise_exception: bool = True,
        silent: bool = False
    ) -> List[MediaFile]:
        """
        Validate that all files can be processed for batch operations. This depends on configuration.
        :param raise_exception: if set false, function will return only processable files and ignore the rest
        Raises:
            ValueError if any file cannot be processed due to configuration.
        """
        if ignore_all_potential_errors:
            return self.media_files

        processable_files = [
            f for f in self.media_files
            if isinstance(f, MediaFile)
        ]

        if len(processable_files) != len(self.media_files):
            not_processable_file_names = [str(f) for f in self.media_files if f not in processable_files]
            message = f"Files not processed: {not_processable_file_names}. " \
                        f"Check configuration (download_files={self.download_files}, " \
                        f"read_system_files={self.read_system_files})"
            if raise_exception:
                raise ValueError(message)
            if not silent:
                print(message)

        return processable_files

    def get_url_files(self) -> List[str]:
        """Get all non processed files that are URLs from the list."""
        if self.download_files:
            return []
        return [file for file in self.media_files if isinstance(file, str) and MediaFile._is_url(file)]

    def get_file_path_files(self) -> List[str]:
        """Get all non processed files that are file paths from the list."""
        if self.read_system_files:
            return []
        return [file for file in self.media_files if isinstance(file, str) and MediaFile._is_valid_file_path(file)]

    def to_base64(self) -> List[str]:
        """Convert all files to base64."""
        return [file.to_base64() for file in self.get_processable_files(raise_exception=False)]

    def to_bytes_io(self) -> List[io.BytesIO]:
        return [file.to_bytes_io() for file in self.get_processable_files(raise_exception=False)]

    def file_size(self, unit: str = "bytes") -> float:
        return sum([file.file_size(unit) for file in self.get_processable_files(raise_exception=False)])

    def to_json(self) -> List[Union[MediaFile, str, Any]]:
        files = self.get_processable_files(ignore_all_potential_errors=True)
        return [
            file.to_json() if isinstance(file, MediaFile) else file
            for file in files
        ]

    def to_bytes(self) -> List[bytes]:
        return [file.to_bytes() for file in self.get_processable_files(raise_exception=False)]

    def to_httpx_send_able_tuple(self, param_name: str = None) -> List[tuple]:
        """
        Convert files to httpx-send-able format.
        :param param_name:
            Set this value if you try to send a list of files to an API endpoint as a single parameter
            This will result in a List of (param_name, (filename, content, content_type)) tuples
            If none: List of (filename, content, content_type) tuples
        Returns:
            List of (filename, content, content_type) tuples or (param_name, (filename, content, content_type)) tuples
        """
        files = self.get_processable_files(raise_exception=False, silent=True)
        if param_name:
            return [(param_name, file.to_httpx_send_able_tuple()) for file in files]

        return [file.to_httpx_send_able_tuple() for file in self.media_files]

    def save(self, directory: Optional[str] = None):
        """
        Save all files to a specified directory.

        Args:
            directory: Target directory. Uses current directory if None.
        """
        directory = directory or os.path.curdir
        os.makedirs(directory, exist_ok=True)

        for file in self.get_processable_files(raise_exception=False):
            file.save(os.path.join(directory, file.file_name))

    def append(self, file: Union[str, MediaFile]):
        """Append a single file to the list."""
        processed_file = self._process_file(file)
        self.media_files.append(processed_file)

    def extend(self, files: List[Union[str, MediaFile]]):
        """Extend the list with multiple files."""
        for file in files:
            self.append(self._process_file(file))

    def pop(self, index: int = -1) -> Union[str, MediaFile]:
        """Remove and return the file at the specified index."""
        return self.media_files.pop(index)

    def __iter__(self):
        """Make the class iterable."""
        return iter(self.media_files)

    def __len__(self):
        """Return the number of files in the list."""
        return len(self.media_files)

    def __getitem__(self, index):
        """Allow indexing."""
        return self.media_files[index]

    def __sizeof__(self):
        """Returns the memory size of the instance + actual file/buffer size."""
        size = super().__sizeof__() + self.file_size("bytes")
        return size

    def to_list(self) -> List[Union[str, MediaFile]]:
        """Convert MediaList to a list of files."""
        return self.media_files
