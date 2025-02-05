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


def media_from_any(file, media_file_type=None, use_temp_file: bool = False, temp_dir: str = None) -> MediaFile:
    """
    Converts a file to a send able format.
    :param file: The file to convert.
    :param media_file_type: The target type to convert to. If not specified will be converted to MediaFile.
        Use ImageFile, AudioFile, VideoFile to convert to those types.
    :param use_temp_file: If True, a temporary file will be used to store the data within the media-file.
        If not stored in RAM.
    :param temp_dir: The directory to store the temporary file in. If not specified, the default temp directory will be used.
    :return: The send able file.
    """
    # it is already converted
    if isinstance(file, MediaFile):
        return file

    # determine target class
    target_class = MediaFile
    if media_file_type is not None and issubclass(media_file_type, MediaFile):
        target_class = media_file_type
    media_file_instance = target_class(use_temp_file=use_temp_file, temp_dir=temp_dir)

    # load data
    media_file_instance = media_file_instance.from_any(file)
    return media_file_instance


def media_from_file_result(file_result: dict, allow_reads_from_disk: bool = False) -> MediaFile:
    """
    Converts a file result to a MediaFile. FileResult contains "content_type", "content" and "file_name".
    This type stems usually from a FastTaskAPI JobResult.
    :param file_result: The file result to convert.
    :param allow_reads_from_disk: If True, the file will be read from disk if the content is a file path.
        This is in most cases not recommended, because it can be a security risk.
    :return: The MediaFile.
    """
    content_type = file_result.get("content_type", None)
    target_class = MediaFile
    if content_type is not None and isinstance(content_type, str):
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

    content = file_result.get('content', file_result)
    # make sure that file_result is not a file path of system to avoid security issues
    if not allow_reads_from_disk and MediaFile._is_valid_file_path(content):
        raise ValueError("Reading files from disk is not allowed. This can be a security risk.")

    return target_class().from_dict(file_result)

