"""
Tests some core functionalities of the VideoFile class.
"""
from tqdm import tqdm

from media_toolkit import VideoFile
import cv2

outdir = "outdir/"

# test video files
test_video = "test_files/test_video.mp4"
vf = VideoFile().from_file(test_video)
### extract audio_file
#vf.extract_audio(f"{outdir}/extracted_audio.mp3")
#audio_bytes = vf.extract_audio()

## test video streaming
audio_array = []
image_paths = []
for i, (img, audio_part) in tqdm(enumerate(vf.to_video_stream(include_audio=True))):
    p = f"{outdir}/test_out_video_stream_{i}.png"
    image_paths.append(p)
    cv2.imwrite(p, img)
    audio_array.append(audio_part)

# new video File
vf = VideoFile().from_files(image_paths)
vf.add_audio(audio_array)
vf.save(f"{outdir}/test_from_files_add_audio.mp4")
# from dir; and combine audio and video
fromdir = VideoFile().from_dir(outdir, audio=f"{outdir}/extracted_audio.mp3", frame_rate=30)
fromdir.save(f"{outdir}/test_from_dir.mp4")

# test video streaming with audio_file
fromstream = VideoFile().from_video_stream(vf.to_video_stream(include_audio=True))
fromstream.save(f"{outdir}/test_from_stream.mp4")