"""
Comprehensive tests for media-toolkit including file conversion utilities.
Incorporates tests from test_audio_file, test_image_file, and test_video_file.
"""
import os
import cv2
import numpy as np
import pytest
import time

from media_toolkit import MediaFile, ImageFile, AudioFile, VideoFile
from media_toolkit.core.media_files.file_conversion import (
    media_from_numpy,
    media_from_any,
    _resolve_media_class,
    _interpret_type_hint
)

# Test directory setup
outdir = "test/outdir/"
outdir_video = f"{outdir}video/"
test_files_dir = "test/test_files/"


def setup_test_directory():
    """Create output directory for test files."""
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(outdir_video, exist_ok=True)
    yield


class TestExistingFunctionality:
    """Tests from existing test files."""
    
    def test_audio_file(self):
        """Test from test_audio_file.py"""
        audio_file = AudioFile().from_file(f"{test_files_dir}test_audio.wav")
        audio_file.save(f"{outdir}test_audio.wav")
        assert os.path.exists(f"{outdir}test_audio.wav")

    def test_audio_stream(self):
        """Test from test_audio_stream.py"""
        audio_file = AudioFile().from_file(f"{test_files_dir}test_audio.wav")
        audio_stream = audio_file.to_stream()
        
        from_stream_direct = AudioFile().from_stream(audio_stream)
        assert from_stream_direct.file_size() > 0
        from_stream_direct.save(f"{outdir}test_from_audio_stream.wav")
        assert os.path.exists(f"{outdir}test_from_audio_stream.wav")

        # Reset stream and test numpy path
        audio_stream.container.seek(0)
        audio_packages = []
        for i, audio in enumerate(audio_stream.frames(output_format="numpy")):
            audio_packages.append(audio)

        audio_file_from_np = AudioFile().from_np_array(audio_packages, sample_rate=audio_stream.sample_rate)
        audio_file_from_np.save(f"{outdir}test_from_audio_np.mp3")
        assert os.path.exists(f"{outdir}test_from_audio_np.mp3")

    def test_audio_from_av_packages(self):
        """Test from test_audio_file.py"""
        audio_file = AudioFile().from_file(f"{test_files_dir}test_audio.wav")
        audio_stream = audio_file.to_stream()
        audio_file_from_av_packages = AudioFile().from_av_audio_frames(audio_stream.frames(output_format="av"), output_format="m4a", codec="aac")
        audio_file_from_av_packages.save(f"{outdir}test_from_audio_av_packages.m4a")
        audio_file_from_av_packages.save(f"{outdir}test_from_audio_av_packages.mp3")
        assert os.path.exists(f"{outdir}test_from_audio_av_packages.m4a")

    def test_img_from_url(self):
        """Test from test_image_file.py"""
        url = "https://socaityfiles.blob.core.windows.net/backend-model-meta/speechcraft_icon.png"
        fromurl = ImageFile().from_any(url)
        fromurl.save(f"{outdir}test_img_from_url.png")
        assert os.path.exists(f"{outdir}test_img_from_url.png")

    def test_img_from_file_to_np_array(self):
        """Test from test_image_file.py"""
        img_file = ImageFile().from_file(f"{test_files_dir}test_image.png")
        np_array = img_file.to_np_array()
        assert np_array is not None
        assert np_array.shape == (544, 512, 4)
        assert np_array.dtype == np.uint8
        img2 = ImageFile().from_np_array(np_array)
        img2.save(f"{outdir}test_img_from_file_to_np_array.jpg")
        assert os.path.exists(f"{outdir}test_img_from_file_to_np_array.jpg")

    def test_video_file(self):
        """Test from test_video_file.py"""
        test_video = f"{test_files_dir}test_video.mp4"
        vf = VideoFile().from_file(test_video)
        # extract audio_file
        vf.extract_audio(f"{outdir_video}extracted_audio.mp3")
        audio_bytes = vf.extract_audio()
        assert audio_bytes is not None
        assert os.path.exists(f"{outdir_video}extracted_audio.mp3")

    def test_video_from_files(self):
        """Test from test_video_file.py"""
        # First create some test images
        if not os.path.exists(f"{outdir_video}test_out_video_stream_0.png"):
            self.test_video_stream()
        
        files = [f"{outdir_video}test_out_video_stream_{i}.png" for i in range(10)]
        vf = VideoFile().from_files(files, frame_rate=30, audio_file=f"{outdir_video}extracted_audio.mp3")
        vf.save(f"{outdir_video}test_from_files_add_audio.mp4")
        
        # from dir; and combine audio and video
        fromdir = VideoFile().from_dir(outdir_video, audio=f"{outdir_video}extracted_audio.mp3", frame_rate=30)
        fromdir.save(f"{outdir_video}test_from_dir.mp4")
        
        assert os.path.exists(f"{outdir_video}test_from_files_add_audio.mp4")
        assert os.path.exists(f"{outdir_video}test_from_dir.mp4")

    def test_video_stream(self):
        """Test from test_video_file.py"""
        vf = VideoFile().from_file(f"{test_files_dir}test_video.mp4")
        stream = vf.to_stream()
        for i, img in enumerate(stream):
            if i >= 30:  # Limit to 30 frames for testing
                break
            p = f"{outdir_video}test_out_video_stream_{i}.png"
            cv2.imwrite(p, img)

        audio_packages = []
        # Use a fresh stream for audio decoding
        audio_stream = VideoFile().from_file(f"{test_files_dir}test_video.mp4").to_stream()
        for i, audio in enumerate(audio_stream.audio_frames(output_format="numpy")):
            if i >= 30:  # Limit to 30 frames for testing
                break
            audio_packages.append(audio)
        audio_file = AudioFile().from_np_array(audio_packages)
        audio_file.save(f"{outdir_video}extracted_audio.mp3")
  
        # test video clients with audio_file
        fromdir = VideoFile().from_dir(outdir_video, audio=f"{outdir_video}extracted_audio.mp3", frame_rate=30)
        assert fromdir.file_size() > 0
        fromstream = VideoFile().from_stream(fromdir.to_stream())
        fromstream.save(f"{outdir_video}test_from_stream.mp4")
        
        assert os.path.exists(f"{outdir_video}test_from_stream.mp4")

    def test_video_to_audio_stream(self):
        """Test video to audio stream."""
        vf = VideoFile().from_file(f"{test_files_dir}test_video.mp4")
        stream = vf.to_stream()
        audio_frames = stream.audio_frames(output_format="av")
        af = AudioFile().from_av_audio_frames(audio_frames)
        af.save(f"{outdir_video}test_video_to_audio_stream.mp3")
        af.save(f"{outdir_video}test_video_to_audio_stream.m4a")
        af.save(f"{outdir_video}test_video_to_audio_stream.wav")
        assert os.path.exists(f"{outdir_video}test_video_to_audio_stream.mp3")
        assert os.path.exists(f"{outdir_video}test_video_to_audio_stream.m4a")
        assert os.path.exists(f"{outdir_video}test_video_to_audio_stream.wav")
 
    def test_video_stream_speed(self):
        """Test video stream speed."""
        # test video to stream
        vf = VideoFile().from_file(f"{test_files_dir}test_video.mp4")
        stream = vf.to_stream()
        start_time = time.time()
        video_frames = []
        n_frames = 300
        for i, img in enumerate(stream):
            if i >= n_frames:
                break
            video_frames.append(img)

        audio_frames = stream.audio_frames(output_format="av")
        end_time = time.time()
        fps = n_frames / (end_time - start_time)
        print(f"Video to stream fps: {fps}")
        assert fps > 60

        # test video encode from frames
        start_time = time.time()
        video_from_array = VideoFile().from_generators(
            video_frames,
            audio_generator=audio_frames,
            frame_rate=int(vf.video_info.frame_rate or 30)
        )
        end_time = time.time()
        fps = n_frames / (end_time - start_time)
        print(f"Video encode from frames fps: {fps}")
        # assert fps > 30
        video_from_array.save(f"{outdir_video}test_video_stream_speed.mp4")
        assert os.path.exists(f"{outdir_video}test_video_stream_speed.mp4")

    def test_direct_to_and_from_stream(self):
        """Test direct to and from stream."""
        in_path = f"{test_files_dir}test_video.mp4"
        out_path = f"{outdir_video}test_direct_to_and_from_stream.mp4"
        # from file
        vf = VideoFile().from_file(in_path)
        video_gen = vf.to_stream()
        fromstream = VideoFile().from_stream(video_gen)
        # save the video
        fromstream.save(out_path)
        # check if the video is roughly the same
        assert abs(fromstream.file_size() - vf.file_size()) < 1024 * 1024  # smaller 1kb
       

