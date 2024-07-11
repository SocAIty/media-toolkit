from media_toolkit.utils.dependency_requirements import requires
from media_toolkit.core.media_file import MediaFile
import io

from media_toolkit.utils.generator_wrapper import SimpleGeneratorWrapper

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

    @requires('soundfile')
    def to_stream(self, chunks_per_second: int = 10):
        """
        Generator that yields audio chunks of 1/chunks_per_second as numpy arrays.
        :param chunks_per_second: Number of chunks per second
        :return: Generator that yields numpy arrays with audio data.
        """

        audio, sample_rate = self.to_soundfile()
        chunk_size = sample_rate // chunks_per_second
        n_chunks = len(audio) // chunk_size + 1

        def generator():
            for i in range(n_chunks):
                chunk = audio[i * chunk_size: i * chunk_size + chunk_size]
                yield chunk.astype(np.float32) #.tobytes()

        g = SimpleGeneratorWrapper(generator=generator(), length=n_chunks)
        g.sample_rate = sample_rate
        return g
