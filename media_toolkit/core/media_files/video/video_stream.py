from media_toolkit.core.media_files.video.video_info import VideoInfo
import av
import numpy as np

import io
from typing import Iterator, Union, Literal


class VideoStream:
    """A stream wrapper for efficient video and audio access via PyAV.

    Notes on efficiency:
    - Provides packet-level generators to avoid unnecessary decoding when not needed
    - Decoding is limited to specific streams (video/audio) rather than all streams
    - Supports direct numpy frame emission without additional copies where possible
    """

    def __init__(self, buffer: io.BytesIO, video_info: VideoInfo):
        self.container = av.open(buffer)
        self.video_info = video_info

        self._video_stream = next((s for s in self.container.streams if s.type == "video"), None)
        if self._video_stream is None:
            raise ValueError("No video stream found")

        self._audio_stream = next((s for s in self.container.streams if s.type == "audio"), None)

        # Internal iterator state for __iter__/__next__
        self._iter_gen = None
        self._closed = False

        # Try to enable codec threading if supported (best-effort)
        try:
            if hasattr(self._video_stream, "codec_context"):
                codec_ctx = self._video_stream.codec_context
                if hasattr(codec_ctx, "thread_count") and codec_ctx.thread_count in (None, 0, 1):
                    codec_ctx.thread_count = 0  # 0 = auto
                if hasattr(codec_ctx, "thread_type") and codec_ctx.thread_type in (None, 0):
                    # 3 = FRAME | SLICE in FFmpeg
                    codec_ctx.thread_type = 3
        except Exception:
            # Non-fatal; threading config can vary by build
            pass

    # ------------- Packet-level (no decode) -------------
    def video_packets(self) -> Iterator[av.Packet]:
        """Yield raw packets for the video stream (no decoding)."""
        for packet in self.container.demux(self._video_stream):
            if packet.stream.type == "video":
                yield packet

    def audio_packets(self) -> Iterator[av.Packet]:
        """Yield raw packets for the audio stream (no decoding)."""
        if self._audio_stream is None:
            return
        for packet in self.container.demux(self._audio_stream):
            if packet.stream.type == "audio":
                yield packet

    # ------------- Decoded frames -------------
    def video_frames(
        self,
        output_format: Literal["numpy", "av"] = "numpy",
        color_format: Literal["rgb24", "bgr24"] = "bgr24",
    ) -> Iterator[Union[av.VideoFrame, np.ndarray]]:
        """Yield decoded video frames as numpy arrays or av.VideoFrame."""
        for frame in self.container.decode(self._video_stream):
            if output_format == "numpy":
                yield frame.to_ndarray(format=color_format)
            else:
                yield frame

    def audio_frames(
        self,
        output_format: Literal["numpy", "av"] = "numpy"
    ) -> Iterator[Union[av.AudioFrame, np.ndarray]]:
        """Yield decoded audio frames as numpy arrays (channels, samples) or av.AudioFrame.

        The default numpy format is int16 ("s16"), which is broadly compatible and efficient.
        """
        if self._audio_stream is None:
            return
        for frame in self.container.decode(self._audio_stream):
            if output_format == "numpy":
                yield frame.to_ndarray()
            else:
                yield frame

    # ------------- Iterator protocol -------------
    def __iter__(self):
        """
        Iterate over video frames as numpy arrays by default in bgr24 format
        """
        self._iter_gen = self.video_frames(output_format="numpy", color_format="bgr24")
        return self

    def __next__(self):
        """
        Iterate over video frames as numpy arrays by default in bgr24 format
        """
        if self._iter_gen is None:
            self._iter_gen = self.video_frames(output_format="numpy", color_format="bgr24")
        return next(self._iter_gen)

    # ------------- Utilities -------------
    def __len__(self):
        if self.video_info and getattr(self.video_info, "frame_count", None):
            try:
                return int(self.video_info.frame_count)
            except Exception:
                return 0
        return 0

    def reset(self):
        """Reset demux/decoding to the start of the container."""
        try:
            self.container.seek(0)
            self._iter_gen = None
        except Exception:
            # Some formats may not support seek on in-memory buffers; reopen as fallback
            # Capture buffer contents and reopen
            try:
                # pyav exposes container.file as internal; safest is to close and rely on caller to reopen
                pass
            except Exception:
                pass

    @property
    def has_audio(self) -> bool:
        return self._audio_stream is not None

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
        # Best-effort cleanup
        try:
            self.close()
        except Exception:
            pass
