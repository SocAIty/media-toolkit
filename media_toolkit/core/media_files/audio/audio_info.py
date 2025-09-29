from dataclasses import dataclass
from media_toolkit.core.media_files.media_file import MediaFile

try:
    import av
except ImportError:
    pass


@dataclass
class AudioInfo:
    """Audio metadata container with validation and derived properties."""
    sample_rate: int = None
    channels: int = None
    duration: float = None
    codec_name: str = None
    layout: str = None
    bit_rate: int = None

    @property
    def is_valid(self) -> bool:
        """Check if essential audio metadata is present."""
        return all([self.sample_rate, self.channels, self.duration])


def get_audio_info(media_file: MediaFile) -> AudioInfo:
    """Probe audio metadata using PyAV."""
    info = AudioInfo()
    if media_file.file_size() == 0:
        return info

    try:
        buf = media_file.to_bytes_io()
        with av.open(buf) as c:
            a = next((s for s in c.streams if s.type == "audio"), None)
            if not a:
                return info

            duration = None
            if getattr(a, 'duration', None) and getattr(a, 'time_base', None):
                duration = float(a.duration * a.time_base)
            elif getattr(c, 'duration', None):
                # AV_TIME_BASE is 1_000_000
                duration = float(c.duration / 1_000_000)

            codec_name = None
            try:
                codec_name = getattr(getattr(a, 'codec_context', None), 'name', None) or getattr(a, 'name', None)
            except Exception:
                pass
            
            info.sample_rate = getattr(a, 'sample_rate', None)
            info.channels = getattr(a, 'channels', None)
            info.duration = duration
            info.codec_name = codec_name
            info.layout = getattr(a, 'layout.name', 'unknown')
            info.bit_rate = getattr(a, 'bit_rate', None)

    except Exception:
        pass  # Ignore errors, return partial info
    
    return info
