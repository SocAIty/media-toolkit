from media_toolkit import MediaFile, ImageFile, AudioFile, VideoFile


def convert_to_upload_file_type(file, target_media_file=None):
    """
    Converts a file to a send able format.
    :param file: The file to convert.
    :param target_media_file: The target type to convert to. If not specified will be converted to MediaFile.
        Use ImageFile, AudioFile, VideoFile to convert to those types.
    :return: The send able file.
    """
    # it is already converted
    if isinstance(file, MediaFile):
        return file

    # determine target class
    target_class = MediaFile
    if target_media_file is not None and issubclass(target_media_file, MediaFile):
        target_class = target_media_file
    media_file_instance = target_class()

    # load data
    media_file_instance = media_file_instance.from_any(file)
    return media_file_instance


def from_file_result(file_result: dict):
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

