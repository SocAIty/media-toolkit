import io
import tempfile
import os
import glob
from typing import Iterator, Optional, Union, List, Literal
from fractions import Fraction
from media_toolkit.core.media_files.media_file import MediaFile
from media_toolkit.core.media_files.audio.audio_file import AudioFile
from media_toolkit.core.media_files.video.video_stream import VideoStream
from media_toolkit.utils.dependency_requirements import requires
from .video_info import VideoInfo, get_video_info
from media_toolkit.utils.generator_wrapper import SimpleGeneratorWrapper


try:
    import numpy as np
except ImportError:
    pass

try:
    import av
    av.logging.set_level(24)  # warning level
except Exception:
    pass


IMG_COLOR_FORMATS = Literal["rgb24", "bgr24"]


class VideoFile(MediaFile):
    """
    A class to represent and process a video file using PyAV for efficient,
    packet-based stream handling.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._video_info = None
        self._temp_file_path = None

    def _get_video_info(self):
        if self.path is not None:
            self._video_info = get_video_info(self.path)
        elif self._content_buffer is not None:
            self._video_info = get_video_info(self._content_buffer)
        else:
            self._video_info = None
        return self._video_info

    @property
    def video_info(self) -> VideoInfo:
        if self._video_info is not None:
            return self._video_info
        return self._get_video_info()

    def _file_info(self):
        super()._file_info()
        self._get_video_info()

    def _safe_remove(self, path: str, silent: bool = True, message: str = None):
        """Safely removes a file if it exists."""
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

    def _image_to_ndarray(self, image_file: str, color_format: IMG_COLOR_FORMATS = "bgr24") -> np.ndarray:
        """Converts an image file to a numpy array."""
        container = av.open(image_file)
        for frame in container.decode(video=0):
            img_array = frame.to_ndarray(format=color_format)  # shape: (H, W, 3), dtype=uint8
            break  # only need the first frame for an image
        return img_array

    @requires('av', 'numpy')
    def from_image_generator(
        self,
        frame_generator: Union[Iterator, list],
        frame_rate: int = 30,
        px_fmt: str = "yuv420p",
        color_format: IMG_COLOR_FORMATS = "bgr24",
    ) -> 'VideoFile':
        """
        Encode video frames from a generator into this VideoFile using PyAV.
        """
        frames_iter_wrapper = SimpleGeneratorWrapper(frame_generator)
        gen = iter(frames_iter_wrapper)

        # Peek a first valid frame for dimensions
        first_frame = None
        try:
            while first_frame is None:
                first_frame = next(gen)
        except StopIteration:
            raise ValueError("frame_generator produced no frames")

        def rebuilt_frame_iter():
            yield first_frame
            for f in gen:
                if f is None:
                    continue
                yield f

        height, width = first_frame.shape[0], first_frame.shape[1]

        temp_video_path = tempfile.mktemp(suffix=".mp4")
        try:
            container = av.open(temp_video_path, mode="w", format="mp4")

            # Convert frame rate to proper format
            if isinstance(frame_rate, float):
                # Use a common time base like 1/1000 for millisecond precision
                time_base = Fraction(1, 1000)
                rate = int(frame_rate * 1000)  # Convert to milliseconds
            else:
                time_base = Fraction(1, frame_rate)
                rate = frame_rate

            v_stream = container.add_stream('libx264', rate=rate)
            v_stream.width = width
            v_stream.height = height
            v_stream.pix_fmt = px_fmt or 'yuv420p'
            v_stream.time_base = time_base

            frame_pts = 0
            for frame_nd in rebuilt_frame_iter():
                if frame_nd is None:
                    continue
                if frame_nd.ndim == 2:
                    frame_nd = np.stack([frame_nd] * 3, axis=-1)
                if frame_nd.shape[-1] == 4:
                    frame_nd = frame_nd[:, :, :3]
                if frame_nd.dtype != np.uint8:
                    frame_nd = np.asarray(frame_nd).astype(np.uint8)
                frame = av.VideoFrame.from_ndarray(frame_nd, format=color_format)
                frame.pts = frame_pts
                frame.time_base = time_base
                for packet in v_stream.encode(frame):
                    container.mux(packet)
                # For float frame rates, increment by millisecond intervals
                if isinstance(frame_rate, float):
                    frame_pts += int(1000 / frame_rate)
                else:
                    frame_pts += 1

            for packet in v_stream.encode():
                container.mux(packet)

            container.close()

            self.from_file(temp_video_path)
            self._file_info()
        finally:
            self._safe_remove(temp_video_path)

        return self

    @requires('av', 'numpy')
    def from_generators(
        self,
        frame_generator: Union[Iterator, list],
        audio_generator: Optional[Union[Iterator, list]] = None,
        frame_rate: int = 30,
        px_fmt: str = None,
        audio_sample_rate: int = None,
        audio_output_format: str = None,
        audio_codec: str = None,
    ) -> 'VideoFile':
        """
        Creates a new VideoFile from separate generators for video frames and audio data.
        Args:
            frame_generator: Iterator yielding image frames (numpy arrays)
            audio_generator: Optional iterator yielding audio chunks (numpy arrays)
            frame_rate: Video frame rate
            audio_sample_rate: Audio sample rate
            px_fmt: Pixel format for video encoding
            audio_codec: Audio codec to use
        """
        # First, encode the video part using helper
        self.from_image_generator(frame_generator=frame_generator, frame_rate=frame_rate, px_fmt=px_fmt)

        # If audio is provided, build an AudioFile and mux it using existing add_audio
        if audio_generator is not None:
            # Normalize audio chunks (support list or iterator of numpy arrays)
            audio_file = AudioFile().from_audio_generator(
                audio_generator, sample_rate=audio_sample_rate,
                output_format=audio_output_format,
                codec=audio_codec, array_layout="av"
            )
            self.add_audio(audio_file)
        
        return self

    def from_files(self, image_files: Union[List[str], list], frame_rate: int = 30, img_color_format: IMG_COLOR_FORMATS = "bgr24", audio_file=None):
        """
        Creates a video from a list of image files; optionally adds audio.
        """
        if not image_files:
            raise ValueError("The list of image files is empty.")

        def image_gen():
            for image_file in image_files:
                try:
                    yield self._image_to_ndarray(image_file, color_format=img_color_format)
                except Exception as e:
                    print(f"Error converting image file {image_file} to numpy array: {e}")
                    continue

        self.from_generators(SimpleGeneratorWrapper(image_gen, len(image_files)), frame_rate=frame_rate)
        
        if audio_file is not None:
            self.add_audio(audio_file)

        return self

    def from_image_files(self, image_files: List[str], frame_rate: int = 30, img_color_format: IMG_COLOR_FORMATS = "bgr24"):
        """Convenience method to create a video from images only."""
        return self.from_files(image_files, frame_rate, img_color_format=img_color_format, audio_file=None)

    def from_dir(self, dir_path: str, audio: Union[str, list] = None, frame_rate: int = 30):
        """Creates a video from a directory of images and an optional audio file."""
        image_types = ["*.png", "*.jpg", "*.jpeg", "*.bmp", "*.tiff"]
        image_files = []
        for image_type in image_types:
            image_files.extend(glob.glob(os.path.join(dir_path, image_type)))
        image_files.sort(key=lambda x: os.path.getmtime(x))

        if audio is None:
            audio_types = ["*.wav", "*.mp3"]
            for audio_type in audio_types:
                audio_candidate = glob.glob(os.path.join(dir_path, audio_type))
                if len(audio_candidate) > 0:
                    audio = audio_candidate[0]
                    break

        return self.from_files(image_files=image_files, frame_rate=frame_rate, audio_file=audio)

    def _to_temp_file(self):
        """Saves the in-memory content to a temporary file for PyAV processing."""
        if self.content_type is None:
            self.content_type = "video/mp4"
        
        suffix = self.content_type.split("/")[-1] if "/" in self.content_type else "mp4"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{suffix}") as temp_file:
            temp_file.write(self.read())
            temp_path = temp_file.name
        
        self._temp_file_path = temp_path
        return temp_path
    
    @requires('av', 'numpy')
    def extract_audio(self, path: str = None, export_type: str = 'mp3') -> Union[bytes, str]:
        """
        Extracts the audio from the video file and saves it to a file or returns as bytes.
        
        Args:
            path (str, optional): The path to save the audio file. If None, audio is returned as bytes.
            export_type (str, optional): The audio file format. Defaults to 'mp3'.
        
        Returns:
            Union[bytes, str]: The path to the audio file if path is provided, otherwise the audio data as bytes.
        """
        temp_file_path = None
        output_path = path

        if output_path is None:
            output_buffer = io.BytesIO()
            container_out_target = output_buffer
        else:
            container_out_target = output_path
            # Ensure the output directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

        try:
            temp_file_path = self._to_temp_file()
            container = av.open(temp_file_path)

            audio_stream = next((s for s in container.streams if s.type == 'audio'), None)
            if audio_stream is None:
                raise ValueError("No audio stream found in the video file.")
            
            output_container = av.open(container_out_target, 'w', format=export_type)
            output_stream = output_container.add_stream(export_type, rate=audio_stream.sample_rate)

            for frame in container.decode(audio_stream):
                for packet in output_stream.encode(frame):
                    output_container.mux(packet)
            
            # Flush the encoder
            for packet in output_stream.encode():
                output_container.mux(packet)

            output_container.close()
            container.close()

            if output_path is None:
                return output_buffer.getvalue()
            return output_path

        except Exception as e:
            if output_path and os.path.exists(output_path):
                self._safe_remove(output_path)
            raise RuntimeError(f"Failed to extract audio: {e}") from e
        finally:
            self._safe_remove(temp_file_path)
            
    @requires('av')
    def add_audio(self, audio_file: Union[str, AudioFile]):
        """
        Adds audio to the video file.
        :param audio_file: The audio file to add, as a path or an AudioFile object.
        """
        temp_video_path = None
        # Use .mp4 as the suffix is the most common format for combined video/audio
        temp_output_path = tempfile.mktemp(suffix=".mp4")
        
        audio_container_source = audio_file if isinstance(audio_file, str) else audio_file.to_bytes_io()

        try:
            temp_video_path = self._to_temp_file()
            
            with av.open(temp_video_path, 'r') as video_container, \
                 av.open(audio_container_source, 'r') as audio_container, \
                 av.open(temp_output_path, 'w') as output_container:
                
                # --- Stream Setup ---
                
                video_stream = next((s for s in video_container.streams if s.type == 'video'), None)
                input_audio_stream = next((s for s in audio_container.streams if s.type == 'audio'), None)

                if not video_stream:
                    raise ValueError("No video stream found in the video file.")
                if not input_audio_stream:
                    raise ValueError("No audio stream found in the audio file.")

                # Get video duration to trim audio
                video_duration = float(video_stream.duration * video_stream.time_base)

                # Video Stream: Copy properties, re-encode to 'libx264' for broad compatibility
                pix_fmt = 'yuv420p'  # Common for H.264
                codec = 'libx264'
                if hasattr(video_stream, 'codec_context') and hasattr(video_stream.codec_context, 'codec'):
                    codec = video_stream.codec_context.codec.name
              
                if hasattr(video_stream, 'pix_fmt'):
                    pix_fmt = video_stream.pix_fmt

                output_video_stream = output_container.add_stream(codec_name=codec, rate=video_stream.average_rate)
                output_video_stream.width = video_stream.width
                output_video_stream.height = video_stream.height
                output_video_stream.pix_fmt = pix_fmt
                
                # Audio Stream: Re-encode to 'aac'.
                audio_codec = 'aac'
                layout = 'stereo'  # Use stereo as a standard
                sample_rate = 44100
                if hasattr(input_audio_stream, 'codec_context'):
                    if hasattr(input_audio_stream.codec_context, 'channels'):
                        layout_map = {
                            1: 'mono',
                            2: 'stereo',
                            3: '2.1',
                            4: '3.1',
                            5: '4.1',
                            6: '5.1',
                            7: '6.1',
                            8: '7.1'
                        }
                        channels = input_audio_stream.codec_context.channels
                        layout = layout_map.get(channels, 'stereo')
                    if hasattr(input_audio_stream.codec_context, 'rate'):
                        sample_rate = input_audio_stream.codec_context.rate
                      
                output_audio_stream = output_container.add_stream(codec_name=audio_codec, rate=sample_rate, layout=layout)

                # Create an Audio Resampler
                resampler = av.AudioResampler(
                    format='fltp',  # Preferred float format for encoding
                    layout=layout,
                    rate=sample_rate
                )

                # --- Muxing & Transcoding ---

                # Transcode and Mux Video
                for frame in video_container.decode(video_stream):
                    for packet in output_video_stream.encode(frame):
                        output_container.mux(packet)
                
                # Transcode and Mux Audio (using the resampler)
                for frame in audio_container.decode(input_audio_stream):
                    # Check if audio frame is beyond video duration
                    if frame.pts * input_audio_stream.time_base > video_duration:
                        break
                    
                    # Resample the input frame
                    resampled_frames = resampler.resample(frame)
                    
                    if resampled_frames:
                        for resampled_frame in resampled_frames:
                            for packet in output_audio_stream.encode(resampled_frame):
                                output_container.mux(packet)

                # Flush the encoders
                # 1. Flush the video encoder
                for packet in output_video_stream.encode():
                    output_container.mux(packet)
                
                # 2. Flush the audio resampler: Pass None to retrieve buffered frames (Fix for older PyAV)
                for resampled_frame in resampler.resample(None):
                    for packet in output_audio_stream.encode(resampled_frame):
                        output_container.mux(packet)
                
                # 3. Flush the audio encoder
                for packet in output_audio_stream.encode():
                    output_container.mux(packet)

            # Update the VideoFile object with the new file
            self.from_file(temp_output_path)
            self._file_info()
            
        except Exception as e:
            # Clean up temporary file on failure
            print(e)
            self._safe_remove(temp_output_path)
            raise RuntimeError(f"Failed to add audio to video: {e}") from e
        finally:
            # Always clean up the temporary files
            self._safe_remove(temp_video_path)

    @requires('av')
    def to_stream(self) -> VideoStream:
        """
        Creates a VideoStream for easy frame-by-frame processing.
        
        Args:
            include_audio: Whether to include audio stream
            color_format: Color format for video frames ("rgb24" or "bgr24")
            
        Returns:
            VideoStream object for iterating over frames and audio
        """
        if self.file_size() == 0:
            raise ValueError("Empty video file")

        buf = io.BytesIO(self.read())
        return VideoStream(buf, self.video_info)
            
    @requires('av', 'numpy')
    def from_stream(
        self,
        stream: VideoStream,
    ) -> 'VideoFile':
        """
        Creates a new VideoFile from a VideoStream, re-encoding video and audio
        (as they are assumed modified) while reusing original codec parameters
        to maintain file size/quality as closely as possible.
        """
        if not isinstance(stream, VideoStream):
            raise ValueError("Stream must be a VideoStream object. Try from_generators() instead.")
        
        temp_file_path = tempfile.mktemp(suffix=".mp4")
        # Use 'mp4' format for compatibility, but the codecs will be preserved/reused
        container = av.open(temp_file_path, mode="w", format="mp4")
        
        video_info = stream.video_info
        if video_info is None:
            raise ValueError("VideoStream object must contain video_info")
        
        # --- VIDEO WRITER SETUP (Smart Re-encode) ---
        in_vstream = stream._video_stream

        rate = in_vstream.average_rate or video_info.frame_rate
        if isinstance(rate, float):
            rate = Fraction(rate).limit_denominator(10000)

        # 1. Video Codec Selection & Setup
        # Try to use the original codec if it's a standard encoding one (e.g., h264/h265)
        video_codec = in_vstream.codec_context.codec.name if in_vstream.codec_context.codec.name in ('libx264', 'h264', 'hevc', 'libx265') else 'libx264'
        
        v_writer = container.add_stream(video_codec, rate=rate)
        v_writer.width = in_vstream.width
        v_writer.height = in_vstream.height
        v_writer.pix_fmt = in_vstream.pix_fmt or 'yuv420p'
        
        # Set Bit Rate or CRF for size/quality control
        if in_vstream.bit_rate:
            v_writer.bit_rate = in_vstream.bit_rate
        else:
            v_writer.options['crf'] = '23'  # Standard default CRF for H.264/265
        if in_vstream.time_base is not None:
            v_writer.time_base = in_vstream.time_base
            
        # --- AUDIO WRITER SETUP (Smart Re-encode) ---
        
        a_writer = None
        if stream.has_audio and stream._audio_stream:
            in_astream = stream._audio_stream
            
            # 1. Audio Codec Selection & Setup: Prefer original or fallback to 'aac' for broad compatibility
            # Re-encode raw audio formats to 'aac'
            audio_codec = in_astream.codec_context.codec.name if in_astream.codec_context.codec.name not in ('pcm_s16le', 'raw') else 'aac'
            
            a_writer = container.add_stream(audio_codec, rate=in_astream.sample_rate, layout=in_astream.layout.name)
            
            # Apply known properties from the original stream
            if in_astream.bit_rate:
                a_writer.bit_rate = in_astream.bit_rate
            if in_astream.time_base is not None:
                a_writer.time_base = in_astream.time_base

        # --- MUXING ---

        # Process both video and audio in a single demux pass
        for packet in stream.container.demux():
            
            # 1. Video Re-encode (Assumed Modified)
            if packet.stream.type == 'video' and packet.stream == stream._video_stream:
                for frame in packet.decode():
                    for encoded_packet in v_writer.encode(frame):
                        container.mux(encoded_packet)
                        
            # 2. Audio Re-encode (Assumed Modified)
            elif a_writer and packet.stream.type == 'audio' and packet.stream == stream._audio_stream:
                for frame in packet.decode():
                    for encoded_packet in a_writer.encode(frame):
                        container.mux(encoded_packet)
        
        # Flush both encoders
        for packet in v_writer.encode():
            container.mux(packet)
        
        if a_writer:
            for packet in a_writer.encode():
                container.mux(packet)
        
        container.close()
        self.from_file(temp_file_path)
        self._safe_remove(temp_file_path)
        return self

    def __iter__(self):
        """Iterates over the video frames as numpy arrays (re-encoding)."""
        if self.file_size() == 0:
            raise ValueError("Empty video file")
        
        buf = io.BytesIO(self.read())
        container = av.open(buf)
        video_stream = next((s for s in container.streams if s.type == 'video'), None)
        if not video_stream:
            raise ValueError("No video stream found")
        
        def frame_gen():
            for frame in container.decode(video_stream):
                yield frame.to_ndarray(format='rgb24')
        
        return frame_gen()

    def __len__(self):
        return int(self.video_info.frame_count) if self.video_info and self.video_info.frame_count else 0
    
    def __del__(self):
        if self._temp_file_path is not None:
            self._safe_remove(self._temp_file_path, silent=False, message="Could not delete temporary file")
