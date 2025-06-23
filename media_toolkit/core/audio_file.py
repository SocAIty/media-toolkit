import io
from typing import Optional
from media_toolkit.utils.dependency_requirements import requires
from media_toolkit.core.media_file import MediaFile
from media_toolkit.utils.generator_wrapper import SimpleGeneratorWrapper
from media_toolkit.utils.media_type_guesser import guess_content_type

try:
    import soundfile
    import numpy as np
except ImportError:
    pass


class AudioFile(MediaFile):
    """
    Specialized media file for audio processing with advanced audio capabilities.
    
    Features:
    - Native soundfile integration for high-quality audio processing
    - Support for various audio formats (WAV, MP3, OGG, FLAC, AAC, etc.)
    - Sample rate and channel detection
    - Audio streaming and chunking capabilities
    - High-performance numpy array conversions
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content_type = "audio/wav"  # Default audio type
        self._sample_rate = None  # Audio sample rate cache
        self._channels = None  # Audio channel count cache
        self._duration = None  # Audio duration cache

    @requires('soundfile')
    def to_soundfile(self):
        """
        Get audio as soundfile format tuple.
        
        Returns:
            Tuple of (audio_data, sample_rate)
        """
        self._content_buffer.seek(0)
        return soundfile.read(self._content_buffer)

    @requires('soundfile')
    def to_np_array(self, sr: int = None, return_sample_rate: bool = False):
        """
        Convert audio to numpy array with optional sample rate conversion.
        
        Args:
            sr: Target sample rate (None for native sample rate)
            return_sample_rate: If True, returns tuple of (audio, sample_rate)
            
        Returns:
            Numpy array or tuple of (array, sample_rate)
        """
        self._content_buffer.seek(0)
        audio, sample_rate = soundfile.read(self._content_buffer, samplerate=sr)
        
        # Cache detected properties
        if self._sample_rate is None:
            self._sample_rate = sample_rate
        if self._channels is None:
            self._channels = 1 if audio.ndim == 1 else audio.shape[1]
        
        if return_sample_rate:
            return audio, sample_rate
        return audio

    @requires('soundfile')
    def from_np_array(self, np_array, sr: int = 44100, file_type: str = "wav"):
        """
        Create AudioFile from numpy array with specified parameters.
        
        Args:
            np_array: Audio data as numpy array
            sr: Sample rate (default: 44100 Hz)
            file_type: Audio format (default: "wav")
            
        Returns:
            Self for method chaining
        """
        sr = 44100 if sr is None else sr
        
        # Create virtual file for soundfile
        virtual_file = io.BytesIO()
        virtual_file.name = f"audio_file.{file_type}"
        
        soundfile.write(virtual_file, np_array, samplerate=sr, format=file_type)
        
        # Set content type based on format
        self.content_type = f"audio/{self._normalize_audio_format(file_type)}"
        self._sample_rate = sr
        self._channels = 1 if np_array.ndim == 1 else np_array.shape[1]
        
        virtual_file.seek(0)
        # Call UniversalFile.from_file directly to avoid duplicate _file_info calls
        super(MediaFile, self).from_file(virtual_file)
        self._file_info()
        return self

    @requires('soundfile')
    def to_stream(self, chunks_per_second: int = 10):
        """
        Generate audio chunks for streaming playback.
        
        Args:
            chunks_per_second: Number of chunks per second for streaming
            
        Returns:
            Generator yielding audio chunks as numpy arrays
        """
        audio, sample_rate = self.to_soundfile()
        chunk_size = sample_rate // chunks_per_second
        n_chunks = len(audio) // chunk_size + 1

        def generator():
            for i in range(n_chunks):
                start_idx = i * chunk_size
                end_idx = min(start_idx + chunk_size, len(audio))
                chunk = audio[start_idx:end_idx]
                yield chunk.astype(np.float32)

        g = SimpleGeneratorWrapper(generator=generator(), length=n_chunks)
        g.sample_rate = sample_rate
        return g

    def _file_info(self):
        """
        Enhanced file info extraction with audio-specific metadata.
        Detects sample rate, channels, duration, and optimizes content type.
        """
        super()._file_info()
        
        # Extract audio-specific information
        if self.file_size() > 0:
            try:
                # Get audio properties using soundfile
                audio, sample_rate = self.to_np_array(return_sample_rate=True)
                
                # Cache audio properties
                self._sample_rate = sample_rate
                self._channels = 1 if audio.ndim == 1 else audio.shape[1]
                self._duration = len(audio) / sample_rate
                
                # Improve content type detection
                if self.file_name:
                    detected_type = guess_content_type(self.file_name)
                    if detected_type.startswith('audio/'):
                        self.content_type = detected_type
                        
            except Exception as e:
                print(f"Could not extract audio metadata: {e}")
                # Fallback to filename-based detection
                if self.file_name:
                    detected_type = guess_content_type(self.file_name)
                    if detected_type.startswith('audio/'):
                        self.content_type = detected_type

    @property
    def sample_rate(self) -> Optional[int]:
        """
        Get audio sample rate in Hz.
        
        Returns:
            Sample rate in Hz or None if not determined
        """
        if self._sample_rate is None:
            try:
                _, self._sample_rate = self.to_np_array(return_sample_rate=True)
            except Exception:
                pass
        return self._sample_rate

    @property
    def channels(self) -> Optional[int]:
        """
        Get number of audio channels.
        
        Returns:
            Number of channels (1 for mono, 2 for stereo, etc.)
        """
        if self._channels is None:
            try:
                audio = self.to_np_array()
                self._channels = 1 if audio.ndim == 1 else audio.shape[1]
            except Exception:
                pass
        return self._channels

    @property
    def duration(self) -> Optional[float]:
        """
        Get audio duration in seconds.
        
        Returns:
            Duration in seconds or None if not determined
        """
        if self._duration is None:
            try:
                audio, sr = self.to_np_array(return_sample_rate=True)
                self._duration = len(audio) / sr
            except Exception:
                pass
        return self._duration

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
            'wma': 'x-ms-wma'
        }
        return format_mappings.get(file_type.lower(), file_type.lower())
