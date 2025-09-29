from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from fractions import Fraction


@dataclass
class VideoInfo:
    """Video metadata container with validation and derived properties."""
    frame_rate: float = None
    frame_count: int = None
    duration: float = None
    width: int = None
    height: int = None
    pix_fmt: str = None
    video_codec: str = None          # e.g., 'h264', 'hevc'
    video_bit_rate: int = None       # e.g., 5000000 (bits/s)
    audio_sample_rate: int = None
    audio_channels: int = None
    audio_codec: str = None

    def __post_init__(self):
        self._derive_missing()

    @property
    def shape(self) -> Optional[Tuple[int, int]]:
        return (self.width, self.height) if self.width and self.height else None

    @property
    def is_valid(self) -> bool:
        return any(vars(self).values())

    def _derive_missing(self) -> None:
        """Fill missing values when enough data exists."""
        if not self.frame_rate and self.duration and self.frame_count:
            self.frame_rate = self.frame_count / self.duration
        if not self.duration and self.frame_rate and self.frame_count:
            self.duration = self.frame_count / self.frame_rate

    def update(self, **kwargs) -> "VideoInfo":
        """Update only missing or invalid values."""
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None and not getattr(self, key):
                setattr(self, key, value)
        self._derive_missing()
        return self


# ---------------- Safe conversion helpers ---------------- #

def _safe_float(value) -> Optional[float]:
    if value in (None, "", "N/A"):
        return None
    try:
        f = float(Fraction(str(value))) if "/" in str(value) else float(value)
        return f if f > 0 else None
    except Exception:
        return None


def _safe_int(value) -> Optional[int]:
    try:
        i = int(float(value))
        return i if i > 0 else None
    except Exception:
        return None


# ---------------- Probe methods ---------------- #

def _probe_pyav(file_path: str) -> Dict[str, Any]:
    try:
        import av
        with av.open(file_path) as c:
            v = next((s for s in c.streams if s.type == "video"), None)
            a = next((s for s in c.streams if s.type == "audio"), None)
            if not v:
                return {}
            result = {
                "frame_rate": _safe_float(getattr(v, "average_rate", None)),
                "frame_count": _safe_int(getattr(v, "frames", None)),
                "width": _safe_int(getattr(v, "width", None)),
                "height": _safe_int(getattr(v, "height", None)),
                "pix_fmt": getattr(v, "pix_fmt", None),
                "video_codec": getattr(v, "codec_name", None),
                "video_bit_rate": _safe_int(getattr(v, "bit_rate", None)),
            }
            if a:
                result.update({
                    "audio_sample_rate": _safe_int(getattr(a, "sample_rate", None)),
                    "audio_channels": _safe_int(getattr(a, "channels", None)),
                    "audio_codec": getattr(a, "name", None),
                })
            return result
    except Exception:
        return {}


def _probe_mediainfo(file_path: str) -> Dict[str, Any]:
    try:
        from pydub.utils import mediainfo
        info = mediainfo(file_path)
        fps = _safe_float(info.get("avg_frame_rate")) or _safe_float(info.get("r_frame_rate"))
        result = {
            "frame_rate": fps,
            "frame_count": _safe_int(info.get("nb_frames")),
            "duration": _safe_float(info.get("duration")),
            "width": _safe_int(info.get("width")),
            "height": _safe_int(info.get("height")),
            "pix_fmt": info.get("pix_fmt"),
        }
        # Add audio info if present
        if info.get("sample_rate"):
            result.update({
                "audio_sample_rate": _safe_int(info.get("sample_rate")),
                "audio_channels": _safe_int(info.get("channels")),
                "audio_codec": info.get("codec_name"),
            })
        return result
    except Exception:
        return {}


def _probe_opencv(file_path: str) -> Dict[str, Any]:
    try:
        import cv2
        cap = cv2.VideoCapture(file_path)
        try:
            return {
                "frame_rate": _safe_float(cap.get(cv2.CAP_PROP_FPS)),
                "frame_count": _safe_int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                "width": _safe_int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": _safe_int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            }
        finally:
            cap.release()
    except Exception:
        return {}


# ---------------- Orchestration ---------------- #

def get_video_info(file_path: str) -> VideoInfo:
    """
    Probe video metadata using fallback priority:
    PyAV → MediaInfo → OpenCV
    """
    probes = (_probe_pyav, _probe_mediainfo, _probe_opencv)
    info = VideoInfo()

    for probe in probes:
        data = probe(file_path)
        if not data:
            continue
        info.update(**_prefer_better(info, data))
        if _enough_info(info):
            break
    return info


def _prefer_better(current: VideoInfo, new: Dict[str, Any]) -> Dict[str, Any]:
    """Prefer valid, reasonable values when both exist."""
    result = {}
    for k, v in new.items():
        if v is None:
            continue
        cur = getattr(current, k, None)
        if cur is None or _is_better(cur, v, k):
            result[k] = v
    return result


def _is_better(cur: Any, new: Any, field: str) -> bool:
    if field == "frame_rate":
        return not (1 <= cur <= 120) and (1 <= new <= 120)
    return cur <= 0 < new


def _enough_info(info: VideoInfo) -> bool:
    """Check if we have enough metadata to stop probing."""
    return bool(info.width and info.height and (info.frame_rate or (info.duration and info.frame_count)))
