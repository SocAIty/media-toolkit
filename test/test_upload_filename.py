"""An UploadFile subclass keeps the filename the client declared."""

import io

from starlette.datastructures import Headers

from apipod.engine.backend.fastapi.LimitedUploadFile import LimitedUploadFile
from media_toolkit import media_from_any


def _upload(filename: str, payload: bytes, content_type: str) -> LimitedUploadFile:
    return LimitedUploadFile(
        io.BytesIO(payload),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_limited_upload_keeps_js_filename():
    media = media_from_any(_upload("sum.js", b"const sum = (a, b) => a + b\n", "text/javascript"))
    assert media.file_name == "sum.js"


def test_limited_upload_keeps_image_filename():
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    media = media_from_any(_upload("photo.png", png, "image/png"))
    assert media.file_name == "photo.png"


def test_nameless_text_has_no_extension():
    upload = LimitedUploadFile(io.BytesIO(b"const sum = (a, b) => a + b\n"), filename=None)
    media = media_from_any(upload)
    assert not (media.file_name or "").endswith(".js")
