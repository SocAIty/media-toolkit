import base64
import io
import mimetypes

from typing import Union, BinaryIO, Tuple, Optional
import os
from urllib.parse import urlparse

from media_toolkit.core.IMediaFile import IMediaFile
from media_toolkit.core.file_content_buffer import FileContentBuffer
from media_toolkit.utils.dependency_requirements import requires_numpy
from media_toolkit.utils import download_file

import re


try:
    import numpy as np
except ImportError:
    pass


class MediaFile(IMediaFile):
    """
    Has file conversions that make it easy to work standardized with files across the web and in the sdk.
    Works natively with bytesio, base64 and binary data.
    """
    def __init__(
            self,
            file_name: str = "file",
            content_type: str = "application/octet-stream",
            use_temp_file: bool = False,
            temp_dir: str = None
    ):
        """
        :param file_name: The name of the file. Note it is overwritten if you use from_file/from_starlette.
        :param content_type: The content type of the file. Note it is overwritten if you use from_file/from_starlette.
        :param use_temp_file: If True, the file is saved to a temporary file. This is useful for large files.
        :param max_file_size: The maximum file size in bytes. If the file is larger lib will throw an error.
        :param temp_dir: The directory where the temporary file is saved. If None, the system temp dir is used.
        """
        self.content_type = content_type
        self.file_name = file_name  # the name of the file also when specified in bytesio
        self.path = None  # the path of the file if it was provided. Is also indicator if file was loaded from file.

        self._content_buffer = FileContentBuffer(use_temp_file=use_temp_file, temp_dir=temp_dir)

    def from_any(self, data, allow_reads_from_disk: bool = True):
        """
        Load a file from any supported data type.
        
        :param data: The data to load from. Can be a file path, url, base64 string, bytes, numpy array, file handle...
        :param allow_reads_from_disk:
            If True, the method will try to read from disk if the data is a file path. (Risky in web environments)
            If False, the method will not read from disk and only load the file path as a string.
        """
        if data is None:
            return None

        # it is already converted
        if isinstance(data, MediaFile):
            return data

        # conversion factory
        if type(data) in [io.BufferedReader, io.BytesIO]:
            self.from_bytesio_or_handle(data)
        elif isinstance(data, str):
            if self._is_valid_file_path(data):
                if not allow_reads_from_disk:
                    print(f"Reads from disk disabled. Skipping file {data}")
                else:
                    self.from_file(data)
            elif self._is_url(data):
                self.from_url(data)
            else:
                try:
                    self.from_base64(data)
                except Exception as e:
                    print(f"Either wrong file path or not base64. Check your inputs: {data}. Error: {e}")
        elif isinstance(data, bytes):
            self.from_bytes(data)
        elif type(data).__name__ == 'ndarray':
            self.from_np_array(data)
        elif self._is_starlette_upload_file(data):
            self.from_starlette_upload_file(data)

        return self

    def from_bytesio_or_handle(
            self,
            buffer: Union[io.BytesIO, BinaryIO, io.BufferedReader],
            copy: bool = True
    ):
        """
        Set the content of the file from a BytesIO or a file handle.
        :params buffer: The buffer to read from.
        :params copy: If true, the buffer is completely read to bytes and the bytes copied to this file.
            If false file works with the provided buffer. Danger -- The buffer is kept open (not thread safe).
        """
        if not type(buffer) in [io.BytesIO, io.BufferedReader]:
            raise ValueError(f"Buffer must be of type BytesIO or BufferedReader. Got {type(buffer)}")

        self._reset_buffer()
        buffer.seek(0)

        # setting path is needed in order that file_info can work properly
        if type(buffer) in [io.BufferedReader]:
            self.path = buffer.name

        if not copy:
            self._content_buffer.overwrite_buffer(buffer)
            self._file_info()
        else:
            self.from_bytes(buffer.read())  # calls self._file_info also
            buffer.seek(0)

        return self

    def from_bytesio(self, buffer: Union[io.BytesIO, BinaryIO], copy: bool = True):
        return self.from_bytesio_or_handle(buffer=buffer, copy=copy)

    def from_file(self, path_or_handle: Union[str, io.BytesIO, io.BufferedReader]):
        """
        Load a file from a file path, file handle or base64 and convert it to BytesIO.
        """
        if type(path_or_handle) in [io.BufferedReader, io.BytesIO]:
            self.from_bytesio_or_handle(path_or_handle)
        elif isinstance(path_or_handle, str):
            # read file from path
            if not os.path.exists(path_or_handle):
                raise FileNotFoundError(f"File {path_or_handle} not found.")

            self.path = path_or_handle
            # self.content_type = mimetypes.guess_type(self.file_name)[0] or "application/octet-stream"
            with open(path_or_handle, 'rb') as file:
                self.from_bytesio_or_handle(file)  # method also calls self._file_info.

        return self

    def from_bytes(self, data: bytes):
        self._reset_buffer()
        self._content_buffer.write(data)
        self._content_buffer.seek(0)
        self._file_info()
        return self

    def from_starlette_upload_file(self, starlette_upload_file):
        """
        Load a file from a starlette upload file.
        :param starlette_upload_file:
        :return:
        """
        # in file info all the meta is retrieved from the file.name in case of buffered reader
        content = starlette_upload_file.file.read()
        if starlette_upload_file.size == 0:
            raise ValueError("UploadFile file is empty.")

        self.file_name = starlette_upload_file.filename
        self.content_type = starlette_upload_file.content_type
        self.from_bytes(content)
        return self

    def from_base64(self, base64_str: str):
        """
        Load a file which was encoded as a base64 string.
        """
        decoded, media_type = self._decode_base_64_if_is(base64_str)
        if media_type is not None:
            self.content_type = media_type

        if decoded is not None:
            return self.from_bytes(decoded)
        else:
            err_str = base64_str if len(base64_str) <= 50 else base64_str[:50] + "..."
            raise ValueError(f"Decoding from base64 like string {err_str} was not possible. Check your data.")

    @requires_numpy()
    def from_np_array(self, np_array: np.array):
        """
        Convert a numpy array to a file which is saved as bytes b"\x93NUMPY" into the buffer.
        """
        self._reset_buffer()
        np.save(self._content_buffer, np_array)
        return self

    def from_dict(self, file_result_json: dict):
        """
        Load a file from a dictionary.
        :param d: The dictionary to load from formatted as FileModel.to_json().
        """
        self.file_name = file_result_json["file_name"]
        self.content_type = file_result_json["content_type"]
        # ToDo: the from_base64 might overwrite name and content type (ImageFile). Check if this always is intended.
        return self.from_any(file_result_json["content"])

    def from_url(self, url: str):
        """
        Download a file from an url.
        """
        file, original_file_name = download_file(url)
        self.file_name = original_file_name
        return self.from_bytesio_or_handle(file, copy=False)

    @requires_numpy()
    def to_np_array(self, shape=None, dtype=np.uint8):
        """
        If file was created with from_np_array it will return the numpy array.
        Else it will try to convert the file to a numpy array (note this is converted bytes representation of the file).
        :param shape: The shape of the numpy array. If None it will be returned flat.
        :param dtype: The dtype of the numpy array. If None it will be uint8.
        """
        bytes = self.to_bytes()
        # check if was saved with np.save so bytes contains NUMPY
        if bytes.startswith(b"\x93NUMPY"):
            self._content_buffer.seek(0)
            return np.load(self._content_buffer, allow_pickle=False)

        shape = shape or (1, len(bytes))
        dtype = dtype or np.uint8

        arr_flat = np.frombuffer(bytes, dtype=dtype)
        return arr_flat.reshape(shape)

    def to_bytes(self) -> bytes:
        return self.read()

    def read(self) -> bytes:
        self._content_buffer.seek(0)
        res = self._content_buffer.read()
        self._content_buffer.seek(0)
        return res

    def to_bytes_io(self) -> io.BytesIO:
        """
        Returns the file as a BytesIO object.
        :return: BytesIO object
        """
        return self._content_buffer.to_bytes_io()

    def to_base64(self):
        return base64.b64encode(self.to_bytes()).decode('ascii')

    def to_httpx_send_able_tuple(self):
        return self.file_name, self.read(), self.content_type

    def _reset_buffer(self):
        self._content_buffer.seek(0)
        self._content_buffer.truncate(0)

    def save(self, path: str = None):
        """
        Methods saves the file to disk.
        If path is a folder it will save it in folder/self.filename.
        If path is a file it will save it there.
        :param path:
        :return:
        """
        # set to working directory if path is None
        if path is None:
            path = os.path.curdir
        # create folder if not exists
        elif os.path.dirname(path) != "" and not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

        # check if path contains a file name add default if not given
        if os.path.isdir(path):
            if self.file_name is None:
                self.file_name = "media_toolkit_output"
                print(f"No file name given. Using {self.file_name}")
            path = os.path.join(path, self.file_name)

        with open(path, 'wb') as file:
            file.write(self.read())

    def _file_info(self):
        """
        After writing the file to the buffer, this method is called to determine additional file informations.
        For videos this might be length, frame rate...
        If you subclass don't forget to call super()._file_info() to set the file name and content type.
        """
        # cases when file_info is called
        # from_file -> retrieve info directly from the file path
        # from bytesio -> tempfile
        # from bytes -> tempfile
        # from buffered_reader -> set path -> from bytes -> get info from previously set file_path
        # from np_array -> tempfile
        # from starlette_upload_file -> from_buffered_reader(spooled_temporary) -> info from the spooled_temporary
        # from base64 -> from-bytes -> tempfile
        # from url -> from bytesio
        if self.path is not None:
            self.file_name = os.path.basename(self.path)
            self.content_type = mimetypes.guess_type(self.file_name)[0] or "application/octet-stream"
        elif hasattr(self._content_buffer, "name") and self._content_buffer.name is not None:
            self.file_name = os.path.basename(self._content_buffer.name)

        if self.content_type is None:
            self.content_type = "application/octet-stream"

    def file_size(self, unit="bytes") -> int:
        """
        :param unit: bytes, kb, mb or gb
        """
        size_in_ = self._content_buffer.getbuffer().nbytes
        if unit == "bytes":
            return size_in_
        elif unit == "kb":
            size_in_ = size_in_ / 1000
        elif unit == "mb":
            size_in_ = size_in_ / 1000000
        elif unit == "gb":
            size_in_ = size_in_ / 1000000000
        return size_in_

    @property
    def extension(self) -> Union[str, None]:
        """
        Will try to guess the file type based on the detected mimetype.
        If no mimetype is detected it will try to guess the file extension based on the file name.
        :return: the guessed file extension without '.'.
        """
        if self.file_name is None and self.content_type == "application/octet-stream":
            return None

        if self.content_type and self.content_type != "application/octet-stream":
            guessed_ext = mimetypes.guess_extension(self.content_type)
            if guessed_ext:
                return guessed_ext.replace(".", "").lower()

        if self.file_name is not None:
            return None

        return self.file_name.rsplit(".", 1)[-1]

    def __bytes__(self):
        return self.to_bytes()

    def __array__(self):
        return self.to_np_array()

    def to_json(self):
        """
        Returns the file as a json serializable dictionary.
        :return: { "file_name": str, "content_type": str, "content": str }
        """
        return {
            "file_name": self.file_name,
            "content_type": self.content_type,
            "content": self.to_base64()
        }

    @staticmethod
    def _parse_base64_uri(data: str) -> Tuple[str, Optional[str]]:
        """
        Parse base64 string, handling data URI format and extracting content.
        Args:
            data (str): Base64 encoded string, potentially with data URI prefix
        Returns:
            Tuple of (base64 content, optional media_type)
        """
        # Regex to match data URI format: data:[<media type>][;base64],<data>
        data_uri_pattern = r'^data:(?P<mediatype>[\w/\-\.]+)?(?:;base64)?,(?P<base64>.*)'

        # Check if the string matches data URI format
        match = re.match(data_uri_pattern, data)
        if match:
            # Extract media type and base64 content
            media_type = match.group('mediatype')
            base64_content = match.group('base64')
            return base64_content, media_type

        # If no data URI prefix, return the original string
        return data, None

    @staticmethod
    def _decode_base_64_if_is(data: Union[bytes, str]) -> Tuple[Union[str, None], Union[str, None]]:
        """
        Checks if a string is base64 (or base64uri).
        :param data: The data to decode.
        :return: If is base64 (decoded base64 data as bytes, optional media_type) else None, None
        """
        media_type = None
        if isinstance(data, str):
            # check if is uri format and parse it
            data, media_type = MediaFile._parse_base64_uri(data)
            data = data.encode()

        # Decode and Re-encode the data to check if it is valid base64
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

    @staticmethod
    def _is_valid_file_path(path: str):
        try:
            is_file = os.path.isfile(path)
            return is_file
        except Exception:
            return False

    @staticmethod
    def _is_url(url: str):
        if not isinstance(url, str):
            return False

        return urlparse(url).scheme in ['http', 'https']

    @staticmethod
    def _is_starlette_upload_file(data):
        return hasattr(data, '__module__') and data.__module__ == 'starlette.datastructures' and type(data).__name__ == 'UploadFile'

    @staticmethod
    def _is_file_model(data: dict):
        if not isinstance(data, dict):
            if not hasattr(data, "__dict__"):
                return False
            data = dict(data)

        return "file_name" in data and "content" in data

    def __sizeof__(self):
        """Returns the memory size of the instance + actual file/buffer size."""
        cls_size = super().__sizeof__()
        cls_size = cls_size if cls_size is not None else 0
        file_size = self.file_size("bytes")
        return cls_size + file_size
