from io import BufferedReader, BytesIO
import os

from multimodal_files import UploadFile


def convert_to_upload_file_type(file, target_type=None):
    """
    Converts a file to a send able format.
    :param file: The file to convert.
    :param target_type: The target type to convert to. If not specified will be converted to UploadFile.
        Use ImageFile, AudioFile, VideoFile to convert to those types.
    :return: The send able file.
    """
    # it is already converted
    if isinstance(file, UploadFile):
        return file

    target_class = UploadFile
    if target_type is not None and issubclass(target_type, UploadFile):
        target_class = target_type

    upload_file_instance = target_class()
    # load from file cases
    if type(file) in [BufferedReader, BytesIO]:
        upload_file_instance.from_file(file)
    elif isinstance(file, str):
        if is_valid_file_path(file):
            upload_file_instance.from_file(open(file, 'rb'))
        else:
            upload_file_instance.from_base64(file)
    elif isinstance(file, bytes):
        upload_file_instance.from_bytes(file)
    elif type(file).__name__ == 'ndarray':
        upload_file_instance.from_np_array(file)
    elif file.__module__ == 'starlette.datastructures' and type(file).__name__ == 'UploadFile':
        upload_file_instance.from_starlette_upload_file(file)

    # convert the file
    return upload_file_instance


def is_valid_file_path(path: str):
    try:
        is_file = os.path.isfile(path)
        return is_file
    except:
        return False

