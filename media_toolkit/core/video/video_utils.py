import tempfile
import tqdm
from fractions import Fraction

from media_toolkit.utils.dependency_requirements import requires
import subprocess
import os


try:
    from pydub import AudioSegment
    from pydub.utils import mediainfo
except ImportError:
    pass

try:
    import numpy as np
except ImportError:
    pass

try:
    import av
except ImportError:
    pass

try:
    import cv2
except ImportError:
    pass

 
@requires('pydub', 'numpy')
def add_audio_to_video_file(
        video_file: str,
        audio_file: str,
        save_path: str = None
):
    """
    Adds audio_file to a video file and saves it it to save_path. If save_path is None, a tempfile is created.
    :return: The path to the video file.
    """
    # convert to abs file paths
    video_file = os.path.abspath(video_file)
    audio_file = os.path.abspath(audio_file)
    if save_path is None:
        save_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    if save_path == video_file:
        save_path = save_path.replace(".mp4", "_with_audio.mp4")

    try:
        # https://stackoverflow.com/questions/11779490/how-to-add-a-new-audio-not-mixing-into-a-video-using-ffmpeg
        # os.system(f"ffmpeg -i {video_file} -i {audio_file} -map 0:v -map 1:a -c:v copy -shortest {save_path}.mp4")
        p = subprocess.Popen((
            "ffmpeg",
            "-y", "-i", video_file, "-i", audio_file, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
            "-shortest", save_path
        ))
        p.wait()
    except Exception as e:
        print(f"Error adding audio_file to video: {e}", e.__traceback__)

    return save_path


@requires('pydub', 'numpy')
def audio_array_to_audio_file(audio_array, sample_rate: int = 44100, save_path: str = None, audio_format: str = "mp3") -> str:
    """
    Saves an audio array to an audio file.
    :param audio_array: A numpy array containing the audio samples.
        Can be 1D or 2D (stereo). In form np.array([[array_frame_1], [array_frame_2], ..])
    """
    # audio_array in fom numpy to audio_file file saved in temporary file
    audio_array = np.array(audio_array, dtype=np.int16)
    # remove faulty channels
    channels = 2 if audio_array.ndim == 2 else 1
    song = AudioSegment(
        audio_array.tobytes(),
        frame_rate=sample_rate,
        sample_width=audio_array.dtype.itemsize,
        channels=channels
    )
    if save_path is None:
        temp_audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{audio_format}")
        save_path = temp_audio_file.name
    song.export(save_path, format=audio_format)
    return save_path


@requires('pydub')
def get_audio_sample_rate_from_file(file_path: str) -> int:
    info = mediainfo(file_path)
    if "sample_rate" not in info:
        raise ValueError("The audio file does not have a sample rate.")

    return int(info['sample_rate'])


@requires('numpy', 'av', 'cv2')
def video_from_image_generator(
        image_generator,
        save_path: str = None,
        frame_rate: int = 30,
        ffmpeg_params: dict = None
):
    """
    Creates a video from an image generator using PyAV.
    The image generator should yield images as numpy arrays (BGR) or filepaths.
    Returns a path to a tempfile if save_path is None, otherwise saves the video to the save_path.
    """
    # Create temp file if none provided
    if save_path is None:
        tempf = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        save_path = tempf.name

    # Wrap in tqdm if possible
    if hasattr(image_generator, "__len__"):
        image_generator = tqdm.tqdm(enumerate(image_generator), total=len(image_generator))
    else:
        image_generator = tqdm.tqdm(enumerate(image_generator))

    # Default ffmpeg parameters
    ffmpeg_params = ffmpeg_params or {}
    # Pick codec and pix_fmt from params (fall back to defaults)
    codec = ffmpeg_params.get("-vcodec", "libx264")
    pix_fmt = ffmpeg_params.get("-pix_fmt", "yuv420p")

    container = None
    stream = None
    width, height = None, None

    try:
        # Open output container
        container = av.open(save_path, mode="w")

        for i, img in image_generator:
            try:
                # Load from path if needed
                if isinstance(img, str):
                    img = cv2.imread(img)
                if not isinstance(img, np.ndarray):
                    raise ValueError("Image generator must yield numpy arrays or file paths.")

                if width is None or height is None:
                    height, width = img.shape[:2]

                # Add video stream once we know frame size
                # Ensure the encoding stream exists (attempt each iteration until it succeeds)
                if stream is None and width is not None and height is not None:
                    stream = container.add_stream(codec, rate=Fraction(frame_rate).limit_denominator())
                    # Add video stream once we know frame size
                    stream.width = width
                    stream.height = height
                    stream.pix_fmt = pix_fmt
                
                if stream is None:
                    raise RuntimeError("Video stream not initialized; skipping frame until stream is created.")

                # Convert BGR → RGB (PyAV expects RGB24 for ndarray import)
                frame = av.VideoFrame.from_ndarray(img[:, :, ::-1], format="rgb24")

                # Encode and mux
                for packet in stream.encode(frame):
                    container.mux(packet)

            except Exception as e:
                file_name = img if isinstance(img, str) else f"image_{i}"
                print(f"Error reading {file_name}: {e}. Skipping frame {i}")
                continue

        # Flush encoder
        if stream is not None:
            for packet in stream.encode():
                container.mux(packet)
        else:
            print("Warning: No valid frames were processed. Video file may be empty or corrupted.")

    except Exception as e:
        print(f"Error writing video: {e}")
    finally:
        if container is not None:
            container.close()

    return save_path
