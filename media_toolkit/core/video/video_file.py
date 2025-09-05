import glob
import os
import tempfile
from io import BytesIO
from typing import List, Union, Optional

from media_toolkit.core.video.video_utils import (add_audio_to_video_file, audio_array_to_audio_file,
                                                  video_from_image_generator, get_audio_sample_rate_from_file)
from media_toolkit.utils.generator_wrapper import SimpleGeneratorWrapper
from media_toolkit.utils.dependency_requirements import requires
from media_toolkit.core.media_file import MediaFile
from media_toolkit.core.video.video_file_info import get_video_info, VideoInfo

try:
    import numpy as np
except ImportError:
    pass

try:
    import av
    try:
        av.logging.set_level(24)  # warning level
    except Exception:
        pass
except ImportError:
    pass

try:
    from pydub import AudioSegment
except ImportError:
    pass


class VideoFile(MediaFile):
    """
    A class to represent a video file.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.video_info: Optional[VideoInfo] = None
        self.frame_count = None
        self.frame_rate = None
        self.width = None
        self.height = None
        self.shape = None
        self.duration = None
        self.audio_sample_rate = None
        self._temp_file_path = None  # if to_temp_file is called, the path is stored here. Needed clean deletion

    def _safe_remove(self, path: str, silent: bool = True, message: str = None):
        """
        Remove a file if it exists. Optionally print a message on failure.
        Clears `_temp_file_path` if it matches the removed path.
        """
        if not path:
            return
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            if not silent:
                if message:
                    print(f"{message}. Error: {e}")
                else:
                    print(f"Could not remove temporary file {path}. Error: {e}")
        finally:
            if self._temp_file_path == path:
                self._temp_file_path = None

    def from_files(self, image_files: Union[List[str], list], frame_rate: int = 30, audio_file=None):
        """
        Creates a video based of a list of image files and an audio_file file.
        :param image_files: A list of image files to convert to a video. Either paths or numpy arrays.
        :param frame_rate: The frame rate of the video.
        :param audio_file: The audio_file file to add to the video, as path, bytes or AudioSegment.
        """
        # Check if there are images in the list
        if not image_files:
            raise ValueError("The list of image files is empty.")

        # Create a temporary file to store the video
        temp_vid_file_path = video_from_image_generator(image_files, frame_rate=frame_rate, save_path=None)
        # Merge video and audio_file using pydub
        if audio_file is not None:
            combined = add_audio_to_video_file(video_file=temp_vid_file_path, audio_file=audio_file)
            # Call UniversalFile.from_file directly to avoid duplicate _file_info calls
            super(MediaFile, self).from_file(combined)
            self._file_info()
            self._safe_remove(combined)
            self._safe_remove(temp_vid_file_path)
            return self

        # Init self from the temp file
        # Call UniversalFile.from_file directly to avoid duplicate _file_info calls
        super(MediaFile, self).from_file(temp_vid_file_path)
        self._file_info()
        # remove tempfile
        self._safe_remove(temp_vid_file_path)

        return self

    def from_image_files(self, image_files: List[str], frame_rate: int = 30):
        """
        Converts a list of image files into a video file.
        """
        return self.from_files(image_files, frame_rate, audio_file=None)

    def from_dir(self, dir_path: str, audio: Union[str, list] = None, frame_rate: int = 30):
        """
        Converts all images in a directory into a video file.
        """
        image_types = ["*.png", "*.jpg", "*.jpeg"]
        image_files = []
        for image_type in image_types:
            image_files.extend(glob.glob(os.path.join(dir_path, image_type)))
        # sort by date to make sure the order is correct
        image_files.sort(key=lambda x: os.path.getmtime(x))

        # if audio_file is none, take the first audio_file file in the directory
        if audio is None:
            audio_types = ["*.wav", "*.mp3"]
            for audio_type in audio_types:
                audio = glob.glob(os.path.join(dir_path, audio_type))
                if len(audio) > 0:
                    audio = audio[0]
                else:
                    audio = None

        return self.from_files(image_files=image_files, frame_rate=frame_rate, audio_file=audio)

    def add_audio(self, audio_file: Union[str, list], sample_rate: int = 44100):
        """
        Adds audio to the video file.
        :param audio_file: The audio_file file to add to the video, as path, or numpy array.
            In case of a file, the sample rate is determined from the file.
        :param sample_rate: If the audio_file is a numpy array, the sample rate should be provided.
        """

        # Ensure we have a temp video file available and tracked
        tmp = self._to_temp_file()

        if self.audio_sample_rate is None:
            if self.frame_rate is None:
                raise Exception("The frame rate of the video file is not set. Read a video file first.")

            if os.path.isfile(audio_file):
                self.audio_sample_rate = get_audio_sample_rate_from_file(audio_file)
            else:
                # Derive sample rate from the video temp file if audio_file is an array
                self.audio_sample_rate = get_audio_sample_rate_from_file(tmp)

        # Normalize audio input to a file path and track if it's a temp we created
        local_audio_file = audio_file
        temp_audio_created = False
        if isinstance(audio_file, list) or isinstance(audio_file, np.ndarray):
            local_audio_file = audio_array_to_audio_file(audio_file, sample_rate=sample_rate)
            temp_audio_created = True

        combined = add_audio_to_video_file(tmp, local_audio_file)
        # Call UniversalFile.from_file directly to avoid duplicate _file_info calls
        super(MediaFile, self).from_file(combined)
        self._file_info()
        self._safe_remove(tmp)
        if temp_audio_created:
            self._safe_remove(local_audio_file)
        self._safe_remove(combined)
        return self

    def _to_temp_file(self):
        # get suffix
        if self.content_type is None:
            raise ValueError("The content type of the video file is not set.")
        if "/" in self.content_type:
            suffix = self.content_type.split("/")[1]
            if suffix == 'octet-stream':
                raise ValueError("The content type of the video file is not valid. Read a video file first.")
        else:
            suffix = "mp4"

        # If already using temp file storage, return path
        if self._content_buffer._use_temp_file:
            return self._content_buffer.name

        # create new temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{suffix}") as temp_video_file:
            temp_video_file.write(self.read())
            temp_video_file_path = temp_video_file.name

        self._temp_file_path = temp_video_file_path
        return temp_video_file_path

    @requires('av', 'numpy', 'pydub')
    def from_video_stream(self, video_audio_stream, frame_rate: int = 30, audio_sample_rate: int = 44100):
        """
        Given a generator that yields video frames and audio_file data as numpy arrays, this creates a video.
        The generator is expected to be in the form of: VideoFile().to_video_stream()
            or a generator that yields images as numpy arrays like VideoFile().to_image_stream().
        """
        # Reset and pre-settings
        self._reset_buffer()

        # new generator, to extract audio_file
        audio_frames = []

        def _frame_gen():
            for frame in video_audio_stream:
                # check if is video and audio_file stream or only video stream
                if isinstance(frame, tuple) and len(frame) == 2:
                    frame, audio_data = frame
                    if audio_data is None:
                        audio_data = np.zeros(0)
                        print("Warning: Audio data is None. Adding silence in frame.")
                    audio_frames.append(audio_data)
                yield frame

        # allows tqdm to work with the generator
        video_gen_wrapper = _frame_gen()
        if hasattr(video_audio_stream, '__len__'):
            video_gen_wrapper = SimpleGeneratorWrapper(video_gen_wrapper, length=len(video_audio_stream))

        # Create video
        temp_video_file_path = video_from_image_generator(video_gen_wrapper, frame_rate=frame_rate, save_path=None)

        # Add audio_file
        if len(audio_frames) > 0:
            try:
                temp_audio_file = audio_array_to_audio_file(audio_frames, sample_rate=audio_sample_rate)
                combined = add_audio_to_video_file(temp_video_file_path, temp_audio_file)
                # Call UniversalFile.from_file directly to avoid duplicate _file_info calls
                super(MediaFile, self).from_file(combined)
                self._file_info()
                # cleanup
                self._safe_remove(temp_audio_file)
                self._safe_remove(temp_video_file_path)
                self._safe_remove(combined)
                return self
            except Exception as e:
                print(f"Error adding audio_file to video. Returning video without audio. {e.__traceback__} ")

        # if no audio_file was added
        # Call UniversalFile.from_file directly to avoid duplicate _file_info calls
        super(MediaFile, self).from_file(temp_video_file_path)
        self._file_info()
        # rely on finally for cleanup

        return self

    def _file_info(self):
        """
        Enhanced file info extraction with video-specific metadata.
        Handles both filename extraction and content type detection in one pass.
        Uses strategy pattern to detect: PyAV > MediaInfo > OpenCV.
        Sets: file_name, content_type, frame_count, duration, width, height, shape, audio_sample_rate, frame_rate
        """
        # First, handle basic filename extraction from parent
        super()._file_info()
        if self.file_size() == 0:
            return

        # Ensure we have a filesystem path
        path = self.path
        saved_to_temporary_file = False
        if not path or not os.path.exists(path):
            path = self._to_temp_file()
            saved_to_temporary_file = True

        # Get video info using utility function and store it
        self.video_info = get_video_info(path)

        # Set attributes from VideoInfo for backward compatibility
        self.frame_rate = self.video_info.frame_rate
        self.frame_count = self.video_info.frame_count
        self.duration = self.video_info.duration
        self.width = self.video_info.width
        self.height = self.video_info.height
        self.audio_sample_rate = self.video_info.audio_sample_rate

        # Prefer VideoInfo.shape computation
        self.shape = self.video_info.shape

        # Cleanup and defaults
        if saved_to_temporary_file:
            self._safe_remove(path)

        if self.content_type is None:
            self.content_type = "video/mp4"

        if self.file_name == "file":
            self.file_name = "videofile"

    @requires('av')
    def to_image_stream(self):
        return self.to_video_stream(include_audio=False)

    @requires('pydub', 'av')
    def to_video_stream(self, include_audio=True):
        """
        Yields video frames and audio_file data as numpy arrays.
        :param include_audio: if the audio_file is included in the video stream. If not it will only yield the video frames.
        :return:
        """
        if self.file_size() == 0:
            raise ValueError("The video file is empty.")

        self._content_buffer.seek(0)
        # because PyAV does not support reading from a BytesIO buffer directly, we need to save the buffer to a temporary file
        temp_video_file_path = self._to_temp_file()

        container = None
        audio = None
        stream_video = None

        try:
            container = av.open(temp_video_file_path)

            for stream in container.streams:
                if stream.type == 'video' and stream_video is None:
                    stream_video = stream
            # We will extract audio separately using pydub for simplicity
            if include_audio:
                try:
                    audio = AudioSegment.from_file(temp_video_file_path)
                    # duration of each video frame in ms
                    # stream_video.average_rate may be Fraction; fallback to self.frame_rate
                    fr = None
                    if stream_video and stream_video.average_rate is not None:
                        fr = float(stream_video.average_rate)
                    if fr is None:
                        fr = self.frame_rate if self.frame_rate else 30
                    audio_per_frame_duration = 1000.0 / fr
                except Exception:
                    include_audio = False
                    print("Could not extract audio_file from video file. Audio will not be included in the video stream.")

            frame_count = 0
            audio_shape = None

            for frame in container.decode(video=0):
                img = frame.to_ndarray(format='bgr24')

                if not include_audio:
                    yield img
                else:
                    start_time = frame_count * audio_per_frame_duration
                    end_time = start_time + audio_per_frame_duration
                    frame_audio = audio[start_time:end_time]
                    audio_data = np.array(frame_audio.get_array_of_samples())

                    if audio_shape is None and len(audio_data) > 0:
                        audio_shape = audio_data.shape

                    if audio_data is None:
                        audio_data = np.zeros(audio_shape)

                    if audio_shape is not None:
                        if len(audio_data) < audio_shape[0]:
                            audio_data = np.pad(audio_data, (0, audio_shape[0] - len(audio_data)), 'constant')
                        elif len(audio_data) > audio_shape[0]:
                            audio_data = audio_data[:audio_shape[0]]

                    yield img, audio_data

                frame_count += 1
        finally:
            if container is not None:
                try:
                    container.close()
                except Exception:
                    pass
            self._safe_remove(temp_video_file_path, silent=False, message=f"Could not remove temporary video file {temp_video_file_path}")
            self.frame_count = frame_count

    @requires('pydub')
    def extract_audio(self, path: str = None, export_type: str = 'mp3') -> Union[bytes, None]:
        temp_video_file_path = self._to_temp_file()
        audio = AudioSegment.from_file(temp_video_file_path)

        if path is not None and len(path) > 0:
            dirname = os.path.dirname(path)
            if len(dirname) > 0 and not os.path.isdir(dirname):
                os.makedirs(dirname)
            audio.export(path, format=export_type)
            self._safe_remove(temp_video_file_path)
            return None

        # return as bytes
        file = BytesIO()
        file = audio.export(file, format=export_type)
        file.seek(0)
        data = file.read()
        file.close()
        # remove tempfile
        self._safe_remove(temp_video_file_path)
        return data

    def __iter__(self):
        return self.to_video_stream()

    def __len__(self):
        return int(self.frame_count)

    def __del__(self):
        if self._temp_file_path is not None:
            self._safe_remove(self._temp_file_path, silent=False, message="Could not delete temporary file")
