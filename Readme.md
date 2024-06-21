
  <h1 align="center" style="margin-top:-25px">Multimodal-files</h1>
<p align="center">
  <img align="center" src="docs/multimodal_file_icon.png" height="200" />
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
- etc.

Transmit files between services with a common interface
- Native FastSDK and FastTaskAPI integration
- Supports httpx, requests

Work with native python libs like BytesIO.

Only use the file types you need, no unnecessary dependencies.

## Installation

You can install the package with PIP, or clone the repository.

```bash
# install from pypi
pip install multimodal-files
# install without dependencies: this is useful if you only need the basic functionality
pip install multimodal-files --no-deps
# if you only want to use certain file types
pip install multimodal-files[ImageFile]  # or [AudioFile, VideoFile, ...]
# install from github for newest release
pip install git+git://github.com/SocAIty/multimodal-files
```
The version without dependencies does not include the optional dependencies like numpy, soundfile, etc. 
Instead, you can only install the dependencies which are required for your project. Making the package size tiny.

# Usage

## Create a multimodal-file from any data type
The library automatically detect the data type and loads it correctly.
```python
from multimodal_files import MultiModalFile, ImageFile, AudioFile, VideoFile

# represents either path, base64, bytesio, file_handle, numpy array ...
arbitrary_data = "...."
new_file = ImageFile().from_any(arbitrary_data)
```

All files ```(ImageFile, AudioFile, VideoFile)``` types support the same interface / methods.

#### Explicitly load from a certain type.
This method is more secure than from_any, because it definitely uses the correct method to load the file.
```python
new_file = MultiModalFile()

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

### Easy conversion from any type

```python
my_image_file = convert_to_upload_file_type(arbitrary_data, ImageFile) 
```


