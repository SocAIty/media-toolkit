import io
import uuid
from typing import List, Union, Optional, Any, Dict, TypeVar, Generic
from media_toolkit.core.IMediaFile import IMediaFile, IMediaContainer
from media_toolkit.core.media_file import MediaFile
from media_toolkit.core.MediaList import MediaList
from media_toolkit.core.file_conversion import media_from_any, media_from_FileModel
from media_toolkit.utils.data_type_utils import is_file_model_dict, is_url

T = TypeVar('T', bound=IMediaFile)


class MediaDict(IMediaContainer, Generic[T]):
    """
    A flexible media file dictionary that handles multiple file types
    and sources with configurable loading behaviors.
    It will try to convert all values to a IMediaFile object.
    If it can't convert a value to media file it will be stored as is.

    Supports:
    - Multiple MediaFile types as dictionary values
    - Batch media processing
    - Generic type restrictions (e.g. MediaDict[AudioFile])
    """
    def __init__(
            self,
            files: Optional[Dict[str, Union[str, T, IMediaContainer[T]]]] = None,
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
        self._all_items: Dict[str, Union[str, T, MediaList[T]]] = {}
        
        # Category sets for efficient file type lookup
        self._url_files: set[str] = set()
        self._non_processable_files: set[str] = set()
        # note that media_files and media_containers are not distinct sets.
        # Media files can be containers themselves.
        self._media_files: set[str] = set()
        self._media_containers: set[str] = set()

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
            key: str,
            file: Union[str, T, IMediaContainer[T]]
    ) -> Union[str, T, MediaList[T], 'MediaDict[T]']:
        """
        Process a single file and automatically categorize it.

        Args:
            key: The key for this file in the dictionary
            file: File to process (URL, path, MediaFile, MediaList)
        Returns:
            Processed file (MediaFile, MediaList, or original str)
        """
        # Remove from all sets first to avoid duplicates
        self._remove_from_all_sets(key)
        
        if isinstance(file, (IMediaFile, IMediaContainer)):
            self._media_files.add(key)
            if isinstance(file, IMediaContainer):
                self._media_containers.add(key)
            return file

        # check if is empty
        if MediaDict._is_empty_file(file):
            self._non_processable_files.add(key)
            return file

        # perform conversion
        if isinstance(file, str):
            if is_url(file):
                if not self.download_files:
                    self._url_files.add(key)
                    return file
                try:
                    processed_file = media_from_any(file, allow_reads_from_disk=self.read_system_files)
                    self._media_files.add(key)
                    return processed_file
                except Exception:
                    self._non_processable_files.add(key)
                    return file

        if is_file_model_dict(file):
            try:
                processed_file = media_from_FileModel(file, allow_reads_from_disk=self.read_system_files)
                self._media_files.add(key)
                return processed_file
            except Exception:
                self._non_processable_files.add(key)
                return file

        if isinstance(file, list):
            media_list = MediaList[T](
                files=file,
                download_files=self.download_files,
                read_system_files=self.read_system_files,
                use_temp_file=self.use_temp_file,
                temp_dir=self.temp_dir
            )
            self._media_files.add(key)
            self._media_containers.add(key)
            return media_list

        if isinstance(file, dict):
            media_dict = MediaDict[T](
                files=file,
                download_files=self.download_files,
                read_system_files=self.read_system_files,
                use_temp_file=self.use_temp_file,
                temp_dir=self.temp_dir
            )
            self._media_files.add(key)
            self._media_containers.add(key)
            return media_dict

        try:
            processed_file = media_from_any(file, use_temp_file=self.use_temp_file, temp_dir=self.temp_dir)
            self._media_files.add(key)
            return processed_file
        except Exception:
            self._non_processable_files.add(key)
            return file

    def _remove_from_all_sets(self, key: str):
        """Remove key from all category sets."""
        self._media_files.discard(key)
        self._url_files.discard(key)
        self._non_processable_files.discard(key)
        self._media_containers.discard(key)

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

        # Use the media_files set for efficient lookup
        # In case of nested containers we need to get the processable files from the nested container
        processable_files = {}
        # Add non-container media files
        for key in self._media_files - self._media_containers:
            processable_files[key] = self._all_items[key]
        
        # Process containers separately
        for key in self._media_containers:
            nested_files = self._all_items[key].get_processable_files(raise_exception=False, silent=True)
            if len(nested_files) > 0:
                processable_files[key] = nested_files

        non_processable_count = len(self._non_processable_files) + len(self._url_files)
        if non_processable_count > 0 and (raise_exception or not silent):
            not_processable_file_names = list(self._non_processable_files | self._url_files)
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

    def get_non_file_params(self, include_urls: bool = True) -> dict:
        """
        Get all non-processed files.
        If include_urls is True, it will include URLs that are not processed.
        
        Args:
            include_urls: Whether to include URL files in the result
        Returns:
            Dictionary of non-processable files and optionally URLs
        """
        non_file_keys = self._non_processable_files.copy()
        if include_urls:
            non_file_keys.update(self._url_files)

        non_file_params = {key: self._all_items[key] for key in non_file_keys}
 
        # Process containers separately
        for key in self._media_containers:
            nested_files = self._all_items[key].get_non_file_params(include_urls)
            if len(nested_files) > 0:
                non_file_params[key] = nested_files
        
        return non_file_params

    def _shallow_copy_with_settings(self, data: dict | None = None) -> 'MediaDict[T]':
        """
        Creates a new MediaDict with the same settings but shallow copies the media files dictionary.
        This avoids re-reading all files when creating a copy.
        """
        md = MediaDict[T](
            file_name=self.file_name, download_files=self.download_files,
            read_system_files=self.read_system_files, use_temp_file=self.use_temp_file, temp_dir=self.temp_dir
        )
        if data is None:
            return md
        
        data_keys = data.keys()

        md._all_items = data.copy()
        md._media_files = self._media_files.intersection(data_keys)
        md._url_files = self._url_files.intersection(data_keys)
        md._non_processable_files = self._non_processable_files.intersection(data_keys)
        md._media_containers = self._media_containers.intersection(data_keys)

        return md

    def get_url_files(self) -> Union['MediaDict[T]', dict]:
        """
        Get all non-processed files that are URLs.

        Returns:
            Dictionary of URL files
        """
        if self.download_files:
            return {}

        url_files = {key: self._all_items[key] for key in self._url_files}
        return self._shallow_copy_with_settings(url_files)

    def get_file_path_files(self) -> Union['MediaDict[T]', dict]:
        """
        Get all non-processed files that are file paths.

        Returns:
            Dictionary of file path files
        """
        if self.read_system_files:
            return {}
            
        # Get non-processable files that are valid file paths
        path_files = {
            key: self._all_items[key] for key in self._non_processable_files
            if isinstance(self._all_items[key], str) and MediaFile._is_valid_file_path(self._all_items[key])
        }
        return self._shallow_copy_with_settings(path_files)

    def to_base64(self) -> Dict[str, str]:
        """Convert all processable files to base64."""
        return {
            key: self._all_items[key].to_base64()
            for key in self._media_files
        }

    def to_bytes_io(self) -> Dict[str, io.BytesIO]:
        """Convert all processable files to BytesIO."""
        return {
            key: self._all_items[key].to_bytes_io()
            for key in self._media_files
        }

    def file_size(self, unit: str = "bytes") -> float:
        """Calculate total file size."""
        return sum(
            self._all_items[key].file_size(unit)
            for key in self._media_files
        )

    def to_json(self) -> Dict[str, Any]:
        """Convert files to JSON representation."""
        return {
            key: (self._all_items[key].to_json() if key in self._media_files else self._all_items[key])
            for key in self._all_items
        }

    def to_bytes(self) -> Dict[str, bytes]:
        """Convert all processable files to bytes."""
        return {
            key: self._all_items[key].to_bytes()
            for key in self._media_files
        }

    def to_httpx_send_able_tuple(self) -> List[tuple] | dict:
        """
        Convert files to httpx-send-able format.

        Returns:
            List of tuples for httpx file transmission
        """
        ret = []
        # Process non-container media files
        for key in self._media_files - self._media_containers:
            file = self._all_items[key]
            ret.append((key, file.to_httpx_send_able_tuple()))
        
        # Process containers separately
        for key in self._media_containers:
            file = self._all_items[key]
            if isinstance(file, MediaList):
                ret.extend(file.to_httpx_send_able_tuple(key))
            elif isinstance(file, MediaDict):
                fls = file.to_httpx_send_able_tuple()
                if isinstance(fls, dict):
                    ret.append((key, fls))
                else:
                    ret.extend(fls)
            else:
                ret.append((key, file.to_httpx_send_able_tuple()))

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

        for key in self._media_files:
            self._all_items[key].save(directory)

    def __getitem__(self, key: str):
        """Allow dictionary-style access."""
        return self._all_items[key]

    def __setitem__(self, key: str, value: Union[str, T, MediaList[T]]):
        """Allow dictionary-style assignment with processing."""
        self._all_items[key] = self._process_file(key, value)

    def __delitem__(self, key: str):
        """Allow dictionary-style deletion."""
        del self._all_items[key]
        self._remove_from_all_sets(key)

    def __iter__(self):
        """Make the class iterable."""
        return iter(self._all_items)

    def __len__(self):
        """Return the number of files in the dictionary."""
        return len(self._all_items)

    def __contains__(self, key: str):
        """Check if a key exists in the dictionary."""
        return key in self._all_items

    def keys(self):
        """Return dictionary keys."""
        return self._all_items.keys()

    def values(self):
        """Return dictionary values."""
        return self._all_items.values()

    def items(self):
        """Return dictionary items."""
        return self._all_items.items()

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
            self._all_items[key] = self._process_file(key, file)

    def __sizeof__(self):
        """Returns the memory size of the instance + actual file/buffer size."""
        size = super().__sizeof__() + self.file_size("bytes")
        return size

    def to_dict(self) -> Dict[str, Union[str, T, MediaList[T]]]:
        """Convert MediaDict to a standard dictionary."""
        return {
            key: (file.to_dict() if isinstance(file, MediaDict) else file)
            for key, file in self._all_items.items()
        }
