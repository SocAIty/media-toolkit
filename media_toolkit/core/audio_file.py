from media_toolkit.dependency_requirements import requires
from media_toolkit.core.media_file import MediaFile
import io

try:
    import soundfile
    import numpy as np
except ImportError:
    pass


class AudioFile(MediaFile):
    """
    Has file conversions that make it easy to work with image files across the web.
    """
    @requires('soundfile')
    def to_soundfile(self):
        return soundfile.read(self._content_buffer)

    @requires('soundfile')
    def to_np_array(self, sr: int = None, return_sample_rate: bool = False):
        self._content_buffer.seek(0)
        audio, sr = soundfile.read(self._content_buffer, samplerate=sr)  # sr=None returns the native sample rate
        if return_sample_rate:
            return audio, sr
        return audio

    @requires('soundfile')
    def from_np_array(self, np_array, sr: int = 44100, file_type: str = "wav"):
        sr = 44100 if sr is None else sr  # 22050
        # write to virtual file with librosa
        virtual_file = io.BytesIO()
        virtual_file.name = f"audio_file.{file_type}"
        soundfile.write(virtual_file, np_array, samplerate=sr, format=file_type)
        return super().from_file(virtual_file)

