import io
from fractions import Fraction
from typing import Optional, Union, List, Literal, Tuple, Iterator

from media_toolkit.core.media_files.audio.audio_stream import AudioStream
from media_toolkit.core.media_files.audio.audio_info import AudioInfo, get_audio_info
from media_toolkit.utils.dependency_requirements import requires
from media_toolkit.core.media_files.media_file import MediaFile
from media_toolkit.utils.generator_wrapper import SimpleGeneratorWrapper

try:
    import av
    import numpy as np
except ImportError:
    pass


class AudioFile(MediaFile):
    """
    Specialized media file for audio processing with advanced audio capabilities.
    
    Features:
    - Native PyAV integration for high-quality audio processing
    - Support for various audio formats (WAV, MP3, OGG, FLAC, AAC, etc.)
    - Sample rate and channel detection
    - Audio streaming and chunking capabilities
    - High-performance numpy array conversions
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._audio_info: Optional[AudioInfo] = None

    @property
    def audio_info(self) -> AudioInfo:
        if self._audio_info is None:
            self._audio_info = get_audio_info(self)
        return self._audio_info

    @requires('av', 'numpy')
    def to_np_array(self, sr: int = None, return_sample_rate: bool = False):
        """
        Convert audio to numpy array with optional sample rate conversion using PyAV.
        
        Args:
            sr: Target sample rate (None for native sample rate)
            return_sample_rate: If True, returns tuple of (audio, sample_rate)
            
        Returns:
            Numpy array (shape: (samples, channels), dtype=float32 in [-1, 1])
            or tuple of (array, sample_rate)
        """
        buf = self.to_bytes_io()
        buf.seek(0)

        with av.open(buf) as container:
            a_stream = next((s for s in container.streams if s.type == 'audio'), None)
            if a_stream is None:
                raise ValueError("No audio stream found")

            input_sample_rate = getattr(a_stream, 'sample_rate', None) or sr or 44100

            resampler = None
            if sr is not None and sr > 0 and a_stream.sample_rate and a_stream.sample_rate != sr:
                # Keep sample format s16 for broad compatibility
                layout = getattr(a_stream, 'layout', None) or ("stereo" if getattr(a_stream, 'channels', 1) == 2 else "mono")
                resampler = av.AudioResampler(format='s16', layout=layout, rate=sr)

            chunks: List[np.ndarray] = []
            for frame in container.decode(a_stream):
                if resampler is not None:
                    frames = resampler.resample(frame) or []
                else:
                    frames = [frame]

                for fr in frames:
                    arr = fr.to_ndarray()  # shape: (channels, samples), dtype by sample format
                    if arr.dtype == np.int16:
                        arr = (arr.astype(np.float32) / 32768.0)
                    else:
                        arr = arr.astype(np.float32)
                    chunks.append(arr)

            if not chunks:
                audio = np.zeros((0, getattr(a_stream, 'channels', 1)), dtype=np.float32)
                sample_rate = sr or input_sample_rate
            else:
                concat = np.concatenate(chunks, axis=1)  # (channels, total_samples)
                audio = concat.T  # (samples, channels)
                sample_rate = sr or input_sample_rate

        # Cache detected properties
        if self._sample_rate is None:
            self._sample_rate = sample_rate
        if self._channels is None:
            self._channels = 1 if audio.ndim == 1 else audio.shape[1]

        if return_sample_rate:
            return audio, sample_rate
        return audio

    @requires('av', 'numpy')
    def from_np_array(
        self,
        np_array: Union[np.ndarray, List[np.ndarray], Tuple[np.ndarray, ...]],
        sample_rate: int = 44100,
        file_type: str = "wav",
        input_layout: Literal["pyav", "soundfile"] = "pyav",
    ):
        """
        Create AudioFile from numpy array(s) with specified parameters using PyAV.
        
        Args:
            np_array: Audio data as numpy array or list/tuple of arrays
                - For input_layout="pyav": shape (channels, samples)
                - For input_layout="soundfile": shape (samples,) or (samples, channels)
            sample_rate: Sample rate (default: 44100 Hz)
            file_type: Audio format (default: "wav")
            input_layout: Indicates the orientation of input arrays
            
        Returns:
            Self for method chaining
        """
        sample_rate = 44100 if sample_rate is None else sample_rate

        # Normalize inputs into a single 2D array: (channels, samples)
        def normalize_to_channels_first(arr_like) -> np.ndarray:
            arr = np.asarray(arr_like)
            if input_layout == "soundfile":
                # (samples,) or (samples, channels) -> (channels, samples)
                if arr.ndim == 1:
                    arr = arr.reshape(-1, 1)
                else:
                    arr = arr  # (samples, channels)
                arr = arr.T
            else:
                # Expected (channels, samples); if (samples,) promote to mono
                if arr.ndim == 1:
                    arr = arr.reshape(1, -1)
            return arr

        if isinstance(np_array, (list, tuple)):
            chunks_cf = [normalize_to_channels_first(a) for a in np_array if a is not None and np.asarray(a).size > 0]
            if len(chunks_cf) == 0:
                raise ValueError("Input array list is empty")
            # Validate consistent channel count
            ch = chunks_cf[0].shape[0]
            for c in chunks_cf:
                if c.shape[0] != ch:
                    raise ValueError("All chunks must have the same number of channels")
            audio_cf = np.concatenate(chunks_cf, axis=1)
        else:
            audio_cf = normalize_to_channels_first(np_array)

        # Convert to int16 for broad encoder compatibility
        if audio_cf.dtype != np.int16:
            if np.issubdtype(audio_cf.dtype, np.floating):
                audio_cf = (np.clip(audio_cf, -1.0, 1.0) * 32767).astype(np.int16)
            else:
                audio_cf = audio_cf.astype(np.int16)

        channels = int(audio_cf.shape[0])
        total_samples = int(audio_cf.shape[1])

        # Choose codec based on file_type
        codec_map = {
            'wav': 'pcm_s16le',
            'wave': 'pcm_s16le',
            'mp3': 'mp3',
            'flac': 'flac',
            'ogg': 'vorbis',
            'aac': 'aac',
            'm4a': 'aac',
        }
        normalized_ft = (file_type or 'wav').lower()
        codec_name = codec_map.get(normalized_ft, 'pcm_s16le')
        layout = 'stereo' if channels == 2 else 'mono'

        buffer = io.BytesIO()
        container = av.open(buffer, mode='w', format=normalized_ft)
        try:
            a_stream = container.add_stream(codec_name, rate=sample_rate, layout=layout)
            a_stream.time_base = Fraction(1, sample_rate)

            # Encode in moderately sized chunks
            chunk_size = 4096
            audio_pts = 0
            for start in range(0, total_samples, chunk_size):
                end = min(start + chunk_size, total_samples)
                chunk_cf = audio_cf[:, start:end]
                chunk_pk = chunk_cf.T
                
                # For packed formats, PyAV's `from_ndarray` expects a 2D array with shape
                # (1, samples * channels) and C-contiguous memory layout.
                flat_chunk = np.ascontiguousarray(chunk_pk).reshape(1, -1)

                a_frame = av.AudioFrame.from_ndarray(flat_chunk, format='s16', layout=layout)
                a_frame.sample_rate = sample_rate
                a_frame.pts = audio_pts
                a_frame.time_base = Fraction(1, sample_rate)
                for packet in a_stream.encode(a_frame):
                    container.mux(packet)
                audio_pts += (end - start)

            # Flush
            for packet in a_stream.encode():
                container.mux(packet)
        finally:
            container.close()

        # Update self from file and clean up temp
        self.from_bytes(buffer.getvalue())

        # Set content type based on format
        self.content_type = f"audio/{self._normalize_audio_format(file_type)}"
        self._audio_info = AudioInfo(sample_rate=sample_rate, channels=channels)
        return self

    @requires('av', 'numpy')
    def from_audio_generator(
        self,
        audio_generator: Union[Iterator, List],
        sample_rate: int = 44100,
        file_type: str = "wav",
        input_layout: Literal["pyav", "soundfile"] = "pyav",
    ) -> 'AudioFile':
        """
        Create AudioFile from an iterator of audio chunks using existing from_np_array.

        Args:
            audio_generator: Iterator/list of numpy arrays representing audio chunks
            sample_rate: Target sample rate
            file_type: Target audio file type (e.g., 'wav', 'mp3', 'aac')
            input_layout: Orientation of arrays; see from_np_array

        Returns:
            Self for method chaining
        """
        chunks: List[np.ndarray] = []
        for chunk in SimpleGeneratorWrapper(audio_generator):
            if chunk is None:
                continue
            arr = np.asarray(chunk)
            if arr.size == 0:
                continue
            chunks.append(arr)

        if len(chunks) == 0:
            raise ValueError("audio_generator produced no audio chunks")

        return self.from_np_array(chunks, sample_rate=sample_rate, file_type=file_type, input_layout=input_layout)

    @requires('av')
    def to_stream(self) -> AudioStream:
        """
        Create an AudioStream for frame-by-frame processing via PyAV.
        """
        if self.file_size() == 0:
            raise ValueError("Empty audio file")
        buf = io.BytesIO(self.read())
        return AudioStream(buf)

    @requires('av')
    def from_stream(self, stream: 'AudioStream', file_type: str = "wav"):
        """
        Creates an AudioFile from an AudioStream by re-encoding into a new container.

        Args:
            stream: The input AudioStream.
            file_type: The output audio format (e.g., 'wav', 'mp3'). Defaults to 'wav'.
        """
        if not isinstance(stream, AudioStream):
            raise TypeError("Input must be an AudioStream object.")

        buffer = io.BytesIO()
        
        codec_map = {
            'wav': 'pcm_s16le', 'wave': 'pcm_s16le', 'mp3': 'mp3',
            'flac': 'flac', 'ogg': 'vorbis', 'aac': 'aac', 'm4a': 'aac',
        }
        codec_name = codec_map.get(file_type.lower(), 'pcm_s16le')

        output_container = av.open(buffer, mode='w', format=file_type)
        try:
            in_stream = stream._audio_stream
            layout = in_stream.layout.name
            rate = in_stream.sample_rate
            out_stream = output_container.add_stream(codec_name, rate=rate, layout=layout)

            for frame in stream.frames(output_format='av'):
                for packet in out_stream.encode(frame):
                    output_container.mux(packet)
            
            # Flush encoder
            for packet in out_stream.encode():
                output_container.mux(packet)
        finally:
            output_container.close()
        
        self.from_bytes(buffer.getvalue())
        self.content_type = f"audio/{self._normalize_audio_format(file_type)}"
        return self

    def _file_info(self):
        """
        Enhanced file info extraction with audio-specific metadata using PyAV probe.
        Handles both filename extraction and content type detection in one pass.
        """
        # First, handle basic filename extraction from parent
        super()._file_info()
        
        # Then do audio-specific content detection and metadata extraction
        self._audio_info = get_audio_info(self)
        if self.audio_info.is_valid:
            if self.content_type is None and self.audio_info.codec_name:
                self.content_type = f"audio/{self._normalize_audio_format(self.audio_info.codec_name)}"
        else:
            # Fallback: decode quickly to get duration if probe failed
            try:
                audio, sample_rate = self.to_np_array(return_sample_rate=True)
                self._audio_info.sample_rate = self.audio_info.sample_rate or sample_rate
                self._audio_info.channels = self.audio_info.channels or (1 if audio.ndim == 1 else audio.shape[1])
                self._audio_info.duration = self.audio_info.duration or (len(audio) / sample_rate if sample_rate else None)
            except Exception:
                pass
        
        if self.content_type is None:
            print("No content type given or detection failed. Defaulting to audio/wav")
            self.content_type = "audio/wav"
        
        if self.file_name == "file":
            self.file_name = "audiofile"

    @property
    def sample_rate(self) -> Optional[int]:
        """
        Get audio sample rate in Hz.
        
        Returns:
            Sample rate in Hz or None if not determined
        """
        return self.audio_info.sample_rate

    @property
    def channels(self) -> Optional[int]:
        """
        Get number of audio channels.
        
        Returns:
            Number of channels (1 for mono, 2 for stereo, etc.)
        """
        return self.audio_info.channels

    @property
    def duration(self) -> Optional[float]:
        """
        Get audio duration in seconds.
        
        Returns:
            Duration in seconds or None if not determined
        """
        return self.audio_info.duration

    @property
    def is_mono(self) -> bool:
        """Check if audio is mono (single channel)."""
        return self.channels == 1

    @property
    def is_stereo(self) -> bool:
        """Check if audio is stereo (two channels)."""
        return self.channels == 2

    def _get_audio_format(self) -> str:
        """Get current audio format from content type."""
        if self.content_type and self.content_type.startswith('audio/'):
            return self.content_type.split('/')[-1]
        return 'wav'  # Default

    def _normalize_audio_format(self, file_type: str) -> str:
        """Normalize audio format names for content type."""
        format_mappings = {
            'mp3': 'mpeg',
            'aac': 'aac',
            'ogg': 'ogg',
            'flac': 'flac',
            'wav': 'wav',
            'wave': 'wav',
            'aiff': 'aiff',
            'wma': 'x-ms-wma',
            'mp3': 'mpeg',
        }
        return format_mappings.get(file_type.lower(), file_type.lower())