class TestFileConversionUtilities:
    """Tests for file conversion utility functions."""

    def test_interpret_type_hint(self):
        """Test _interpret_type_hint function."""
        # Test None input
        assert _interpret_type_hint(None) is None
        
        # Test class instances
        assert _interpret_type_hint(ImageFile) == "ImageFile"
        assert _interpret_type_hint(AudioFile()) == "AudioFile"
        assert _interpret_type_hint(VideoFile) == "VideoFile"
        
        # Test string hints
        assert _interpret_type_hint("image") == "ImageFile"
        assert _interpret_type_hint("audio") == "AudioFile"
        assert _interpret_type_hint("video") == "VideoFile"
        assert _interpret_type_hint("npy") == "MediaFile"
        
        # Test extensions
        assert _interpret_type_hint("jpg") == "ImageFile"
        assert _interpret_type_hint("mp3") == "AudioFile"
        assert _interpret_type_hint("mp4") == "VideoFile"
        assert _interpret_type_hint("wav") == "AudioFile"
        assert _interpret_type_hint("png") == "ImageFile"
        
        # Test invalid input
        assert _interpret_type_hint("invalid") is None
        assert _interpret_type_hint(123) is None

    def test_resolve_media_class(self):
        """Test _resolve_media_class function."""
        assert _resolve_media_class("MediaFile") == MediaFile
        assert _resolve_media_class("ImageFile") == ImageFile
        assert _resolve_media_class("AudioFile") == AudioFile
        assert _resolve_media_class("VideoFile") == VideoFile
        assert _resolve_media_class("InvalidClass") == MediaFile  # fallback

    def test_media_from_numpy_with_hint(self):
        """Test media_from_numpy with type hints."""
        # Create test numpy arrays
        image_array = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        audio_array = np.random.rand(1000).astype(np.float32)
        
        # Test with type hints
        img_file = media_from_numpy(image_array, type_hint="image")
        assert isinstance(img_file, ImageFile)
        
        audio_file = media_from_numpy(audio_array, type_hint=AudioFile)
        assert isinstance(audio_file, AudioFile)
        
        # Test with extension hint
        img_file2 = media_from_numpy(image_array, type_hint="jpg")
        assert isinstance(img_file2, ImageFile)

    def test_media_from_numpy_auto_detect(self):
        """Test media_from_numpy with automatic detection."""
        # Create image-like array
        image_array = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        media_file = media_from_numpy(image_array)
        # Should auto-detect as some media file type
        assert isinstance(media_file, (MediaFile, ImageFile))

    def test_media_from_file(self):
        """Test media_from_file function."""
        # Test with existing audio file
        audio_file = media_from_any(f"{test_files_dir}test_audio.wav")
        assert isinstance(audio_file, AudioFile)
        
        # Test with existing video file
        video_file = media_from_any(f"{test_files_dir}test_video.mp4")
        assert isinstance(video_file, VideoFile)

    def test_media_from_any_file_path(self):
        """Test media_from_any with file paths."""
        # Test audio file
        audio_file = media_from_any(f"{test_files_dir}test_audio.wav")
        assert isinstance(audio_file, AudioFile)
        
        # Test video file
        video_file = media_from_any(f"{test_files_dir}test_video.mp4")
        assert isinstance(video_file, VideoFile)

    def test_media_from_any_with_type_hint(self):
        """Test media_from_any with type hints."""
        # Force audio file to be treated as MediaFile
        media_file = media_from_any(f"{test_files_dir}test_audio.wav", type_hint="npy")
        assert isinstance(media_file, MediaFile)
        
        # Force with class hint
        audio_file = media_from_any(f"{test_files_dir}test_video.mp4", type_hint=AudioFile)
        assert isinstance(audio_file, AudioFile)

    def test_media_from_any_numpy_array(self):
        """Test media_from_any with numpy arrays."""
        image_array = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        media_file = media_from_any(image_array)
        assert isinstance(media_file, (MediaFile, ImageFile))

    def test_media_from_any_existing_media_file(self):
        """Test media_from_any with existing MediaFile instances."""
        original = ImageFile().from_file(f"{test_files_dir}test_audio.wav")  # Will load as ImageFile
        result = media_from_any(original)
        assert result is original  # Should return the same instance

    def test_3d_model_file(self):
        """Test loading 3D model files."""
        # Test GLB file (binary glTF)
        glb_file = media_from_any(f"{test_files_dir}test_mesh.glb")
        assert isinstance(glb_file, MediaFile)
        assert glb_file.file_name.endswith('.glb')
        assert glb_file.content_type == 'model/gltf-binary'
        assert glb_file.file_size() > 0

        # Test that we can convert to different formats
        glb_bytes = glb_file.to_bytes()
        assert len(glb_bytes) > 0

        # Test loading from bytes
        glb_from_bytes = media_from_any(glb_bytes)
        assert isinstance(glb_from_bytes, MediaFile)
        assert glb_from_bytes.file_size() == len(glb_bytes)

        # Test base64 conversion
        glb_base64 = glb_file.to_base64()
        assert isinstance(glb_base64, str)
        assert len(glb_base64) > 0

        # Test loading from base64
        glb_from_base64 = media_from_any(glb_base64)
        assert isinstance(glb_from_base64, MediaFile)
        assert glb_from_base64.file_size() == glb_file.file_size()

        # Test with type hint override
        glb_as_media = media_from_any(f"{test_files_dir}test_mesh.glb", type_hint="asset_3d")
        assert isinstance(glb_as_media, MediaFile)
        # Should still contain the GLB data despite the hint
        assert glb_as_media.file_size() > 0

        glb_from_url = media_from_any("https://replicate.delivery/yhqm/VL5mWW95DxoQAdPeOHf3LlTeC7PJv2MhMu17YXWcrhpuP2RrA/textured_mesh.glb")
        assert isinstance(glb_from_url, MediaFile)
        assert glb_from_url.file_size() > 0
        pass 

    def test_media_from_FileModel(self):
        """Test media_from_FileModel function."""
        # Test valid FileModel dict
        file_model = {
            'file_name': 'test.jpg',
            'content': f"{test_files_dir}test_audio.wav",  # Use existing file
            'content_type': 'image/jpeg'
        }
        
        # Test with allow_reads_from_disk=True
        media_file = media_from_any(file_model, allow_reads_from_disk=True)
        assert isinstance(media_file, ImageFile)  # Should detect as image based on content_type
        
        # Test invalid input
        try:
            media_from_any("invalid", allow_reads_from_disk=False)
            assert False, "Should raise an error"
        except Exception:
            pass
        
        # Test security check
        with pytest.raises(ValueError, match="Reading files from disk is not allowed"):
            media_from_any(file_model, allow_reads_from_disk=False)

    def test_media_from_FileModel_with_bytes(self):
        """Test media_from_FileModel with byte content."""
        # Read file content as bytes
        with open(f"{test_files_dir}test_audio.wav", 'rb') as f:
            content = f.read()
        
        file_model = {
            'file_name': 'test.wav',
            'content': content,
            'content_type': 'audio/wav'
        }
        
        media_file = media_from_any(file_model)
        assert isinstance(media_file, AudioFile)

    def test_error_handling(self):
        """Test error handling in conversion functions."""
        # Test invalid file path
        with pytest.raises(ValueError):
            media_from_any("nonexistent_file.xyz")
        
        # Test invalid numpy array
        with pytest.raises(Exception):
            media_from_numpy("not_an_array")


