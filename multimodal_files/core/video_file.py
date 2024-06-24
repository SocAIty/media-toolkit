import os
import tempfile
from io import BytesIO
from typing import Union

from multimodal_files.dependency_requirements import requires
from multimodal_files.core.multimodal_file import MultiModalFile

try:
    import cv2
    import numpy as np
except ImportError:
    pass

try:
    import av
except ImportError:
    pass

try:
    import soundfile as sf
except ImportError:
    pass


class VideoFile(MultiModalFile):
    """
    A class to represent a video file.
    """
    def __init__(self):
        super().__init__()
        self.content_type = "video"
        self.frame_count = None  # an estimated value based on cv2.VideoCapture.get(cv2.CAP_PROP_FRAME_COUNT)
        self.frame_rate = None
        self.shape = None

    def from_image_files(self, image_files: list[str], frame_rate: int = 30):
        """
        Converts a list of image files into a video file.
        """
        # Check if there are images in the list
        if not image_files:
            raise ValueError("The list of image files is empty.")

        # Read the first image to get the dimensions
        first_image = cv2.imread(image_files[0])
        if first_image is None:
            raise ValueError(f"Could not read the first image from the path: {image_files[0]}")

        height, width, layers = first_image.shape
        self.shape = first_image.shape

        self.frame_count = 0
        self.frame_rate = frame_rate
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video_file:
            # Define the codec and create VideoWriter object
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec for .mp4 files
            video_writer = cv2.VideoWriter(temp_video_file.name, fourcc, frame_rate, (width, height))

            for image_file in image_files:
                img = cv2.imread(image_file)
                if img is None:
                    print(f"Warning: Skipping file {image_file} as it cannot be read.")
                    continue
                video_writer.write(img)
                self.frame_count += 1

            # Release the VideoWriter object
            video_writer.release()

            # Read the temporary video file into a BytesIO object
            temp_video_file.seek(0)
            video_data = temp_video_file.read()

        # Clean up the temporary file
        os.remove(temp_video_file.name)
        # Set the content buffer to the video data
        self._content_buffer = BytesIO(video_data)
        return self

    @staticmethod
    def _add_to_av_container(av_container, video_stream, audio_stream, image, audio_frames, frame_pts):
        # Add the video frame to the container
        frame = av.VideoFrame.from_ndarray(image, format='bgr24')
        frame.pts = frame_pts
        for packet in video_stream.encode(frame):
            av_container.mux(packet)

        # Add the audio frames to the container
        if audio_stream:
            for audio_frame in audio_frames:
                audio_frame.pts = frame_pts
                for packet in audio_stream.encode(audio_frame):
                    av_container.mux(packet)

    @requires('av', 'numpy')
    def from_video_stream(self, video_audio_stream, frame_rate: int = 30):
        """
        Given a generator that yields video frames and audio data as numpy arrays, this creates a video.
        The generator is expected to be in the form of: VideoFile().to_video_stream()
        """
        # Reset and pre-settings
        self._reset_buffer()
        if frame_rate <= 0:
            frame_rate = 30
            print("Warning: Invalid frame rate. Setting to default value of 30.")

        # Create a temporary file for the output video
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        output_container = av.open(temp_file.name, mode='w')

        # Get video dimensions and initialize streams
        first_image, first_audio_frames = next(video_audio_stream)
        height, width, layers = first_image.shape
        video_stream = output_container.add_stream('h264', rate=frame_rate)
        video_stream.width = width
        video_stream.height = height
        video_stream.pix_fmt = 'yuv444p'

        audio_stream = None
        if first_audio_frames:
            sample_rate = first_audio_frames[0].sample_rate
            audio_stream = output_container.add_stream('aac')
            audio_stream.sample_rate = sample_rate
            audio_stream.channels = len(first_audio_frames[0].layout.channels)

        self.frame_count = 0

        # Add the first frame
        self._add_to_av_container(output_container, video_stream, audio_stream, first_image, first_audio_frames,
                                  self.frame_count)

        # Process remaining frames
        for image, audio_frames in video_audio_stream:
            self.frame_count += 1
            self._add_to_av_container(output_container, video_stream, audio_stream, image, audio_frames,
                                      self.frame_count)

        # Flush the streams
        packet = video_stream.encode(None)
        output_container.mux(packet)

        #for packet in video_stream.encode():
        #    output_container.mux(packet)
        #if audio_stream:
        #    for packet in audio_stream.encode():
        #        output_container.mux(packet)
