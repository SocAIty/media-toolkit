import io
import uuid
from typing import List, Union, Optional, Any, Dict, TypeVar, Generic
from media_toolkit.core.IMediaFile import IMediaFile
from media_toolkit.core.media_file import MediaFile
from media_toolkit.core.MediaList import MediaList

T = TypeVar('T', bound=IMediaFile)


class MediaDict(IMediaFile, Generic[T]):
    """
    A flexible media file dictionary that handles multiple file types
    and sources with configurable loading behaviors.

    Supports:
    - Multiple MediaFile types as dictionary values
    - Batch media processing
    - Generic type restrictions (e.g. MediaDict[AudioFile])
    """
    def __init__(
            self,
            files: Optional[Dict[str, Union[str, T, MediaList[T], 'MediaDict[T]']]] = None,
            download_files: bool = True,
            read_system_files: bool = True,
            file_name: str = "MediaDict",
            use_temp_file: bool = False,
            temp_dir: str = None
    ):
        """
        Initialize MediaDict with optional files and configuration.

        Args:
            files: Dictionary of files with keys as identifiers
            download_files: Flag if files provided as URLs are downloaded and converted
            read_system_files: Flag if files provided as paths are read and converted
            file_name: Name of the media dictionary
            use_temp_file: Flag to use temp file for file processing
            temp_dir: Temp directory path for file processing
        """
        self.file_name = file_name
        self.use_temp_file = use_temp_file
        self.temp_dir = temp_dir
        self.download_files = download_files
        self.read_system_files = read_system_files
        self._media_files: Dict[str, Union[str, T, MediaList[T]]] = {}

        if files:
            self.update(files)

    @staticmethod
    def _is_empty_file(file: Any) -> bool:
        """ Check if file has any content. """
        if isinstance(file, list) and all(MediaDict._is_empty_file(item) for item in file):
            return True
        return file is None or (hasattr(file, '__len__') and len(file) == 0)
            
    def _process_file(
            self,
            file: Union[str, T, MediaList[T], 'MediaDict[T]']
    ) -> Union[str, T, MediaList[T], 'MediaDict[T]']:
        """
        Process a single file based on configuration.

        Args:
            file: File to process (URL, path, MediaFile, MediaList)
        Returns:
            Processed file (MediaFile, MediaList, or original str)
        """
        if isinstance(file, (IMediaFile, MediaList, MediaDict)):
            return file

        # check if is empty
        if MediaDict._is_empty_file(file):
            return file

        # perform conversion
        if isinstance(file, str):
            if MediaFile._is_url(file):
                if not self.download_files:
                    return file
                return MediaFile(use_temp_file=self.use_temp_file, temp_dir=self.temp_dir).from_url(file)

            if MediaFile._is_valid_file_path(file):
                if not self.read_system_files:
                    return file
                return MediaFile(use_temp_file=self.use_temp_file, temp_dir=self.temp_dir).from_file(file)

        if MediaFile._is_file_model(file):
            from media_toolkit.utils import media_from_FileModel
            return media_from_FileModel(file, allow_reads_from_disk=self.read_system_files)

        if isinstance(file, list):
            return MediaList[T](
                files=file,
                download_files=self.download_files,
                read_system_files=self.read_system_files,
                use_temp_file=self.use_temp_file,
                temp_dir=self.temp_dir
            )

        if isinstance(file, dict):
            return MediaDict[T](
                files=file,
                download_files=self.download_files,
                read_system_files=self.read_system_files,
                use_temp_file=self.use_temp_file,
                temp_dir=self.temp_dir
            )

        return MediaFile(use_temp_file=self.use_temp_file, temp_dir=self.temp_dir).from_any(file)

    def from_any(
            self,
            data: Union[Dict[str, Union[str, T, MediaList[T]]], Any]
    ) -> 'MediaDict[T]':
        """
        Load files from a dictionary of files.

        Args:
            data: Dictionary of files to load
        Returns:
            Self, for method chaining
        """
        self.update(data)
        return self

    def get_processable_files(
            self,
            ignore_all_potential_errors: bool = False,
            raise_exception: bool = True,
            silent: bool = False
    ) -> 'MediaDict[T]':
        """
        Validate that all files can be processed for batch operations.

        Args:
            ignore_all_potential_errors: Ignore processing errors
            raise_exception: Raise exceptions for unprocessable files
            silent: Suppress error messages
        Returns:
            Dictionary of processable files
        """
        if ignore_all_potential_errors:
            return self

        processable_files = {
            key: file for key, file in self._media_files.items()
            if isinstance(file, (IMediaFile, MediaList))
        }

        if len(processable_files) != len(self._media_files):
            not_processable_file_names = [
                str(key) for key, file in self._media_files.items()
                if file not in processable_files.values()
            ]
            message = (
                f"Files not processed: {not_processable_file_names}. "
                f"Check configuration (download_files={self.download_files}, "
                f"read_system_files={self.read_system_files})"
            )

            if raise_exception:
                raise ValueError(message)
            if not silent:
                print(message)

            return self._shallow_copy_with_settings(processable_files)

        return self

    def _shallow_copy_with_settings(self, data: dict | None = None) -> 'MediaDict[T]':
        """
        Creates a new MediaDict with the same settings but shallow copies the media files dictionary.
        This avoids re-reading all files when creating a copy.
        """
        md = MediaDict[T](
            file_name=self.file_name, download_files=self.download_files,
            read_system_files=self.read_system_files, use_temp_file=self.use_temp_file, temp_dir=self.temp_dir
        )
        md._media_files = data
        return md

    def get_url_files(self) -> Union['MediaDict[T]', dict]:
        """
        Get all non-processed files that are URLs.

        Returns:
            Dictionary of URL files
        """
        if self.download_files:
            return {}

        return self._shallow_copy_with_settings({
            key: file for key, file in self._media_files.items()
            if isinstance(file, str) and MediaFile._is_url(file)
        })

    def get_file_path_files(self) -> Union['MediaDict[T]', dict]:
        """
        Get all non-processed files that are file paths.

        Returns:
            Dictionary of file path files
        """
        if self.read_system_files:
            return {}
        return self._shallow_copy_with_settings({
            key: file for key, file in self._media_files.items()
            if isinstance(file, str) and MediaFile._is_valid_file_path(file)
        })

    def to_base64(self) -> Dict[str, str]:
        """Convert all processable files to base64."""
        return {
            key: file.to_base64()
            for key, file in self.get_processable_files(raise_exception=False).items()
        }

    def to_bytes_io(self) -> Dict[str, io.BytesIO]:
        """Convert all processable files to BytesIO."""
        return {
            key: file.to_bytes_io()
            for key, file in self.get_processable_files(raise_exception=False).items()
        }

    def file_size(self, unit: str = "bytes") -> float:
        """Calculate total file size."""
        return sum(
            file.file_size(unit)
            for file in self.get_processable_files(raise_exception=False).values()
        )

    def to_json(self) -> Dict[str, Any]:
        """Convert files to JSON representation."""
        files = self.get_processable_files(ignore_all_potential_errors=True)
        return {
            key: (file.to_json() if isinstance(file, (IMediaFile, MediaList)) else file)
            for key, file in files.items()
        }

    def to_bytes(self) -> Dict[str, bytes]:
        """Convert all processable files to bytes."""
        return {
            key: file.to_bytes()
            for key, file in self.get_processable_files(raise_exception=False).items()
        }

    def to_httpx_send_able_tuple(self) -> List[tuple] | dict:
        """
        Convert files to httpx-send-able format.

        Args:
            param_name: Optional parameter name for API endpoint
        Returns:
            List of tuples  for httpx file transmission
        """
        files = self.get_processable_files(raise_exception=False, silent=True)

        ret = []
        for k, file in files.items():
            if isinstance(file, MediaList):
                ret.extend(file.to_httpx_sendable_tuple(k))
            elif isinstance(file, MediaDict):
                fls = file.to_httpx_sendable_tuple()
                if isinstance(fls, dict):
                    ret.append((k, fls))
                else:
                    ret.extend(fls)
            else:
                ret.append((k, file.to_httpx_send_able_tuple()))

        if len(ret) == 1:
            return {ret[0][0]: ret[0][1]}
        return ret

    def save(self, directory: Optional[str] = None):
        """
        Save all processable files to a specified directory.

        Args:
            directory: Target directory (uses current directory if None)
        """
        import os
        directory = directory or os.path.curdir
        os.makedirs(directory, exist_ok=True)

        for key, file in self.get_processable_files(raise_exception=False).items():
            file.save(directory)

    def __getitem__(self, key: str):
        """Allow dictionary-style access."""
        return self._media_files[key]

    def __setitem__(self, key: str, value: Union[str, T, MediaList[T]]):
        """Allow dictionary-style assignment with processing."""
        self._media_files[key] = self._process_file(value)

    def __delitem__(self, key: str):
        """Allow dictionary-style deletion."""
        del self._media_files[key]

    def __iter__(self):
        """Make the class iterable."""
        return iter(self._media_files)

    def __len__(self):
        """Return the number of files in the dictionary."""
        return len(self._media_files)

    def __contains__(self, key: str):
        """Check if a key exists in the dictionary."""
        return key in self._media_files

    def keys(self):
        """Return dictionary keys."""
        return self._media_files.keys()

    def values(self):
        """Return dictionary values."""
        return self._media_files.values()

    def items(self):
        """Return dictionary items."""
        return self._media_files.items()

    def update(self, files: Union['MediaDict[T]', Dict[str, Union[str, T, MediaList[T]]]]):
        """
        Update the dictionary with new files.

        Args:
            files: Dictionary of files to add or update
        """
        if files is None:
            return

        if not isinstance(files, dict) and not isinstance(files, MediaDict):
            files = {str(uuid.uuid4()): files}

        for key, file in files.items():
            self[key] = self._process_file(file)

    def __sizeof__(self):
        """Returns the memory size of the instance + actual file/buffer size."""
        size = super().__sizeof__() + self.file_size("bytes")
        return size

    def to_dict(self) -> Dict[str, Union[str, T, MediaList[T]]]:
        """Convert MediaDict to a standard dictionary."""
        return {
            key: (file.to_dict() if isinstance(file, MediaDict) else file)
            for key, file in self._media_files.items()
        }
