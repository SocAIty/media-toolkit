
  <h1 align="center" style="margin-top:-25px">MediaToolkit</h1>
<p align="center">
  <img align="center" src="docs/media-file-icon.png" height="200" />
</p>
  <h3 align="center" style="margin-top:-10px">Web-ready standardized file processing and serialization</h3>


# Features

Read, load and convert to standard file types with a common interface.
Especially useful for code that works with multiple file types like images, audio, video, etc.

Load and convert from and to common data types:
- numpy arrays 
- file paths 
- bytes,
- base64
- json
- urls
- etc.

Transmit files between services with a common interface
- Native [FastSDK](https://github.com/SocAIty/fastSDK) and [FastTaskAPI](https://github.com/SocAIty/FastTaskAPI) integration
- Supports httpx, requests

Work with native python libs like BytesIO.

Only use the file types you need, no unnecessary dependencies.

## Installation

You can install the package with PIP, or clone the repository. 

```bash
# install from pypi
pip install media-toolkit
# install without dependencies: this is useful if you only need the basic functionality (working with files)
pip install media-toolkit --no-deps
# if you want to use certain file types, and convenience functions
pip install media-toolkit[VideoFile]  # or [AudioFile, VideoFile, ...]
# install from github for newest release
pip install git+git://github.com/SocAIty/media-toolkit
```
The package checks if you have missing dependencies for certain file types while using. 
Use the ```--no-deps``` flag for a minimal tiny pure python installation.
The package with dependencies is quite small < 39kb itself.

Note: for VideoFile you will also need to install [ffmpeg](https://ffmpeg.org/download.html)

# Usage

## Create a media-file from any data type
The library automatically detects the data type and loads it correctly.

```python
from media_toolkit import MediaFile, ImageFile, AudioFile, VideoFile

# could be a path, url, base64, bytesio, file_handle, numpy array ...
arbitrary_data = "...."
# Instantiate an image file
new_file = ImageFile().from_any(arbitrary_data)
```

All files ```(ImageFile, AudioFile, VideoFile)``` types support the same interface / methods.

#### Explicitly load from a certain type.
This method is more secure than from_any, because it definitely uses the correct method to load the file.
```python
new_file = MediaFile()

new_file.from_file("path/to/file")
new_file.from_file(open("path/to/file", "rb"))
new_file.from_numpy_array(my_array)
new_file.from_bytes(b'bytes')
new_file.from_base64('base64string')
new_file.from_starlette_upload_file(starlette_upload_file)

```

## Convert to any format or write to file
Supports common serialization methods like bytes(), np.array(), dict()

```python
my_file = ImageFile().from_file("path/to/my_image.png")

my_file.save("path/to/new_file.png")  
as_numpy_array = my_file.to_numpy_array()
as_numpy_array = np.array(my_file)

as_bytes = my_file.to_bytes()
as_bytes = bytes(my_file)
as_base64 = my_file.to_base64()
as_json = my_file.to_json()
```

### Working with VideoFiles.

The VideoFiles wrap the famous [vidgear](https://abhitronix.github.io/vidgear/latest/) package as well as [pydub](https://github.com/jiaaro/pydub).
VideoFiles support extra methods like audio extraction, combining video and audio.
Vidgear is a powerful video processing library that supports many video formats and codecs and is known for fast video processing.

```python
# load the video file
vf = VideoFile().from_file("test_files/test_vid_1.mp4")

# extract audio_file
vf.extract_audio("extracted_audio.mp3")

# stream the video
for img, audio in vf.to_video_stream(include_audio=True):
    cv2.imwrite("outtest.png", img)

# add audio to an videofile (supports files and numpy.array)
vf.add_audio("path/to/audio.mp3")

# create a video from a folder
VideoFile().from_dir("path/to/image_folder", audio=f"extracted_audio.mp3", frame_rate=30)

# create a video from a video stream
fromstream = VideoFile().from_video_stream(vf.to_video_stream(include_audio=True))
```

## Web-features

We intent to make transmitting files between services as easy as possible.
Here are some examples for services and clients.

### FastTaskAPI - Services
The library supports the FastTaskAPI and FastSDK for easy file transmission between services.
Simply use the files in the task_endpoint function definition and transmitted data will be converted.
Check out the [FastTaskAPI]() documentation for more information.
```python
from fast_task_api import ImageFile, AudioFile, VideoFile

@app.task_endpoint("/my_file_upload")
def my_upload_image(image: ImageFile, audio: AudioFile, video: VideoFile):
    image_as_np_array = np.array(image)
```

### fastAPI - services
You can use the files in fastapi and transform the starlette upload file to a MediaFile.
```python
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    mf = ImageFile().from_starlette_upload_file(file)
    return {"filename": file.filename}
```

### Client with: requests, httpx
To send a MediaFile to an openapi endpoint you can use the following method:

```python
import httpx

my_media_file = ImageFile().from_file("path/to/my_image.png")
my_files = {
  "param_name": my_media_file.to_httpx_send_able_tuple()
  ...
}
response = httpx.Client().post(url, files=my_files)
```


# How it works

If media-file is instantiated with ```from_*``` it converts it to an intermediate representation.
The ```to_*``` methods then convert it to the desired format.

Currently the intermediate representation is supported in memory with (BytesIO).


# ToDo:

- [x] additionally support tempfile backend instead of working bytesio memory mode only.
- [x] decreasing redundancies for _file_info() method