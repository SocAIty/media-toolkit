import os.path
from typing import Tuple
from media_toolkit.utils.dependency_requirements import requires_numpy, requires_cv2, requires
from media_toolkit.core.media_file import MediaFile
from media_toolkit.utils.media_type_guesser import guess_content_type, MediaTypeGuesser

try:
    import cv2
    import numpy as np
except ImportError:
    pass


class ImageFile(MediaFile):
    """
    Specialized media file for image processing with advanced computer vision capabilities.
    
    Features:
    - Native OpenCV integration for image processing
    - Automatic format detection and optimization
    - Support for various image formats (PNG, JPEG, GIF, BMP, TIFF, SVG)
    - Channel detection and image metadata extraction
    - High-performance numpy array conversions
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content_type = "image/jpeg"  # Default image type
        self._channels = None  # Image channel count cache
        self._image_format = None  # Detected image format cache

    @requires('cv2', 'numpy')
    def from_np_array(self, np_array, img_type: str = None):
        """
        Create ImageFile from numpy array with automatic format detection.
        
        Args:
            np_array: Input numpy array or list
            img_type: Target image format (auto-detected if None)
            
        Returns:
            Self for method chaining
        """
        if isinstance(np_array, list):
            np_array = np.array(np_array)

        # Auto-detect image type if not specified
        if img_type is None:
            if "image/" not in self.content_type:
                img_type, self._channels = self.detect_image_type_and_channels(np_array)
            else:
                img_type = self.content_type.split("/")[1]
            self.content_type = f"image/{img_type}"

        # Encode array to image bytes
        is_success, buffer = cv2.imencode(f".{img_type}", np_array)
        if is_success:
            # Call UniversalFile.from_bytes directly to avoid duplicate _file_info calls
            super(MediaFile, self).from_bytes(buffer.tobytes())
            self._file_info()
            return self
        else:
            raise ValueError(f"Could not convert numpy array to {img_type} image")

    @requires('numpy', 'cv2')
    def to_np_array(self):
        """
        Convert image to numpy array using OpenCV.
        
        Returns:
            Numpy array representation of the image
        """
        bytes_data = self.to_bytes()
        return cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_UNCHANGED)

    @requires_numpy()
    def to_cv2_img(self):
        """
        Alias for to_np_array() for OpenCV compatibility.
        
        Returns:
            Numpy array representation of the image
        """
        return self.to_np_array()

    @requires_cv2()
    def save(self, path: str = None):
        """
        Save image to disk using OpenCV with optimized encoding.
        
        Args:
            path: Target file path or directory
        """
        if path is None:
            path = os.path.curdir
        # create folder if not exists
        elif os.path.dirname(path) != "" and not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

        # check if path contains a file name add default if not given
        if os.path.isdir(path):
            if self.file_name is None:
                self.file_name = "image_output.jpg"
                print(f"No filename given. Using {self.file_name}")
            path = os.path.join(path, self.file_name)
        cv2.imwrite(path, self.to_np_array())

    def _file_info(self):
        """
        Enhanced file info extraction with image-specific metadata.
        Detects image format, channels, and optimizes content type.
        """
        super()._file_info()
        
        # Extract image-specific information
        if self.file_size() > 0:
            try:
                # Get image array for analysis
                image_array = self.to_np_array()
                
                # Detect image properties
                img_type, channels = self.detect_image_type_and_channels(image_array)
                if img_type is not None:
                    self.content_type = f"image/{img_type}"
                    self._channels = channels
                    self._image_format = img_type
                    
            except Exception as e:
                print(f"Could not extract image metadata: {e}")
                # Fallback to filename-based detection
                if self.file_name:
                    detected_type = guess_content_type(self.file_name)
                    if detected_type.startswith('image/'):
                        self.content_type = detected_type

    @staticmethod
    @requires('cv2', 'numpy')
    def detect_image_type_and_channels(image) -> Tuple[str, int]:
        """
        Advanced image type and channel detection using multiple strategies.
        
        Args:
            image: Numpy array or list representing the image
            
        Returns:
            Tuple of (image_type, channel_count)
            
        Raises:
            ValueError: If image format is not supported
        """
        if isinstance(image, list):
            image = np.array(image)

        if not hasattr(image, 'shape'):
            raise ValueError("Unsupported image data type")

        # Determine channel count from shape
        if len(image.shape) == 2:
            channels = 1  # Grayscale
        elif len(image.shape) == 3:
            channels = image.shape[2]
        else:
            raise ValueError(f"Unsupported image shape: {image.shape}")

        # Try multiple encoding formats for format detection
        format_encodings = [
            ('.png', 'png'),
            ('.jpg', 'jpeg'),
            ('.bmp', 'bmp'),
            ('.tiff', 'tiff')
        ]

        for ext, img_type in format_encodings:
            try:
                success, encoded_image = cv2.imencode(ext, image)
                if success:
                    encoded_bytes = encoded_image.tobytes()
                    # validate with magic bytes
                    media_info = MediaTypeGuesser._detect_from_content_inspection(encoded_bytes)
                    if media_info.file_extension == ext:
                        return img_type, channels
            except Exception:
                continue

        # Default fallback
        return 'png', channels

    @property
    def channels(self) -> int:
        """
        Get number of image channels.
        
        Returns:
            Number of channels (1 for grayscale, 3 for RGB, 4 for RGBA)
        """
        if self._channels is None:
            try:
                image_array = self.to_np_array()
                _, self._channels = self.detect_image_type_and_channels(image_array)
            except Exception:
                # Reasonable default for unknown images
                self._channels = 3
        return self._channels

    @requires('numpy')
    @property
    def dimensions(self) -> Tuple[int, int]:
        """
        Get image dimensions (width, height).
        
        Returns:
            Tuple of (width, height) in pixels
        """
        try:
            image_array = self.to_np_array()
            if len(image_array.shape) >= 2:
                height, width = image_array.shape[:2]
                return width, height
        except Exception:
            pass
        return 0, 0
