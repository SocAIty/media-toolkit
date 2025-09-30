from typing import Tuple
from dataclasses import dataclass
from media_toolkit.core.media_files.media_file import MediaFile

try:
    import av
except ImportError:
    pass

# Map extension -> (container format, codec)
EXT_TO_FORMAT_CODEC = {
    # Uncompressed / PCM
    "wav": ("wav", "pcm_s16le"),
    "wave": ("wav", "pcm_s16le"),
    "aiff": ("aiff", "pcm_s16be"),
    "aif": ("aiff", "pcm_s16be"),
    "au": ("au", "pcm_s16be"),
    "snd": ("au", "pcm_s16be"),

    # Lossy compressed
    # Prefer modern encoders where applicable
    "mp3": ("mp3", "libmp3lame"),
    "aac": ("adts", "aac"),        # raw AAC = ADTS container
    "m4a": ("mp4", "aac"),         # most common iTunes-style
    "mp4": ("mp4", "aac"),         # could also use 'alac'
    "mkv": ("matroska", "aac"),    # can hold many codecs
    "wma": ("asf", "wmav2"),       # Windows Media Audio
    "asf": ("asf", "wmav2"),
    "ra": ("rm", "real_144"),     # RealAudio legacy
    "rm": ("rm", "real_144"),

    # Modern compressed
    "ogg": ("ogg", "vorbis"),      # could also be opus
    "opus": ("ogg", "libopus"),    # prefer libopus encoder
    "oga": ("ogg", "vorbis"),      # alt extension for OGG audio
    "flac": ("flac", "flac"),

    # Other container-ish ones
    "mka": ("matroska", "flac"),   # Matroska Audio
    "mov": ("mov", "aac"),         # Apple QuickTime container
    "3gp": ("3gp", "aac"),         # Mobile container
    "3g2": ("3gp", "aac"),         # Mobile container
}


def ext_to_format_codec(ext: str) -> Tuple[str, str]:
    """
    Return (container format, codec) for a given extension.
    If combination is not found, return "wav", "pcm_s16le".
    This is used for pyav to know valid combinations of container format and codec.
    """
    if ext is None:
        return None
    ext = ext.lower().lstrip(".")
    return EXT_TO_FORMAT_CODEC.get(ext)


def codec_to_format_codec_ext(codec: str) -> Tuple[str, str, str]:
    """
    Return (container format, codec) for a given codec.
    If combination is not found, return "wav", "pcm_s16le".
    This is used for pyav to know valid combinations of container format and codec.
    """
    if codec is None:
        return None
    
    codec = codec.lower().strip()
    for ext, format_codecs in EXT_TO_FORMAT_CODEC.items():
        if codec in format_codecs:
            return (*format_codecs, ext)
    return None


def get_valid_format_codec_ext_combination(ext: str = None, codec: str = None) -> Tuple[str, str, str]:
    """
    Return (container format, codec) for a given codec.
    If combination is not found, return "wav", "pcm_s16le".
    This is used for pyav to know valid combinations of container format and codec.
    """
    if ext is None and codec is None:
        return "wav", "pcm_s16le", "wav"
    
    if ext is not None:
        _fc = ext_to_format_codec(ext)
        if _fc is not None:
            return (*_fc, ext)
    
    _fce = codec_to_format_codec_ext(codec)
    if _fce is not None:
        return _fce

    print(f"No valid combination found for {ext} and {codec}, returning default 'wav', 'pcm_s16le'")
    return "wav", "pcm_s16le", "wav"


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
            # layout can be a Layout object or a string depending on backend
            try:
                layout = getattr(a, 'layout', None)
                if hasattr(layout, 'name'):
                    info.layout = layout.name
                elif isinstance(layout, str):
                    info.layout = layout
                else:
                    info.layout = None
            except Exception:
                info.layout = None
            info.bit_rate = getattr(a, 'bit_rate', None)

    except Exception:
        pass  # Ignore errors, return partial info
    
    return info
