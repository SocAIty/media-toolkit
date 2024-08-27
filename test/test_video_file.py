"""
Tests some core functionalities of the VideoFile class.
"""
from tqdm import tqdm

from media_toolkit import VideoFile, ImageFile
import cv2

outdir = "outdir/"

def test_video_file():
    test_video = "test_files/test_video.mp4"
    vf = VideoFile().from_file(test_video)
    # extract audio_file
    vf.extract_audio(f"{outdir}/extracted_audio.mp3")
    audio_bytes = vf.extract_audio()

def test_video_from_files():
    files = [f"{outdir}/test_out_video_stream_{i}.png" for i in range(10)]
    vf = VideoFile().from_files(files)
    vf.add_audio(f"{outdir}/extracted_audio.mp3")
    vf.save(f"{outdir}/test_from_files_add_audio.mp4")
    # from dir; and combine audio and video
    fromdir = VideoFile().from_dir(outdir, audio=f"{outdir}/extracted_audio.mp3", frame_rate=30)
    fromdir.save(f"{outdir}/test_from_dir.mp4")

def test_video_stream():
    audio_array = []
    image_paths = []
    for i, (img, audio_part) in tqdm(enumerate(vf.to_video_stream(include_audio=True))):
        p = f"{outdir}/test_out_video_stream_{i}.png"
        image_paths.append(p)
        cv2.imwrite(p, img)
        audio_array.append(audio_part)

    # test video clients with audio_file
    fromstream = VideoFile().from_video_stream(fromdir.to_video_stream(include_audio=True))
    fromstream.save(f"{outdir}/test_from_stream.mp4")

