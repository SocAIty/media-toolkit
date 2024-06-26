import glob
import os
import sys
import tempfile
from io import BytesIO
from typing import List, Union

from media_toolkit.core.video.video_utils import (add_audio_to_video_file, audio_array_to_audio_file,
                                                     video_from_image_generator, get_sample_rate_from_audio_file)
from media_toolkit.dependency_requirements import requires
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
    def __init__(self):
        super().__init__()
        self.content_type = "video"
        self.frame_count = None  # an estimated value based on cv2.VideoCapture.get(cv2.CAP_PROP_FRAME_COUNT)
        self.frame_rate = None
        self.shape = None
        self.audio_sample_rate = None

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
                    break

        return self.from_files(image_files=image_files, frame_rate=frame_rate, audio_file=audio)

    def add_audio(self, audio_file: Union[str, list], sample_rate: int = 44100):
        if self.audio_sample_rate is None:
            if self.frame_rate is None:
                raise Exception("The frame rate of the video file is not set. Read a video file first.")

            if os.path.isfile(audio_file):
                self.audio_sample_rate = get_sample_rate_from_audio_file(audio_file)
            else:

                self.audio_sample_rate = int(mediainfo(self._to_temp_file())['sample_rate'])


        if isinstance(audio_file, list) or isinstance(audio_file, np.ndarray):
            audio_file = audio_array_to_audio_file(audio_file, sample_rate=self.audio_sample_rate)

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
        if "/" not in self.content_type:
            raise ValueError("The content type of the video file is not valid. Read a video file first.")
        suffix = self.content_type.split("/")[1]
        if suffix == 'octet-stream':
            raise ValueError("The content type of the video file is not valid. Read a video file first.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{suffix}") as temp_video_file:
            temp_video_file.write(self._content_buffer.getvalue())
            temp_video_file_path = temp_video_file.name

        return temp_video_file_path

    @requires('vidgear', 'numpy', 'pydub')
    def from_video_stream(self, video_audio_stream, frame_rate: int = 30):
        """
        Given a generator that yields video frames and audio_file data as numpy arrays, this creates a video.
        The generator is expected to be in the form of: VideoFile().to_video_stream()
        """
        # Reset and pre-settings
        self._reset_buffer()

        # new generator, to extract audio_file
        audio_frames = []
        def _frame_gen():
            for frame in video_audio_stream:
                # check if is video and audio_file stream or only video stream
                if len(frame) == 2:
                    frame, audio_data = frame
                    audio_frames.append(audio_data)
            yield frame

        # Create video
        temp_video_file_path = video_from_image_generator(_frame_gen(), frame_rate=frame_rate, save_path=None)

        # Add audio_file
        if len(audio_frames) > 0:
            temp_audio_file = audio_array_to_audio_file(audio_frames, sample_rate=self.audio_sample_rate)
            combined = add_audio_to_video_file(temp_video_file_path, temp_audio_file)
            self.from_file(combined)
            # cleanup
            os.remove(temp_audio_file)
            os.remove(temp_video_file_path)
            os.remove(combined)

    @requires('cv2', 'pydub')
    def _file_info(self):
        super()._file_info()

        #if file_path is not None:
        #    temp = file_path
        #else:
        self._content_buffer.seek(0)
        temp = self._to_temp_file()

        cap = cv2.VideoCapture(temp)
        self.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))  # is an estimated value.
        # determine content codec
        # https://stackoverflow.com/questions/61659346/how-to-get-4-character-codec-code-for-videocapture-object-in-opencv
        # h = int(cap.get(cv2.CAP_PROP_FOURCC))
        # b = h.to_bytes(4, byteorder=sys.byteorder)
        # codec = b.decode()  # results in the codec
        self.content_type = f"video/mp4"
        self.frame_rate = cap.get(cv2.CAP_PROP_FPS)
        self.shape = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        cap.release()
        # get audio sample rate
        info = mediainfo(temp)
        if 'sample_rate' in info:
            try:
                self.audio_sample_rate = int(info['sample_rate'])
            except ValueError:
                self.audio_sample_rate = 44100
        os.remove(temp)

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
            audio = AudioSegment.from_file(temp_video_file_path)
            # Calculate the audio_file segment duration per frame
            audio_per_frame_duration = 1000 / stream.framerate  # duration of each video frame in ms
            # Initialize frame counter for audio_file
            frame_count = 0

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
    def extract_audio(self, path: str = None, export_type: str = 'mp4') -> Union[bytes, None]:
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
        return self.frame_count
