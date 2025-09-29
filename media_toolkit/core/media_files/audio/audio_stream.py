import av
import numpy as np


import io
from typing import Iterator, Literal, Union, Optional


class AudioStream:
    """A stream wrapper for efficient audio access via PyAV.

    Provides decoded frame iteration as numpy arrays or av.AudioFrame,
    and exposes basic stream metadata when available.
    """

    def __init__(self, buffer: io.BytesIO):
        self.container = av.open(buffer)
        self._audio_stream = next((s for s in self.container.streams if s.type == "audio"), None)
        if self._audio_stream is None:
            raise ValueError("No audio stream found")

        self._iter_gen = None
        self._closed = False

    def frames(self, output_format: Literal["numpy", "av"] = "numpy") -> Iterator[Union[av.AudioFrame, np.ndarray]]:
        for frame in self.container.decode(self._audio_stream):
            if output_format == "numpy":
                yield frame.to_ndarray()
            else:
                yield frame

    def __iter__(self):
        self._iter_gen = self.frames(output_format="numpy")
        return self

    def __next__(self):
        if self._iter_gen is None:
            self._iter_gen = self.frames(output_format="numpy")
        return next(self._iter_gen)

    @property
    def sample_rate(self) -> Optional[int]:
        try:
            return getattr(self._audio_stream, "sample_rate", None)
        except Exception:
            return None

    @property
    def channels(self) -> Optional[int]:
        try:
            return getattr(self._audio_stream, "channels", None)
        except Exception:
            return None

    @property
    def duration(self) -> Optional[float]:
        try:
            if getattr(self._audio_stream, "duration", None) is not None and getattr(self._audio_stream, "time_base", None):
                return float(self._audio_stream.duration * self._audio_stream.time_base)
            if getattr(self.container, "duration", None) is not None:
                # container duration is in microseconds
                return float(self.container.duration / 1_000_000)
        except Exception:
            return None
        return None

    def close(self):
        if not self._closed:
            try:
                self.container.close()
            finally:
                self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass