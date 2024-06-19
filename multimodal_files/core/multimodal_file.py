import base64
import io
import mimetypes
from typing import Union
import os

from multimodal_files.dependency_requirements import requires_numpy, requires

try:
    import numpy as np
    from fastapi.responses import Response
except ImportError:
    pass


class MultiModalFile:
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
        self.file_name = file_name
        self._content_buffer = io.BytesIO()

    def set_content(self, buffer: Union[io.BytesIO, io.BufferedReader],
                    path_or_handle: Union[str, io.BytesIO, io.BufferedReader]):
        # read buffer
        self._reset_buffer()
        if type(buffer) in [io.BytesIO, io.BufferedReader]:
            buffer.seek(0)
            self._content_buffer = buffer

        # set file name and type
        self.file_name = path_or_handle if isinstance(path_or_handle, str) else path_or_handle.name
        self.file_name = os.path.basename(self.file_name)
        self.content_type = mimetypes.guess_type(self.file_name)[0] or "application/octet-stream"

    def from_file(self, path_or_handle: Union[str, io.BytesIO, io.BufferedReader]):
        """
        Load a file from a file path, file handle or base64 and convert it to BytesIO.
        """
        if type(path_or_handle) in [io.BufferedReader, io.BytesIO]:
            self.set_content(path_or_handle, path_or_handle)
        elif isinstance(path_or_handle, str):
            # read file from path
            with open(path_or_handle, 'rb') as file:
                file_content = file.read()
            self.from_bytes(file_content)

        return self

    def from_bytes(self, data: bytes):
        self._reset_buffer()
        self._content_buffer.write(data)
        self._content_buffer.seek(0)
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

    def to_bytes(self) -> bytes:
        return self.read()

    def read(self) -> bytes:
        self._content_buffer.seek(0)
        res = self._content_buffer.read()
        self._content_buffer.seek(0)
        return res

    def to_bytes_io(self) -> io.BytesIO:
        return self._content_buffer

    #def from_bytes_io(self, bytes_io: io.BytesIO, copy=True):
    #    bytes_io.seek(0)
    #    if not copy:
    #        self._reset_buffer()
    #        self._content_buffer = bytes_io
    #    else:
    #        self.from_bytes(bytes_io.read())
#
    #    return self

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

    def from_base64(self, base64_str: str):
        decoded = self._decode_base_64_if_is(base64_str)
        if decoded is not None:
            return self.from_bytes(base64.b64decode(base64_str))
        else:
            raise ValueError("Decoding from base64 like string was not possible. Check your data.")

    def to_base64(self):
        return base64.b64encode(self.to_bytes()).decode()

    @requires_numpy()
    def from_np_array(self, np_array: np.array):
        """
        Convert a numpy array to a file which is saved as bytes b"\x93NUMPY" into the buffer.
        """
        self._reset_buffer()
        np.save(self._content_buffer, np_array)
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
            return np.load(self._content_buffer)

        shape = shape or (1, len(bytes))
        dtype = dtype or np.uint8

        arr_flat = np.frombuffer(bytes, dtype=dtype)
        return arr_flat.reshape(shape)

    def to_httpx_send_able_tuple(self):
        return self.file_name, self.read(), self.content_type

    def _reset_buffer(self):
        self._content_buffer.seek(0)
        self._content_buffer.truncate(0)

    def save(self, path: str):
        # create directory if not exists
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

        # if path includes filename save file there. If not append self.filename
        if os.path.isdir(path):
            path = os.path.join(path, self.file_name)

        with open(path, 'wb') as file:
            file.write(self.read())

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

