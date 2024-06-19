# Multimodal-files

Read, load and convert to standard file types with a common interface.
Especially useful for code that works with multiple file types like images, audio, video, etc.

## Features

Load and convert from and to common data types:
- numpy arrays 
- file paths 
- bytes,
- base64
- json
- etc.

Transmit files between services with a common interface
- Native socaity-client and socaity-router integration
- Supports httpx, requests

Work with native python libs like BytesIO.

Only use the file types you need, no unnecessary dependencies.

# Usage

### From file or arbitrary data

All files types support the same interface / methods.

```python
from multimodal_files import ImageFile, AudioFile, VideoFile

MultiModalFile().from_file("path/to/file")
MultiModalFile().from_file(open("path/to/file", "rb"))
MultiModalFile().from_numpy_array(my_array)
MultiModalFile().from_bytes(b'bytes')
MultiModalFile().from_base64('base64string')
MultiModalFile().from_starlette_upload_file(starlette_upload_file)

```

### To file or arbitrary data
Supports common serialization methods like bytes(), np.array(), dict()

```python
my_file = MultiModalFile().from_file("path/to/file")

my_file.save("path/to/new_file")  
as_numpy_array = my_file().to_numpy_array()
as_numpy_array = np.array(my_file)

as_bytes = MultiModalFile().to_bytes()
as_bytes = bytes(my_file)
as_base64 = MultiModalFile().to_base64()
as_json = MultiModalFile().to_json()
```

### Easy conversion from any type

```python
my_image_file = convert_to_upload_file_type(arbitrary_data, ImageFile) 
```


## Installation

You can install the package with PIP, or clone the repository.

Coming soon: install from pypi.

```python
pip install multimodal-files
```

Install the package with pip from the github repository.

```python
pip install git+git://github.com/SocAIty/multimodal-files
```