class TestIntegration:
    """Integration tests combining multiple components."""
    
    def test_round_trip_conversion(self):
        """Test converting between different media types."""
        # Load audio file
        audio_file = AudioFile().from_file(f"{test_files_dir}test_audio.wav")
        
        # Convert to bytes and back
        audio_bytes = audio_file.to_bytes()
        new_audio = media_from_any(audio_bytes, type_hint="audio")
        assert isinstance(new_audio, AudioFile)
        
        # Save and verify
        new_audio.save(f"{outdir}round_trip_audio.wav")
        assert os.path.exists(f"{outdir}round_trip_audio.wav")

    def test_type_hint_override(self):
        """Test that type hints can override automatic detection."""
        # Load audio file but force it to be MediaFile
        media_file = media_from_any(f"{test_files_dir}test_audio.wav", type_hint="npy")
        assert isinstance(media_file, MediaFile)
        
        # Verify it still contains the audio data
        assert len(media_file.to_bytes()) > 0


def run_all_tests():
    """Run all tests when script is executed directly."""
    setup_test_directory()

    conversion_tests = TestFileConversionUtilities()
    conversion_tests.test_3d_model_file()
    print("✓ 3D model file test passed")

    # Run existing functionality tests
    existing_tests = TestExistingFunctionality()

    existing_tests.test_img_from_url()
    print("✓ Image from URL test passed")
