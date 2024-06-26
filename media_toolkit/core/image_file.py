from media_toolkit.dependency_requirements import requires_numpy, requires_cv2, requires
from media_toolkit.core.media_file import MediaFile

try:
    import cv2
    import numpy as np
except ImportError:
    pass


class ImageFile(MediaFile):
    """
    Has file conversions that make it easy to work with image files across the web.
    Internally it uses cv2 file format.
    """
    @requires('cv2', 'numpy')
    def from_np_array(self, np_array, img_type: str = None):
        if isinstance(np_array, list):
            np_array = np.array(np_array)

        if img_type is None:
            if "image/" not in self.content_type:
                img_type, self._channels = self.detect_image_type_and_channels(np_array)
            else:
                img_type = self.content_type.split("/")[1]
            self.content_type = f"image/{img_type}"

        is_success, buffer = cv2.imencode(f".{img_type}", np_array)
        if is_success:
            # avoid to check again for image type by calling super().from_bytes instead of self.from_bytes
            return super().from_bytes(buffer)
        else:
            raise ValueError(f"Could not convert np_array to {img_type} image")


    @requires('numpy', 'cv2')
    def to_np_array(self):
        bytes = self.to_bytes()
        return cv2.imdecode(np.frombuffer(bytes, np.uint8), -1)

    @requires_numpy()
    def to_cv2_img(self):
        return self.to_np_array()

    @requires_cv2()
    def save(self, path: str):
        cv2.imwrite(path, self.to_np_array())

    def _file_info(self):
        super()._file_info()
        np_array = self.to_np_array()
        img_type, self._channels = self.detect_image_type_and_channels(np_array)
        if img_type is not None:
            self.content_type = f"image/{img_type}"
        

    @staticmethod
    def detect_image_type_and_channels(image) -> (str, int):
        """Detect the image type and number of _channels from a numpy array."""
        if isinstance(image, list):
            image = np.array(image)

        # Check the number of _channels
        if len(image.shape) == 2:
            channels = 1  # Grayscale
        elif len(image.shape) == 3:
            channels = image.shape[2]
        else:
            #raise ValueError("Unsupported image shape: {}".format(image.shape))
            return None, None

        # Detect image type by checking for specific markers
        image_type = None

        # Convert to bytes and inspect file signatures for format detection
        success, encoded_image = cv2.imencode('.png', image)
        if success:
            encoded_bytes = encoded_image.tobytes()
            if encoded_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                image_type = 'png'
            elif encoded_bytes[0:2] == b'\xff\xd8':
                image_type = 'jpeg'
            elif encoded_bytes.startswith(b'BM'):
                image_type = 'bmp'
            elif encoded_bytes.startswith(b'GIF'):
                image_type = 'gif'

        return image_type, channels