#
        # Close the container and process the temp file
        output_container.close()
        self.from_file(temp_file.name)
        temp_file.close()
        os.remove(temp_file.name)

        return self
    #@requires('av', 'numpy')
    #def from_video_stream(self, video_audio_stream, frame_rate: int = 30):
    #    """
    #    Given a generator that yields video frames and audio data as numpy arrays this creates a video.
    #    the generator is in form of like VideoFile().to_video_stream()
    #    """
    #    # reset and pre settings
    #    self._reset_buffer()
    #    if frame_rate is None or frame_rate <= 0:
    #        print("Warning: Invalid frame rate. Setting to default value of 30.")
    #        frame_rate = 30
    #    self.frame_rate = frame_rate
#
    #    # Create a temporary file for the output video
    #    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    #    output_container = av.open(temp_file, mode='w')
#
    #    # get video dimensions
    #    first_image, first_audio_frames = next(video_audio_stream)
    #    height, width, layers = first_image.shape
    #    self.shape = first_image.shape
#
    #    video_stream = output_container.add_stream('mpeg4', rate=frame_rate)
    #    video_stream.width = width
    #    video_stream.height = height
    #    video_stream.pix_fmt = 'yuv420p'
#
    #    # Create an audio stream in the output container
    #    if first_audio_frames:
    #        sample_rate = first_audio_frames[0].sample_rate
    #        audio_stream = output_container.add_stream('aac')
    #        audio_stream.sample_rate = sample_rate
    #        audio_stream.channels = len(first_audio_frames[0].layout.channels)
    #    else:
    #        audio_stream = None
#
    #    self.frame_count = 0
    #    # add first frame
    #    self._add_to_av_container(output_container, first_image, first_audio_frames, self.frame_count)
#
    #    # Create a video stream in the output container
    #    for image, audio_frames in video_audio_stream:
    #        self.frame_count += 1
    #        # Write video frame
    #        self._add_to_av_container(output_container, image, audio_frames, self.frame_count)
#
    #    # Flush the streams
    #    for packet in video_stream.encode():
    #        output_container.mux(packet)
#
    #    if first_audio_frames:
    #        for packet in audio_stream.encode():
    #            output_container.mux(packet)
#
    #    output_container.close()
#
    #    # now read temp file again and then delete it
    #    self.from_file(temp_file.name)
    #    os.remove(temp_file.name)
#
    #    return self

    def _file_info(self):
        super()._file_info()
        self._content_buffer.seek(0)
        container = av.open(self._content_buffer)
        video_stream = container.streams.video[0]

        # we assume the video is in RGB or BGR format.. ToDo: also check this might cause problems
        self.shape = (video_stream.height, video_stream.width, 3)
        self.frame_rate = video_stream.average_rate
        self.frame_count = video_stream.frames
        self.content_type = f"video/{video_stream.codec_context.name}"
        container.close()
        self._content_buffer.seek(0)

    @requires('av', 'numpy')
    def to_image_stream(self, image_format='bgr24'):
        self._content_buffer.seek(0)
        # Open the video stream from the BytesIO buffer
        container = av.open(self._content_buffer)
        # Iterate through the frames in the video stream
        for frame in container.decode(video=0):
            # Convert the frame to an array if needed (frame.to_image() for PIL Image)
            yield frame.to_ndarray(format=image_format)

        # Close the container
        container.close()
        self._content_buffer.seek(0)

    @requires('av', 'numpy')
    def to_video_stream(self):
        """
        generator yields the video frames and audio data as numpy arrays
        """
        self._content_buffer.seek(0)
        container = av.open(self._content_buffer)

        video_stream = container.streams.video[0]
        audio_stream = container.streams.audio[0]

        video_frames = container.decode(video_stream)
        audio_frames = container.decode(audio_stream)

        audio_frame = next(audio_frames, None)

        for video_frame in video_frames:
            image = video_frame.to_ndarray(format='bgr24')

            # Collect corresponding audio frames until the next video frame timestamp
            audio_data = []
           # while audio_frame and audio_frame.pts <= video_frame.pts:
           #     audio_data.append(audio_frame)
           #     audio_frame = next(audio_frames, None)

            yield (image, audio_data)

        container.close()
        self._content_buffer.seek(0)

    @requires('av', 'numpy')
    def to_audio_numpy(self):
        # Open the video stream from the BytesIO buffer
        self._content_buffer.seek(0)
        container = av.open(self._content_buffer)
        # Get the audio stream from the container
        audio_stream = container.streams.audio[0]
        # Get the audio data from the stream
        audio_data = audio_stream.to_ndarray()
        # Close the container
        container.close()
        self._content_buffer.seek(0)
        return audio_data

    @requires('soundfile')
    def to_audio_file(self, path: str, sample_rate=44100):
        if len(path.split(".")) < 2:
            raise ValueError("The path must include a file extension.")

        audio_data = self.to_audio_numpy()
        # Save the audio data to a file
        sf.write(path, audio_data, sample_rate)

