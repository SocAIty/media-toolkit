import base64
import io
import mimetypes

from typing import Union, BinaryIO
import os
from urllib.parse import urlparse

from media_toolkit.utils.dependency_requirements import requires_numpy

import re

try:
    import numpy as np
except ImportError:
    pass


class MediaFile:
    """
    Has file conversions that make it easy to work standardized with files across the web and in the sdk.
    Works natively with bytesio, base64 and binary data.
    """

    def __init__(self, file_name: str = "file", content_type: str = "application/octet-stream"):
        """
        :param file_name: The name of the file. Note it is overwritten if you use from_file/from_starlette.
        :param content_type: The content type of the file. Note it is overwritten if you use from_file/from_starlette.
        """
        self.content_type = content_type
        self.file_name = file_name  # the name of the file also when specified in bytesio
        self.path = None  # the path of the file if it was provided. Is also indicator if file was loaded from file.
        self._content_buffer = io.BytesIO()

    def from_any(self, data):
        """
        Load a file from any supported data type. The file is loaded into the memory as bytes.
        """
        # it is already converted
        if isinstance(data, MediaFile):
            return data

        # conversion factory
        if type(data) in [io.BufferedReader, io.BytesIO]:
            self.from_bytesio_or_handle(data)
        elif isinstance(data, str):
            if self._is_valid_file_path(data):
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
        elif data.__module__ == 'starlette.datastructures' and type(data).__name__ == 'UploadFile':
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
            If false file works with the provided buffer. Danger -- The buffer is kept open.
        """
        if not type(buffer) in [io.BytesIO, io.BufferedReader]:
            raise ValueError(f"Buffer must be of type BytesIO or BufferedReader. Got {type(buffer)}")

        self._reset_buffer()
        buffer.seek(0)

        # setting path is needed in order that file_info can work properly
        if type(buffer) in [io.BufferedReader]:
            self.path = buffer.name

        if not copy:
            self._content_buffer = buffer
            self._file_info()
        else:
            self.from_bytes(buffer.read())  # calls self._file_info also
            buffer.seek(0)

        return self

    def from_bytesio(self, buffer: Union[io.BytesIO, BinaryIO], copy: bool = True):
        return self.from_bytesio_or_handle(buffer=buffer, copy=copy)

    # @staticmethod
    # @overload
    # def from_file(path_or_handle: Union[str, io.BytesIO, io.BufferedReader]):
    #    return MediaFile().from_file(path_or_handle)
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
        self.file_name = starlette_upload_file.filename
        self.content_type = starlette_upload_file.content_type
        self.from_bytes(content)
        return self

    def from_base64(self, base64_str: str):
        """
        Load a file which was encoded as a base64 string.
        """

        decoded = self._decode_base_64_if_is(base64_str)
        if decoded is not None:
            return self.from_bytes(base64.b64decode(base64_str))
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
        :param d: The dictionary to load from formatted as FileResult.to_json().
        """
        self.file_name = file_result_json["file_name"]
        self.content_type = file_result_json["content_type"]
        # ToDo: the from_base64 might overwrite name and content type (ImageFile). Check if this always is intended.
        self.from_base64(file_result_json["content"])
        return self

    def from_url(self, url: str):
        """
        Download a file from an url.
        """
        # code inspired by: https://github.com/runpod/runpod-python/blob/main/runpod/serverless/utils/rp_download.py
        import requests
        HEADERS = {"User-Agent": "runpod-python/0.0.0 (https://runpod.io; support@runpod.io)"}
        with requests.get(url, headers=HEADERS, stream=True, timeout=5) as response:
            response.raise_for_status()

            # get orig file name or create new
            original_file_name = []
            if "Content-Disposition" in response.headers.keys():
                original_file_name = re.findall(
                    "filename=(.+)",
                    response.headers["Content-Disposition"]
                )

            if len(original_file_name) > 0:
                original_file_name = original_file_name[0]
            else:
                download_path = urlparse(url).path
                original_file_name = os.path.basename(download_path)

            # DOWNLOAD FILE IN Chunks
            file_size = int(response.headers.get('Content-Length', 0))
            # calculate chunk_size
            if file_size <= 1024 * 1024:  # 1 MB
                chunk_size = 1024  # 1 KB
            elif file_size <= 1024 * 1024 * 1024:  # 1 GB
                chunk_size = 1024 * 1024  # 1 MB
            else:
                chunk_size = 1024 * 1024 * 10  # 10 MB

            # write the content in chunks to the file
            file = io.BytesIO()
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:  # filter out keep-alive chunks
                    file.write(chunk)
            file.name = original_file_name
            self.file_name = original_file_name

            # self.url = url

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
        self._content_buffer.seek(0)
        return self._content_buffer

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

        # check if has extension
        # if os.path.splitext(path)[1] == "":
        #    path += ".mp4"

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
        elif hasattr(self._content_buffer, "name"):
            self.file_name = os.path.basename(self._content_buffer.name)

        if self.content_type is None:
            self.content_type = "application/octet-stream"

    def file_size(self, unit="bytes") -> int:
        """
        :param unit:
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
    def _decode_base_64_if_is(data: Union[bytes, str]):
        """
        Checks if a string is base64. If it is, it returns the base64 string as bytes; else returns None.
        """
        if isinstance(data, str):
            data = data.encode()

        try:
            # Decode the data
            decoded = base64.b64decode(data, validate=True)
            # Re-encode the decoded data
            back_encoded = base64.b64encode(decoded)
            # Compare with the original encoded data
            if back_encoded == data:
                return decoded
        except Exception:
            pass

        return None

    @staticmethod
    def _is_valid_file_path(path: str):
        try:
            is_file = os.path.isfile(path)
            return is_file
        except:
            return False

    @staticmethod
    def _is_url(url: str):
        return urlparse(url).scheme in ['http', 'https']
