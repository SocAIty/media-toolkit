
<h1 align="center">MediaToolkit</h1>
<p align="center">
  <img align="center" src="docs/media-file-icon.png" height="200" />
</p>
<h3 align="center">Ultra-Fast Python Media Processing • FFmpeg • OpenCV • PyAV</h3>

<p align="center">
  <strong>⚡ Lightning-fast • 🛠️ Simple API • 🔄 Any Format • 🌐 Web-ready • 🖥️ Cross-platform</strong>
</p>

---

**MediaToolkit** is a high-performance Python library for processing images, audio, and video with a unified, developer-friendly API. Built on FFmpeg (PyAV) and OpenCV for production-grade speed and reliability.

**Perfect for:** AI/ML pipelines, web services, batch processing, media automation, computer vision, and audio analysis.

## 📦 Installation

```bash
pip install media-toolkit
```

**Note:** Audio/video processing requires FFmpeg. [PyAV](https://github.com/PyAV-Org/PyAV) usually installs it automatically, but if needed, install manually from [ffmpeg.org](https://ffmpeg.org/).

## ⚡ Quick Start

**One API for all media types** - load from files, URLs, bytes, base64, or numpy arrays:

```python
from media_toolkit import ImageFile, AudioFile, VideoFile, media_from_any

# load any file and convert it to the correct format. This works with smart content detection
audio = media_from_any("media/my_favorite_song.mp3") # -> AudioFile

# Load from any source
image = ImageFile().from_any("https://example.com/image.jpg")
audio = AudioFile().from_file("audio.wav")
video = VideoFile().from_file("video.mp4")
imb = ImageFile().from_base64("data:image/png;base64,...")
# Convert to any format
image_array = image.to_np_array()      # → numpy array (H, W, C)
audio_array = audio.to_np_array()      # → numpy array (samples, channels)
image_base64 = image.to_base64()       # → base64 string
video_bytes = video.to_bytes_io()      # → BytesIO object
```

### Batch Processing

```python
from media_toolkit import MediaList, AudioFile

# Process multiple files efficiently
audio_files = MediaList([
    "song1.wav",
    "https://example.com/song2.mp3",
    b"raw_audio_bytes..."
])

for audio in audio_files:
    audio.save(f"converted_{audio.file_name}.mp3")  # Auto-convert on save
```

## 🖼️ Image Processing

**OpenCV-powered image operations:**

```python
from media_toolkit import ImageFile
import cv2

# Load and process
img = ImageFile().from_any("image.png")
image_array = img.to_np_array()  # → (H, W, C) uint8 array

# Apply transformations
flipped = cv2.flip(image_array, 0)

# Save processed image
ImageFile().from_np_array(flipped).save("flipped.jpg")
```

## 🎵 Audio Processing

**FFmpeg/PyAV-powered audio operations:**

```python
from media_toolkit import AudioFile

# Load audio
audio = AudioFile().from_file("input.wav")

# Get numpy array for ML/analysis
audio_array = audio.to_np_array()  # → (samples, channels) float32 in [-1, 1] range

# Inspect metadata
print(f"Sample rate: {audio.sample_rate} Hz; Channels: {audio.channels}; Duration: {audio.duration}")

# Format conversion (automatic re-encoding)
audio.save("output.mp3")   # MP3
audio.save("output.flac")  # FLAC (lossless)
audio.save("output.m4a")   # AAC

# Create audio from numpy
new_audio = AudioFile().from_np_array(
    audio_array,
    sample_rate=audio.sample_rate,
    audio_format="wav"
)
```

**Supported formats:** WAV, MP3, FLAC, AAC, M4A, OGG, Opus, WMA, AIFF

## 🎬 Video Processing

**High-performance video operations:**

```python
from media_toolkit import VideoFile
import cv2

video = VideoFile().from_file("input.mp4")

# Extract audio track
audio = video.extract_audio("audio.mp3")

# Process frames
for i, frame in enumerate(video.to_stream()):
    if i >= 300:  # First 300 frames
        break
    # frame is numpy array (H, W, C)
    processed = my_processing_function(frame)
    cv2.imwrite(f"frame_{i:04d}.png", processed)

# Create video from images
images = [f"frame_{i:04d}.png" for i in range(300)]
modifiedVid = VideoFile().from_files(images, frame_rate=30, audio_file="audio.mp3")

```

## 🌐 Web & API Integration

### Native [APIPod](https://github.com/SocAIty/APIPod) Support

Built-in integration with APIPod for simplified file handling:

```python
from apipod import APIPod, ImageFile, VideoFile

app = APIPod()

@app.endpoint("/process")
def process_media(image: ImageFile, video: VideoFile) -> VideoFile:
    # Automatic type conversion, validation
    modified_video = my_ai_inference(image, video)
    # any media can be returned automatically
    return modified_video
```


### FastAPI Integration

```python
from fastapi import FastAPI, UploadFile, File
from media_toolkit import ImageFile

app = FastAPI()

@app.post("/process-image")
async def process_image(file: UploadFile = File(...)):
    image = ImageFile().from_any(file)
```

### HTTP Client Usage

```python
import httpx
from media_toolkit import ImageFile

image = ImageFile().from_file("photo.jpg")

# Send to API
files = {"file": image.to_httpx_send_able_tuple()}
response = httpx.post("https://api.example.com/upload", files=files)
```


## 📋 Advanced Features

### Container Classes

**MediaList** - Type-safe batch processing:
```python
from media_toolkit import MediaList, ImageFile

images = MediaList[ImageFile]()
images.extend(["img1.jpg", "img2.png", "https://example.com/img3.jpg"])

# Lazy loading - files loaded on access
for img in images:
    img.save(f"processed_{img.file_name}")
```

**MediaDict** - Key-value media storage:
```python
from media_toolkit import MediaDict, ImageFile

media_db = MediaDict()
media_db["profile"] = "profile.jpg"
media_db["banner"] = "https://example.com/banner.png"

# Export to JSON
json_data = media_db.to_json()
```

### Streaming for Large Files

```python
# Memory-efficient processing
audio = AudioFile().from_file("large_audio.wav")
for chunk in audio.to_stream():
    process_chunk(chunk)  # Process in chunks

video = VideoFile().from_file("large_video.mp4")
stream = video.to_stream()
for frame in stream:
    process_frame(frame)  # Frame-by-frame processing

# video-to-audio-stream
for av_frame in stream.audio_frames():
    pass

```

## 🚀 Performance

MediaToolkit leverages industry-standard libraries for maximum performance:

- **FFmpeg (PyAV)**: Professional-grade audio/video codec support
- **OpenCV**: Optimized computer vision operations
- **Streaming**: Memory-efficient processing of large files
- **Hardware acceleration**: GPU support where available

**Benchmarks:**
- Audio conversion: ~100x faster than librosa/pydub
- Image processing: Near-native OpenCV speed
- Video processing: Hardware-accelerated encoding/decoding. FPS > 500 for video decoding on consumer grade hardware.

## 🔧 Key Features

✅ **Universal input**: Files, URLs, bytes, base64, numpy arrays, bytesio, starlette upload files, soundfile  
✅ **Automatic format detection**: Smart content-type inference  
✅ **Seamless conversion**: Change formats on save  
✅ **Type-safe**: Full typing support with generics  
✅ **Web-ready**: Native APIPod integration, extra features for httpx and fastapi  
✅ **Production-tested**: Used in production AI/ML pipelines

## 📋 Format Support Overview

| Category | Formats | Integration | Class | Description |
|----------|---------|-------------|-------|-------------|
| **Images** | `jpg`, `jpeg`, `png`, `gif`, `bmp`, `tiff`, `tif`, `jfif`, `ico`, `webp`, `avif`, `heic`, `heif`, `svg` | Deep | `ImageFile` | OpenCV-powered processing, format conversion, channel detection and more. |
| **Audio** | `wav`, `mp3`, `ogg`, `flac`, `aac`, `m4a`, `wma`, `opus`, `aiff` | Deep | `AudioFile` | FFmpeg/PyAV-powered, format conversions, sample rate conversion, streaming, metadata extraction. |
| **Video** | `mp4`, `avi`, `mov`, `mkv`, `webm`, `flv`, `wmv`, `3gp`, `ogv`, `m4v` | Deep | `VideoFile` | Hardware-accelerated encoding/decoding, frame extraction, audio extraction. |
| **3D Models** | `obj`, `glb`, `gltf`, `dae`, `fbx`, `3ds`, `ply`, `stl`, `step`, `iges`, `x3d`, `blend` | Shallow | `MediaFile` | Basic file handling, no specialized 3D processing yet. |
| **Documents** | `pdf`, `txt`, `html`, `htm`, `json`, `js`, `css`, `xml`, `csv` | Shallow | `MediaFile` | Text and document formats, basic file operations |
| **Archives** | `zip`, `7z`, `tar`, `gz` | Shallow | `MediaFile` | Archive and compressed file formats. Basic file operations. |
| **Data** | `npy`, `npz`, `pkl`, `pickle` | Shallow | `MediaFile` | Python data serialization formats. Basic file operations. |

**Deep Integration**: Specialized classes with advanced processing capabilities, format conversion, and media-specific operations.

**Shallow Integration**: Basic `MediaFile` class with universal file operations, automatic format detection, and standard conversions.

## 🤝 Contributing

We welcome contributions! Key areas:
- Performance optimizations
- New format support
- Documentation & examples
- Test coverage
- Platform-specific enhancements

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---
Join the intelligence revolution. Join [socaity.ai](https://www.socaity.ai)


