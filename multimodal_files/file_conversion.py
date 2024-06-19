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

    # load data
    multimodal_file_instance = multimodal_file_instance.from_any(file)
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
        return MultiModalFile().from_any(content)

    # determine target class from file type
    content_type = content_type.lower()
    file_types = {
        "octet-stream": MultiModalFile,
        "image": ImageFile,
        "audio": AudioFile,
        "video": VideoFile
    }
    # fancy way to write efficient the factory conversion
    target_class = next(
        filter(lambda ft: ft[0] in content_type, file_types.items()),
        (None, MultiModalFile) # return tuple as default because next returns key, value
    )[1]

    return target_class().from_dict(file_result)