#
    existing_tests.test_img_from_file_to_np_array()
    print("✓ Image from file to np array test passed")
#
    existing_tests.test_audio_file()
    print("✓ Audio file test passed")
    
    existing_tests.test_audio_stream()
    print("✓ Audio stream test passed")

    existing_tests.test_audio_from_av_packages()
    print("✓ Audio from av packages test passed")

    existing_tests.test_video_file()
    print("✓ Video file test passed")
    
    existing_tests.test_video_from_files()
    print("✓ Video from files test passed")
    
    existing_tests.test_video_stream()
    print("✓ Video stream test passed")

    existing_tests.test_video_to_audio_stream()
    print("✓ Video to audio stream test passed")
    
    existing_tests.test_video_stream_speed()
    print("✓ Video stream speed test passed")

    existing_tests.test_direct_to_and_from_stream()
    print("✓ Direct to and from stream test passed")

    # Run file conversion tests
    conversion_tests = TestFileConversionUtilities()
    print("\nRunning file conversion utility tests...")
    
    conversion_tests.test_interpret_type_hint()
    print("✓ Type hint interpretation test passed")
    
    conversion_tests.test_resolve_media_class()
    print("✓ Media class resolution test passed")
    
    conversion_tests.test_media_from_numpy_with_hint()
    print("✓ Numpy conversion with hint test passed")
    
    conversion_tests.test_media_from_numpy_auto_detect()
    print("✓ Numpy auto-detection test passed")
    
    conversion_tests.test_media_from_file()
    print("✓ File conversion test passed")
    
    conversion_tests.test_media_from_any_file_path()
    print("✓ Any conversion with file path test passed")
    
    conversion_tests.test_media_from_any_with_type_hint()
    print("✓ Any conversion with type hint test passed")
    
    conversion_tests.test_media_from_any_numpy_array()
    print("✓ Any conversion with numpy array test passed")
    
    conversion_tests.test_media_from_any_existing_media_file()
    print("✓ Any conversion with existing media file test passed")

    conversion_tests.test_3d_model_file()
    print("✓ 3D model file test passed")

    conversion_tests.test_media_from_FileModel_with_bytes()
    print("✓ FileModel conversion with bytes test passed")
    
    # Run integration tests
    integration_tests = TestIntegration()
    print("\nRunning integration tests...")
    
    integration_tests.test_round_trip_conversion()
    print("✓ Round trip conversion test passed")
    
    integration_tests.test_type_hint_override()
    print("✓ Type hint override test passed")
    
    print("\n🎉 All tests passed successfully!")


if __name__ == "__main__":
    run_all_tests()
