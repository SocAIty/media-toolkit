import glob
import os
import tempfile
from io import BytesIO
from typing import List, Union

from media_toolkit.core.video.video_utils import (add_audio_to_video_file, audio_array_to_audio_file,
                                                  video_from_image_generator, get_audio_sample_rate_from_file)
from media_toolkit.utils.generator_wrapper import SimpleGeneratorWrapper
from media_toolkit.utils.dependency_requirements import requires
from media_toolkit.core.media_file import MediaFile

try:
    import cv2
    import numpy as np
except ImportError:
    pass

try:
    from vidgear.gears import VideoGear, WriteGear
except:
    pass

try:
    from pydub import AudioSegment
    from pydub.utils import mediainfo
except ImportError:
    pass


class VideoFile(MediaFile):
    """
    A class to represent a video file.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content_type = "video"
        self.frame_count = None
        self.frame_rate = None
        self.width = None
        self.height = None
        self.shape = None
        self.duration = None
        self.audio_sample_rate = None
        self._temp_file_path = None  # if to_temp_file is called, the path is stored here. Needed clean deletion

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
            self.from_file(combined)
            os.remove(combined)
            os.remove(temp_vid_file_path)
            return self

        # Init self from the temp file
        self.from_file(temp_vid_file_path)
        # remove tempfile
        os.remove(temp_vid_file_path)

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

        if self.audio_sample_rate is None:
            if self.frame_rate is None:
                raise Exception("The frame rate of the video file is not set. Read a video file first.")

            if os.path.isfile(audio_file):
                self.audio_sample_rate = get_audio_sample_rate_from_file(audio_file)
            else:
                self.audio_sample_rate = get_audio_sample_rate_from_file(self._to_temp_file())

        if isinstance(audio_file, list) or isinstance(audio_file, np.ndarray):
            audio_file = audio_array_to_audio_file(audio_file, sample_rate=sample_rate)

        tmp = self._to_temp_file()
        combined = add_audio_to_video_file(tmp, audio_file)
        self.from_file(combined)
        os.remove(tmp)
        os.remove(combined)
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

    @requires('vidgear', 'numpy', 'pydub')
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
                self.from_file(combined)
                # cleanup
                os.remove(temp_audio_file)
                os.remove(temp_video_file_path)
                os.remove(combined)
                return self
            except Exception as e:
                print(f"Error adding audio_file to video. Returning video without audio. {e.__traceback__} ")

        # if no audio_file was added
        self.from_file(temp_video_file_path)
        try:
            os.remove(temp_video_file_path)
        except Exception as e:
            print(f"couldn't remove temp file {temp_video_file_path} after video was created from stream.")

        return self

    @requires('cv2', 'pydub')
    def _file_info(self):
        """
        Gets video file information using mediainfo without necessarily writing to a temporary file.
        Sets: file_name, content_type, frame_count, duration, width, height, shape, audio_sample_rate, frame_rate
        """
        super()._file_info()  # sets: file_name, content_type

        # Helper function to parse mediainfo values
        def info_to_number(info_dict: dict, key: str, default_val=None, cast=float):
            if key in info_dict:
                val = info_dict[key]
                if val == 'N/A':
                    return default_val
                val = val.split("/")[0]  # split if / in val and take first
                return cast(val)
            return default_val

        path = self.path
        # Try to get info directly if path exists
        saved_to_temporary_file = False
        if not self.path or not os.path.exists(self.path):
            path = self._to_temp_file()
            saved_to_temporary_file = True

        info = mediainfo(path)

        # Extract basic video information
        self.frame_count = info_to_number(info, 'nb_frames', cast=int)
        self.duration = info_to_number(info, 'duration')
        self.width = info_to_number(info, 'width', cast=int)
        self.height = info_to_number(info, 'height', cast=int)
        self.shape = (self.width, self.height) if self.width and self.height else None
        self.audio_sample_rate = info_to_number(info, 'sample_rate', 44100)
        self.frame_rate = info_to_number(info, 'avg_frame_rate')

        # Use cv2 as fallback for frame rate and count if needed
        if self.frame_rate is None or self.frame_count is None or self.frame_count == 1:
            try:
                cap = cv2.VideoCapture(path)
                if self.frame_rate is None:
                    self.frame_rate = cap.get(cv2.CAP_PROP_FPS)
                if self.frame_count is None or self.frame_count == 1:
                    self.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                cap.release()
            finally:
                if saved_to_temporary_file:
                    try:
                        os.remove(path)
                    except:
                        pass

        # Set content type based on format information
        if 'format_name' in info:
            format_name = info['format_name'].split(",")[0]
            self.content_type = f"video/{format_name}"
        else:
            # Try to determine format from file extension if available
            if self.file_name:
                ext = os.path.splitext(self.file_name)[1].lower()
                if ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
                    self.content_type = f"video/{ext[1:]}"
            else:
                self.content_type = "video/mp4"  # default fallback

    #@requires('cv2', 'pydub')
    #def _file_info(self):
    #    super()._file_info()  # sets: file_name, content_type.
#
    #    # care for the case that it was loaded from_bytes what usually does not provide any filename / info.
    #    # In this case we need to write the data first to file and then retrieve the info again.
    #    path = self.path
    #    is_temp_file = False
    #    if path is None or not os.path.exists(path):
    #        self._content_buffer.seek(0)
    #        path = self._to_temp_file()
    #        is_temp_file = True
#
    #    # get video info
    #    info = mediainfo(path)
#
    #    def info_to_number(key: str, default_val=None, cast=float):
    #        if key in info:
    #            val = info[key]
    #            if val == 'N/A':
    #                return default_val
    #            # split if / in val and take first
    #            val = val.split("/")[0]
    #            return cast(val)
    #        return default_val
#
    #    self.frame_count = info_to_number('nb_frames', cast=int)
    #    self.duration = info_to_number('duration')
    #    self.width = info_to_number('width', cast=int)
    #    self.height = info_to_number('height', cast=int)
    #    self.shape = (self.width, self.height)
    #    self.audio_sample_rate = info_to_number('sample_rate', 44100)
#
    #    self.frame_rate = info_to_number('avg_frame_rate', None)
    #    # need to determine the frame rate with cv2 because pydub calculation gives some weird results..
    #    if self.frame_rate is None or self.frame_count is None or self.frame_count == 1:
    #        cap = cv2.VideoCapture(path)
    #        self.frame_rate = cap.get(cv2.CAP_PROP_FPS)
    #        self.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    #        cap.release()
#
    #    # if self.width is None or self.height is None:
    #    #    # try to get it with cv2
    #    #    cap = cv2.VideoCapture(path)
    #    #    self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    #    #    self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    #    #    self.shape = (self.width, self.height)
    #    #    self.frame_rate = cap.get(cv2.CAP_PROP_FPS)
    #    #    cap.release()
    #    # else:
    #    #    if self.frame_count is not None and self.duration is not None:
    #    #        self.frame_rate = int(self.frame_count / self.duration)
#
    #    if 'format_name' in info:
    #        format_name = info['format_name'].split(",")[0]
    #        self.content_type = f"video/{format_name}"
    #    else:
    #        self.content_type = "video/mp4"  # overwrite default "application/octet-stream"
#
    #    # if is tempfile remove it
    #    if is_temp_file:
    #        try:
    #            os.remove(path)
    #        except Exception as e:
    #            # If the file came from an buffered file, then the temp_file was not copied but kept in the buffer.
    #            # The file is then already in use and thus can't be deleted.
    #            pass

    @requires('vidgear')
    def to_image_stream(self):
        return self.to_video_stream(include_audio=False)

    @requires('pydub', 'vidgear')
    def to_video_stream(self, include_audio=True):
        """
        Yields video frames and audio_file data as numpy arrays.
        :param include_audio: if the audio_file is included in the video stream. If not it will only yield the video frames.
        :return:
        """
        self._content_buffer.seek(0)
        # because CamGear does not support reading from a BytesIO buffer, we need to save the buffer to a temporary file
        temp_video_file_path = self._to_temp_file()
        stream = VideoGear(source=temp_video_file_path).start()

        if include_audio:
            # Extract audio_file using pydub
            try:
                audio = AudioSegment.from_file(temp_video_file_path)
                # Calculate the audio_file segment duration per frame
                audio_per_frame_duration = 1000 / stream.framerate  # duration of each video frame in ms
            except:
                include_audio = False
                print("Could not extract audio_file from video file. Audio will not be included in the video stream.")

        # Initialize frame counter for audio_file and better self.frame count
        frame_count = 0
        audio_shape = None  # if the audio in a frame is to short or mishaped fill it with silence.
        try:
            while True:
                # Read frame
                frame = stream.read()
                if frame is None:
                    break

                if not include_audio:
                    yield frame
                    continue

                # Calculate the start and end times for the corresponding audio_file segment
                start_time = frame_count * audio_per_frame_duration
                end_time = start_time + audio_per_frame_duration
                frame_audio = audio[start_time:end_time]

                # Convert audio_file segment to raw data
                audio_data = np.array(frame_audio.get_array_of_samples())

                # CODE TO DEAL WITH ERRORS AND IMPUTE VALUES
                # save the first shape of the audio data
                if audio_shape is None and len(audio_data) > 0:
                    audio_shape = audio_data.shape

                if audio_data is None:
                    # sometimes in a frame theres no audio data. Then we need to fill it with silence.
                    audio_data = np.zeros(audio_shape)

                # impute missing values or cut too long audio arrays
                if audio_shape is not None:
                    if len(audio_data) < audio_shape[0]:
                        audio_data = np.pad(audio_data, (0, audio_shape[0] - len(audio_data)), 'constant')
                    elif len(audio_data) > audio_shape[0]:
                        audio_data = audio_data[:audio_shape[0]]

                # Yield the frame and the corresponding audio_file data
                yield frame, audio_data

                # Increment frame counter
                frame_count += 1
        finally:
            # Safely close the video stream
            stream.stop()
            # Remove the temporary video file
            os.remove(temp_video_file_path)
            # accurate value instead of using cv2.CAP_PROP_FRAME_COUNT
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
            os.remove(temp_video_file_path)
            return None

        # return as bytes
        file = BytesIO()
        file = audio.export(file, format=export_type)
        file.seek(0)
        data = file.read()
        file.close()
        # remove tempfile
        os.remove(temp_video_file_path)
        return data

    def __iter__(self):
        return self.to_video_stream()

    def __len__(self):
        return int(self.frame_count)

    def __del__(self):
        if self._temp_file_path is not None:
            try:
                os.remove(self._temp_file_path)
            except Exception as e:
                print("Could not delete temporary file. Error: ", e)

