import io
import os
import tempfile


class FileContentBuffer:
    """Handles file content storage either in memory or temporary file."""

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
        self._initialize_buffer()

    @property
    def name(self) -> str:
        """Get path to temporary file if used.
        Returns:
            str: Path to temporary file. None if not used.
        """
        if self._temp_file:
            return self._temp_file.name
        return None

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

    def overwrite_buffer(self, buf: io.BytesIO):
        """
        Set the buffer to use an existing BytesIO object.
        This will cause:
            - that use tempfile is set to False. And existing tempfile is closed and deleted.
            - the class works entirely in memory.
        This is useful, if you want to use the buffer with an existing BytesIO object to speed up the process.
        Args:
            buf (io.BytesIO): BytesIO object to use as buffer.
        """
        self._use_temp_file = False
        self._remove_temp_file()
        self._memory_buffer = buf

    def write(self, data: bytes):
        """Write data to the buffer.

        Args:
            data (bytes): Data to write.

        Raises:
            ValueError: If data exceeds configured size limit.
        """
        if self._use_temp_file:
            self._temp_file.write(data)
        else:
            self._memory_buffer.write(data)

    def read(self) -> bytes:
        """Read all content from the buffer.

        Returns:
            bytes: Buffer content.
        """
        if self._use_temp_file:
            self._temp_file.seek(0)
            return self._temp_file.read()
        else:
            self._memory_buffer.seek(0)
            return self._memory_buffer.read()

    def seek(self, offset: int):
        """Seek to given position in buffer.

        Args:
            offset (int): Position to seek to.
        """
        if self._use_temp_file:
            self._temp_file.seek(offset)
        else:
            self._memory_buffer.seek(offset)

    def truncate(self, size: int):
        """Truncate buffer to given size.

        Args:
            size (int): Size to truncate to.
        """
        if self._use_temp_file:
            self._temp_file.truncate(size)
        else:
            self._memory_buffer.truncate(size)

    def getbuffer(self) -> memoryview:
        """Get a memoryview of the buffer content.

        Returns:
            memoryview: View of buffer content.
        """
        if self._use_temp_file:
            return memoryview(self.read())
        else:
            return self._memory_buffer.getbuffer()

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
            except:
                pass

    def __del__(self):
        """Cleanup temporary files on deletion."""
        self._remove_temp_file()