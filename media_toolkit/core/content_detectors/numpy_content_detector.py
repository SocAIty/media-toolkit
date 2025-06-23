"""
Numpy array content type detector for media classification.
Analyzes numpy array characteristics to determine media type.
"""
from typing import Tuple
from media_toolkit.utils.dependency_requirements import requires_numpy

try:
    import numpy as np
except ImportError:
    pass


class NumpyContentTypeDetector:
    """
    Content type detector for numpy arrays based on shape and dtype analysis.
    Determines if arrays represent image, video, audio, or generic npy data.
    """
    
    @classmethod
    @requires_numpy()
    def detect_numpy_content_type(cls, np_array) -> Tuple[str, str]:
        """
        Analyze numpy array to determine media type.
        
        Args:
            np_array: Numpy array to analyze
            
        Returns:
            Tuple of (media_type, media_class_name) where:
            - media_type: 'image', 'video', 'audio', or 'npy'
            - media_class_name: 'ImageFile', 'VideoFile', 'AudioFile', or 'MediaFile'
        """
        if not hasattr(np_array, 'shape') or not hasattr(np_array, 'dtype'):
            return 'npy', 'MediaFile'
            
        shape = np_array.shape
        dtype = np_array.dtype
        
        # Check for image patterns
        if cls._is_likely_image(shape, dtype):
            return 'image', 'ImageFile'
            
        # Check for video patterns  
        if cls._is_likely_video(shape, dtype):
            return 'video', 'VideoFile'
            
        # Check for audio patterns
        if cls._is_likely_audio(shape, dtype):
            return 'audio', 'AudioFile'
            
        # Default to generic numpy file
        return 'npy', 'MediaFile'
    
    @staticmethod
    def _is_likely_image(shape: tuple, dtype) -> bool:
        """
        Determine if array shape/dtype represents an image.
        
        Image patterns:
        - 2D: (height, width) - grayscale
        - 3D: (height, width, channels) - RGB/RGBA/etc
        - 4D: (batch, height, width, channels) - batch of images
        """
        ndim = len(shape)
        
        # 2D grayscale image
        if ndim == 2:
            height, width = shape
            # Reasonable image dimensions (10x10 to 10000x10000)
            return (10 <= height <= 10000 and 10 <= width <= 10000 and 
                    dtype in [np.uint8, np.uint16, np.float32, np.float64, np.int8, np.int16])
        
        # 3D color image
        elif ndim == 3:
            height, width, channels = shape
            # Common channel counts: 1(gray), 3(RGB), 4(RGBA)
            return (10 <= height <= 10000 and 10 <= width <= 10000 and 
                    channels in [1, 3, 4] and
                    dtype in [np.uint8, np.uint16, np.float32, np.float64, np.int8, np.int16])
        
        # 4D batch of images
        elif ndim == 4:
            batch, height, width, channels = shape
            # Small batch sizes, reasonable image dimensions
            return (1 <= batch <= 1000 and 10 <= height <= 10000 and 10 <= width <= 10000 and
                    channels in [1, 3, 4] and
                    dtype in [np.uint8, np.uint16, np.float32, np.float64, np.int8, np.int16])
        
        return False
    
    @staticmethod
    def _is_likely_video(shape: tuple, dtype) -> bool:
        """
        Determine if array shape/dtype represents a video.
        
        Video patterns:
        - 4D: (frames, height, width, channels) - video sequence
        - 5D: (batch, frames, height, width, channels) - batch of videos
        """
        ndim = len(shape)
        
        # 4D video sequence
        if ndim == 4:
            frames, height, width, channels = shape
            # Multiple frames, reasonable video dimensions
            return (2 <= frames <= 100000 and 10 <= height <= 4096 and 10 <= width <= 4096 and
                    channels in [1, 3, 4] and
                    dtype in [np.uint8, np.uint16, np.float32, np.float64, np.int8, np.int16])
        
        # 5D batch of videos
        elif ndim == 5:
            batch, frames, height, width, channels = shape
            # Small batch, multiple frames, reasonable dimensions
            return (1 <= batch <= 100 and 2 <= frames <= 10000 and 
                    10 <= height <= 4096 and 10 <= width <= 4096 and
                    channels in [1, 3, 4] and
                    dtype in [np.uint8, np.uint16, np.float32, np.float64, np.int8, np.int16])
        
        return False
    
    @staticmethod
    def _is_likely_audio(shape: tuple, dtype) -> bool:
        """
        Determine if array shape/dtype represents audio.
        
        Audio patterns:
        - 1D: (samples,) - mono audio
        - 2D: (samples, channels) - multi-channel audio
        - 2D: (channels, samples) - alternative layout
        """
        ndim = len(shape)
        
        # 1D mono audio
        if ndim == 1:
            samples, = shape
            # Reasonable audio length (0.1s at 8kHz to 10 hours at 192kHz)
            return (800 <= samples <= 69120000 and
                    dtype in [np.int16, np.int32, np.float32, np.float64, np.uint8, np.int8])
        
        # 2D multi-channel audio
        elif ndim == 2:
            dim1, dim2 = shape
            
            # Pattern 1: (samples, channels) - more common
            if 1 <= dim2 <= 32:  # Reasonable channel count
                samples = dim1
                return (800 <= samples <= 69120000 and
                        dtype in [np.int16, np.int32, np.float32, np.float64, np.uint8, np.int8])
            
            # Pattern 2: (channels, samples) - alternative layout
            elif 1 <= dim1 <= 32:  # Reasonable channel count
                samples = dim2
                return (800 <= samples <= 69120000 and
                        dtype in [np.int16, np.int32, np.float32, np.float64, np.uint8, np.int8])
        
        return False 