import base64
import io
import mimetypes
from typing import Union, BinaryIO
import os

from media_toolkit.dependency_requirements import requires_numpy


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
            else:
                self.from_base64(data)
        elif isinstance(data, bytes):
            self.from_bytes(data)
        elif type(data).__name__ == 'ndarray':
            self.from_np_array(data)
        elif data.__module__ == 'starlette.datastructures' and type(data).__name__ == 'UploadFile':
            self.from_starlette_upload_file(data)

        return self

    def from_bytesio_or_handle(self, buffer: Union[io.BytesIO, BinaryIO, io.BufferedReader], copy: bool = True):
        """
        Set the content of the file from a BytesIO or a file handle.
        :params buffer: The buffer to read from.
        :params copy: If true, the buffer is completely read to bytes and the bytes copied to this file.
        """
        self._reset_buffer()
        if type(buffer) in [io.BytesIO, io.BufferedReader]:
            buffer.seek(0)
            if not copy:
                self._content_buffer = buffer
                self._file_info()
            else:
                self.from_bytes(buffer.read())
                buffer.seek(0)

        return self

    def from_bytesio(self, buffer: Union[io.BytesIO, BinaryIO], copy: bool = True):
        return self.from_bytesio_or_handle(buffer=buffer, copy=copy)

    #@staticmethod
    #@overload
    #def from_file(path_or_handle: Union[str, io.BytesIO, io.BufferedReader]):
    #    return MediaFile().from_file(path_or_handle)

    def from_file(self, path_or_handle: Union[str, io.BytesIO, io.BufferedReader]):
        """
        Load a file from a file path, file handle or base64 and convert it to BytesIO.
        """
        if type(path_or_handle) in [io.BufferedReader, io.BytesIO]:
            self.from_bytesio_or_handle(path_or_handle)
        elif isinstance(path_or_handle, str):
            # read file from path
            self.file_name = os.path.basename(path_or_handle)
            self.content_type = mimetypes.guess_type(self.file_name)[0] or "application/octet-stream"
            with open(path_or_handle, 'rb') as file:
                self.from_bytesio_or_handle(file)

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
        content = starlette_upload_file.file.read()

        self.file_name = starlette_upload_file.filename
        self.content_type = starlette_upload_file.content_type
        self.from_bytes(content)
        return self

    def from_base64(self, base64_str: str):
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
        return self._content_buffer

    def to_base64(self):
        return base64.b64encode(self.to_bytes()).decode()

    def to_httpx_send_able_tuple(self):
        return self.file_name, self.read(), self.content_type

    def _reset_buffer(self):
        self._content_buffer.seek(0)
        self._content_buffer.truncate(0)

    def save(self, path: str):
        """
        Methods saves the file to disk.
        If path is a folder it will save it in folder/self.filename.
        If path is a file it will save it there.
        :param path:
        :return:
        """
        # create folder if not exists
        if os.path.dirname(path) != "" and not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        # check if path contains a file name
        if os.path.basename(path) == "":
            path = os.path.join(path, self.file_name)

        with open(path, 'wb') as file:
            file.write(self.read())

    def _file_info(self):
        """
        After writing the file to the buffer, this method is called to determine additional file informations.
        For videos this might be length, frame rate...
        If you subclass don't forget to call super()._file_info() to set the file name and content type.
        """
        # set file name and type
        if hasattr(self._content_buffer, "name"):
            self.file_name = os.path.basename(self._content_buffer.name)

        if self.file_name != "file":
            self.content_type = mimetypes.guess_type(self.file_name)[0] or "application/octet-stream"
        else:
            self.content_type = "application/octet-stream"

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

