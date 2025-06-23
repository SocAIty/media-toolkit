from media_toolkit import AudioFile

outdir = "outdir/"


def test_audio_file():
    audio_file = AudioFile().from_file("test_files/test_audio.wav")
    audio_file.save(f"{outdir}/test_audio.wav")
