#!/usr/bin/env python3
"""
Test script to demonstrate the improved 4D array classification in numpy_content_detector.
"""

import numpy as np
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from media_toolkit.core.content_detectors.numpy_content_detector import NumpyContentTypeDetector


def test_4d_classification():
    """Test various 4D array scenarios to show improved classification."""
    
    print("Testing 4D Array Classification:")
    print("=" * 50)
    
    # Test case 1: Single image with batch dimension of 1 (should be image)
    single_image_batch = np.random.randint(0, 255, (1, 224, 224, 3), dtype=np.uint8)
    media_type, class_name, extension = NumpyContentTypeDetector.detect_numpy_content_type(single_image_batch)
    print(f"1. Single image batch (1, 224, 224, 3): {media_type} -> {class_name} (.{extension})")
    
    # Test case 2: Video sequence with multiple frames (should be video)
    video_sequence = np.random.randint(0, 255, (30, 480, 640, 3), dtype=np.uint8)
    media_type, class_name, extension = NumpyContentTypeDetector.detect_numpy_content_type(video_sequence)
    print(f"2. Video sequence (30, 480, 640, 3): {media_type} -> {class_name} (.{extension})")
    
    # Test case 3: Small batch of images (should be video due to multiple "frames")
    small_batch_images = np.random.randint(0, 255, (5, 512, 512, 3), dtype=np.uint8)
    media_type, class_name, extension = NumpyContentTypeDetector.detect_numpy_content_type(small_batch_images)
    print(f"3. Small batch images (5, 512, 512, 3): {media_type} -> {class_name} (.{extension})")
    
    # Test case 4: Large video sequence (should be video)
    large_video = np.random.randint(0, 255, (120, 1080, 1920, 3), dtype=np.uint8)
    media_type, class_name, extension = NumpyContentTypeDetector.detect_numpy_content_type(large_video)
    print(f"4. Large video (120, 1080, 1920, 3): {media_type} -> {class_name} (.{extension})")
    
    # Test case 5: Regular 3D image (should be image)
    regular_image = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
    media_type, class_name, extension = NumpyContentTypeDetector.detect_numpy_content_type(regular_image)
    print(f"5. Regular 3D image (256, 256, 3): {media_type} -> {class_name} (.{extension})")
    
    # Test case 6: Audio data (should be audio)
    audio_data = np.random.randn(44100 * 5).astype(np.float32)  # 5 seconds at 44.1kHz
    media_type, class_name, extension = NumpyContentTypeDetector.detect_numpy_content_type(audio_data)
    print(f"6. Audio data (220500,): {media_type} -> {class_name} (.{extension})")
    
    print("\nKey improvements:")
    print("- 4D arrays are now primarily classified as videos (unless batch size = 1)")
    print("- Extensions are now returned: .png for images, .mp4 for videos, .wav for audio")
    print("- Video detection takes priority over image batch detection")


if __name__ == "__main__":
    test_4d_classification() 