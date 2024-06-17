from multimodal_files.dependency_requirements import requires
from multimodal_files.core.upload_file import UploadFile
import io

try:
    import soundfile
    import numpy as np
except ImportError:
    pass


class AudioFile(UploadFile):
    """
    Has file conversions that make it easy to work with image files across the web.
    Internally it uses numpy and librosa.
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
    def from_np_array(self, np_array, sr: int = None, file_type: str = "wav"):
        sr = 22050 if sr is None else sr
        # write to virtual file with librosa
        virtual_file = io.BytesIO()
        virtual_file.name = f"audio_file.{file_type}"
        soundfile.write(virtual_file, np_array, samplerate=sr, format=file_type)

        super().from_file(virtual_file)

