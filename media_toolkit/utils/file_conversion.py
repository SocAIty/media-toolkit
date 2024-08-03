import os.path
from typing import Union
import mimetypes
from media_toolkit import MediaFile, ImageFile, AudioFile, VideoFile


def guess_file_type(file_path: str) -> str:
    """
    Guesses the type of the file based on the file extension.
    :param file_path: The file path to guess the type of.
    :return: The guessed file type.
    """
    if not file_path or not isinstance(file_path, str):
        raise ValueError(f"file_path {file_path} be a string")
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        raise FileNotFoundError(f"file_path does not exist or is not a file: {file_path}")

    type_guess = mimetypes.guess_type(file_path)
    return type_guess[0]


def media_from_file(file_path: str) -> Union[MediaFile, ImageFile, AudioFile, VideoFile]:
    """
    Guesses the type of the file based on the file extension and returns fitting media-file instance.
    :param file_path: The file path to guess the type of.
    :return: An instance of a media-file either, image, audio or video.
    """
    type_guess = guess_file_type(file_path)

    if type_guess.startswith('image'):
        return ImageFile().from_file(file_path)
    if type_guess.startswith('audio'):
        return AudioFile().from_file(file_path)
    if type_guess.startswith('video'):
        return VideoFile().from_file(file_path)

    return MediaFile().from_file(file_path)


def media_from_any(file, media_file_type=None):
    """
    Converts a file to a send able format.
    :param file: The file to convert.
    :param media_file_type: The target type to convert to. If not specified will be converted to MediaFile.
        Use ImageFile, AudioFile, VideoFile to convert to those types.
    :return: The send able file.
    """
    # it is already converted
    if isinstance(file, MediaFile):
        return file

    # determine target class
    target_class = MediaFile
    if media_file_type is not None and issubclass(media_file_type, MediaFile):
        target_class = media_file_type
    media_file_instance = target_class()

    # load data
    media_file_instance = media_file_instance.from_any(file)
    return media_file_instance


def media_from_file_result(file_result: dict):
    """
    Converts a file result to a MediaFile.
    :param file_result: The file result to convert.
    :return: The MediaFile.
    """
    content_type = file_result.get("content_type", None)
    if content_type is None:
        content = file_result.get('content', file_result)
        return MediaFile().from_any(content)

    # determine target class from file type
    content_type = content_type.lower()
    file_types = {
        "octet-stream": MediaFile,
        "image": ImageFile,
        "audio_file": AudioFile,
        "video": VideoFile
    }
    # fancy way to write efficient the factory conversion
    target_class = next(
        filter(lambda ft: ft[0] in content_type, file_types.items()),
        (None, MediaFile) # return tuple as default because next returns key, value
    )[1]

    return target_class().from_dict(file_result)

