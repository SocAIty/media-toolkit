import io
import os
import tempfile
from typing import BinaryIO, Iterator


class FileContentBuffer:
    """Handles file content storage either in memory, temporary file, or as a borrowed view.

    A buffer is either *owned* (we created the memory buffer / temp file and may
    write, truncate, and delete it) or *borrowed* (a view on an external seekable
    handle such as a Starlette upload spool or an open path handle). Borrowed
    buffers are never truncated or deleted; call :meth:`materialize` to copy the
    content into an owned buffer.
    """

    def __init__(
            self,
            use_temp_file: bool = False,
            temp_dir: str = None
    ):
        """Initialize buffer with given configuration.
        :param use_temp_file: If True, store content in temporary file instead of keeping it in memory.
        :param temp_dir: Directory to store temporary files in. If None, system default is used.
        """
        self._use_temp_file = use_temp_file
        self._temp_dir = temp_dir

        self._temp_file = None
        self._memory_buffer = None
        self._owns_buffer = True
        self._initialize_buffer()

    @property
    def name(self) -> str:
        """Get path to temporary file if used.
        Returns:
            str: Path to temporary file. None if not used.
        """
        if self._temp_file:
            return self._temp_file.name
        # Borrowed path handles also expose a usable name (e.g. open(path, 'rb')).
        handle_name = getattr(self._memory_buffer, "name", None)
        if isinstance(handle_name, str) and os.path.exists(handle_name):
            return handle_name
        return None

    @property
    def owns_buffer(self) -> bool:
        """True when the buffer content is owned by this instance (safe to mutate/delete)."""
        return self._owns_buffer

    @property
    def fileobj(self) -> BinaryIO:
        """The underlying seekable handle (owned buffer, temp file, or borrowed source)."""
        return self._temp_file if self._temp_file is not None else self._memory_buffer

    def _initialize_buffer(self):
        """Initialize the appropriate buffer based on configuration."""
        if self._use_temp_file:
            self._temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                dir=self._temp_dir
            )
            self._memory_buffer = None
        else:
            self._memory_buffer = io.BytesIO()
            self._temp_file = None
        self._owns_buffer = True

    def overwrite_buffer(self, buf: BinaryIO, owns: bool = True):
        """
        Set the buffer to use an existing seekable handle (BytesIO, spool, open file).

        This causes:
            - use_temp_file to be set to False. Any existing owned tempfile is closed and deleted.
            - the class to operate directly on the given handle.

        Args:
            buf: Seekable binary handle to use as buffer.
            owns: False when the handle is borrowed (e.g. a Starlette upload spool).
                  Borrowed handles are never truncated or deleted by this class.
        """
        self._use_temp_file = False
        self._remove_temp_file()
        self._memory_buffer = buf
        self._owns_buffer = owns

    def write(self, data: bytes):
        """Write data to the buffer.

        Args:
            data (bytes): Data to write.

        Raises:
            ValueError: If the buffer is a borrowed view (call materialize first).
        """
        if not self._owns_buffer:
            raise ValueError("Cannot write to a borrowed buffer. Call materialize() first.")
        if self._use_temp_file:
            self._temp_file.write(data)
        else:
            self._memory_buffer.write(data)

    def read(self, number_of_bytes: int = None) -> bytes:
        """Read content from the buffer starting at position 0; position is restored to 0.

        Returns:
            bytes: Buffer content.
        """
        handle = self.fileobj
        handle.seek(0)
        content = handle.read(number_of_bytes)
        handle.seek(0)
        return content

    def peek(self, number_of_bytes: int = 1024) -> bytes:
        """Read the first bytes without disturbing the current position."""
        handle = self.fileobj
        pos = handle.tell()
        handle.seek(0)
        content = handle.read(number_of_bytes)
        handle.seek(pos)
        return content

    def chunks(self, chunk_size: int = 65536) -> Iterator[bytes]:
        """Iterate over the content in chunks starting from position 0."""
        handle = self.fileobj
        handle.seek(0)
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            yield chunk

    def size(self) -> int:
        """Content size in bytes, determined via seek; works for borrowed handles."""
        handle = self.fileobj
        pos = handle.tell()
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        handle.seek(pos)
        return size

    def materialize(self):
        """Copy a borrowed view into an owned buffer. Idempotent for owned buffers."""
        if self._owns_buffer:
            return
        source = self.fileobj
        self._memory_buffer = None
        self._initialize_buffer()
        source.seek(0)
        while True:
            chunk = source.read(65536)
            if not chunk:
                break
            self.write(chunk)
        self.seek(0)

    def seek(self, offset: int, whence: int = 0):
        """Seek to given position in buffer.

        Args:
            offset (int): Position to seek to.
            whence (int): Origin of the seek.
        """
        self.fileobj.seek(offset, whence)

    def truncate(self, size: int):
        """Truncate buffer to given size.

        Args:
            size (int): Size to truncate to.

        Raises:
            ValueError: If the buffer is a borrowed view.
        """
        if not self._owns_buffer:
            raise ValueError("Cannot truncate a borrowed buffer. Call materialize() first.")
        self.fileobj.truncate(size)

    def reset(self):
        """Empty the buffer. Borrowed views are detached (never truncated in place)."""
        if not self._owns_buffer:
            self._memory_buffer = None
            self._initialize_buffer()
            return
        self.seek(0)
        self.truncate(0)

    def getbuffer(self) -> memoryview:
        """Get a memoryview of the buffer content.

        Returns:
            memoryview: View of buffer content.
        """
        if not self._use_temp_file and isinstance(self._memory_buffer, io.BytesIO):
            return self._memory_buffer.getbuffer()
        return memoryview(self.read())

    def to_bytes_io(self) -> io.BytesIO:
        """Convert the buffer to a BytesIO object.
        Returns:
            io.BytesIO: A BytesIO object containing the buffer's content.
        """
        if not self._use_temp_file and isinstance(self._memory_buffer, io.BytesIO):
            # If already a BytesIO, reset position and return
            self._memory_buffer.seek(0)
            return self._memory_buffer

        # Create new BytesIO and write content
        content = self.read()
        bytes_io = io.BytesIO()
        bytes_io.write(content)
        bytes_io.seek(0)
        return bytes_io

    def _remove_temp_file(self):
        if self._temp_file:
            try:
                self._temp_file.close()
                os.remove(self._temp_file.name)
                self._temp_file = None
            except Exception:
                pass

    def __del__(self):
        """Cleanup temporary files on deletion."""
        self._remove_temp_file()
