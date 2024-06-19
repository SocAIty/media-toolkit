from io import BufferedReader, BytesIO
import os

from multimodal_files import MultiModalFile, ImageFile, AudioFile, VideoFile


def convert_to_upload_file_type(file, target_multimodal_file_type=None):
    """
    Converts a file to a send able format.
    :param file: The file to convert.
    :param target_multimodal_file_type: The target type to convert to. If not specified will be converted to MultiModalFile.
        Use ImageFile, AudioFile, VideoFile to convert to those types.
    :return: The send able file.
    """
    # it is already converted
    if isinstance(file, MultiModalFile):
        return file

    # determine target class
    target_class = MultiModalFile
    if target_multimodal_file_type is not None and issubclass(target_multimodal_file_type, MultiModalFile):
        target_class = target_multimodal_file_type
    multimodal_file_instance = target_class()

    # load from file cases
    if type(file) in [BufferedReader, BytesIO]:
        multimodal_file_instance.from_file(file)
    elif isinstance(file, str):
        if is_valid_file_path(file):
            multimodal_file_instance.from_file(open(file, 'rb'))
        else:
            multimodal_file_instance.from_base64(file)
    elif isinstance(file, bytes):
        multimodal_file_instance.from_bytes(file)
    elif type(file).__name__ == 'ndarray':
        multimodal_file_instance.from_np_array(file)
    elif file.__module__ == 'starlette.datastructures' and type(file).__name__ == 'UploadFile':
        multimodal_file_instance.from_starlette_upload_file(file)

    # convert the file
    return multimodal_file_instance


def from_file_result(file_result: dict):
    """
    Converts a file result to a MultiModalFile.
    :param file_result: The file result to convert.
    :return: The MultiModalFile.
    """
    content_type = file_result.get("content_type", None)
    if content_type is None:
        content = file_result.get('content', file_result)
        return convert_to_upload_file_type(content, MultiModalFile)

    # determine target class from file type
    content_type = content_type.lower()
    file_types = {
        "octet-stream": MultiModalFile,
        "image": ImageFile,
        "audio": AudioFile,
    }
    # fancy way to write efficient the factory conversion
    target_class = next(
        filter(lambda ft: ft[0] in content_type, file_types.items()),
        (None, MultiModalFile) # return tuple as default because next returns key, value
    )[1]

    return target_class().from_dict(file_result)


def is_valid_file_path(path: str):
    try:
        is_file = os.path.isfile(path)
        return is_file
    except:
        return False

