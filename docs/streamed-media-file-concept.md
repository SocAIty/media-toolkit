# StreamedMediaFile as a separate type

Implementation concept. Not a commitment to ship. Pair with [media-file-streaming-handoff.md](media-file-streaming-handoff.md) (lazy `MediaFile`).

This document describes adding `StreamedMediaFile` next to `MediaFile` instead of making `MediaFile` lazy. Handlers opt into the spool handle by annotation. `MediaFile` / `ImageFile` stay eager and decoded-on-load, as they are today.

## Problem

Same copies as the sibling doc: Starlette spool → `FileContentBuffer` → httpx `read()` → file_service spool. Gateway and file_service want a seekable handle and magic metadata. Model handlers want `to_np_array()`.

The separate-type answer: those are different objects. Do not put both contracts on `MediaFile`.

## Goals

- Explicit handler contract: `list[StreamedMediaFile]` means "do not decode, I will stream out".
- `ImageFile` / `AudioFile` / `VideoFile` behavior stays exactly as today. No `_file_info` rewrite required to ship streaming.
- OpenAPI / fastSDK unchanged: both types rewrite to `UploadFile | FileModel | str`.
- Local users who never import `StreamedMediaFile` see no change.
- Same magic peek (~1 KB) and same `stream_to` / `fileobj` surface as the lazy design, but only on the new type.

## Non-goals

- Changing default ingest of `MediaFile`.
- Making `StreamedMediaFile` a drop-in for `to_np_array`.
- Parse-time S3 tee. Same Starlette `file_factory` limit as the sibling doc.
- Policy (yara, allowlist) inside the type.

## Type relationship

`StreamedMediaFile` is a **sibling** of `MediaFile`, not a subclass.

```
IMediaFile                  # optional: only if we need a shared ABC
    MediaFile
        ImageFile
        AudioFile
        VideoFile
    StreamedMediaFile       # handle, not a decoded media object
```

Subclassing `MediaFile` would inherit `to_np_array`, `to_json`, `save` via cv2, and `isinstance(x, MediaFile)` checks that today mean "I can treat this as owned bytes". A 2 GB video annotated as `StreamedMediaFile` must not accidentally decode because someone called a parent method.

Promote when the caller wants a real media object:

```python
typed = streamed.to_media_file()   # ImageFile | AudioFile | VideoFile | MediaFile
arr = typed.to_np_array()
```

`to_media_file()` uses `detection.media_class` and `from_bytesio_or_handle(fileobj, copy=False)` so the promote does not add a third buffer.

## Public API

```python
class StreamedMediaFile:
    filename: str
    content_type: str          # from ContentDetector, not the client header
    extension: str | None
    media_class: type          # ImageFile | AudioFile | VideoFile | MediaFile
    size: int
    detection: DetectionResult
    fileobj: BinaryIO

    @classmethod
    def from_upload(cls, upload, type_hint=None) -> StreamedMediaFile: ...

    @classmethod
    def from_any(cls, data, type_hint=None) -> StreamedMediaFile: ...

    def peek(self, n: int = 1024) -> bytes: ...
    def chunks(self, n: int = 65536) -> Iterator[bytes]: ...
    def stream_to(self, sink: ByteSink) -> Any: ...
    async def stream_to_async(self, sink: AsyncByteSink) -> Any: ...
    def to_media_file(self) -> MediaFile: ...
    def to_httpx_send_able_tuple(self) -> tuple:  # (filename, fileobj, content_type)
        ...
```

Generics as a constraint, not a cast:

```python
StreamedMediaFile              # any allowed type, magic decides media_class
StreamedMediaFile[ImageFile]   # 415 if magic is not ImageFile
```

`list[StreamedMediaFile]` is a list of handles. Do not run `MediaList.from_any` on it. `MediaList` builds `MediaFile` leaves and would undo the point.

URL / base64 / `FileModel` still construct a `StreamedMediaFile`. There is no inbound stream. `fileobj` is a completed buffer. Handler code stays one path. RunPod always takes this branch.

## Endpoint shape

```python
@app.endpoint("/v1/files")
async def upload(files: list[StreamedMediaFile]):
    out = []
    for f in files:
        url = await f.stream_to_async(s3_sink(content_type=f.content_type))
        out.append(url)
    return out

@app.endpoint("/infer")
def infer(image: ImageFile):
    return model(image.to_np_array())

@app.endpoint("/branch")
def branch(file: StreamedMediaFile):
    if file.media_class is ImageFile:
        return model(file.to_media_file().to_np_array())
    raise HTTPException(415, f"expected image, got .{file.extension}")
```

Gateway (consume on the request path, then enqueue URLs):

```python
@app.endpoint("/v1/text2image")
async def create_job(image: StreamedMediaFile, prompt: str):
    url = await image.stream_to_async(file_service_sink(...))
    return EnqueuePayload(input_data={"image": url, "prompt": prompt})
```

Do not put a `StreamedMediaFile` in Redis job params. Starlette will have closed the spool.

## APIPod wiring

Signature rewriter: treat `StreamedMediaFile` like `MediaFile` for OpenAPI (`LimitedUploadFile | FileModel | str`). Runtime conversion branches:

```python
if _is_streamed_media(annotation):
    hint = _streamed_hint(annotation)
    return StreamedMediaFile.from_upload(value, type_hint=hint)
# else existing media_from_any path
```

`_is_media_param` must return True so the wrap runs. `_get_media_target_type` must not collapse the type to `MediaFile`.

Queued + `StreamedMediaFile` and the handler did not consume: fail at registration, or copy to an owned `NamedTemporaryFile` in P3. Prefer fail-at-registration plus the gateway pattern (upload then enqueue URLs).

## Local use

```python
# unchanged, still the default teaching example
img = ImageFile().from_any("photo.jpg")
arr = img.to_np_array()

# new, only when you want a handle
from media_toolkit import StreamedMediaFile
handle = StreamedMediaFile.from_any("large.mp4")
await handle.stream_to_async(s3)
```

Two ways to load a file is the DX cost. Notebook users should not see `StreamedMediaFile` in the README quick start. It is a web/proxy type. Document it under "Web and API integration" next to APIPod.

If local code wants magic-without-decode on a path, `ContentDetector.detect_from_path` already exists. They do not need this class.

## Async

Same rule as the sibling doc: sync core, async twins at I/O edges (`stream_to_async`, later `from_url_async` on the handle). `StreamedMediaFile` does not make `MediaFile` async.

Because the type is only used at I/O boundaries (upload, proxy), it is reasonable to make `stream_to` async-only and skip the sync twin. That is a product choice. Local scripts that stream a path to S3 would then need `asyncio.run`. Prefer keeping both methods so the type is usable outside FastAPI.

## What we do not change

- `ImageFile._file_info` eager decode.
- `from_starlette_upload_file` full read on `MediaFile`.
- `to_httpx_send_able_tuple` on `MediaFile` (still `self.read()`), unless we fix it anyway. Fixing it on `MediaFile` is still worth doing; it does not require this type.

Shipping `StreamedMediaFile` without fixing `MediaFile.to_httpx_send_able_tuple` means two httpx conventions. Prefer fixing the tuple on both.

## Implementation order

1. Add `StreamedMediaFile` in media-toolkit: `from_upload`, `from_any`, `fileobj`, `peek`, `chunks`, `detection`, `to_media_file`, httpx tuple with file-like.
2. Export from `media_toolkit.core.media_files` and the package root.
3. APIPod: detect annotation, wrap, do not call `media_from_any`.
4. file_service / gateway handlers switch annotations and pass `fileobj` to S3 / httpx.
5. Tests: magic constraint, list wrap, URL/base64 wrap, queue rejection, promote to `ImageFile`.

No change to existing MediaFile tests if we do not touch `_file_info`.

## Risks

- Dual API. People annotate `MediaFile` on a proxy endpoint and get the old copies. The type only helps if authors know it exists.
- `to_media_file()` after `stream_to` needs `seek(0)`. Easy to forget if the sink consumed the handle.
- Generics (`StreamedMediaFile[ImageFile]`) need typing support and OpenAPI mapping. Easy to ship the unparameterized form first.
- `IMediaFile` as a shared ABC is awkward: `to_np_array` is not on the handle. Do not force the handle into that ABC. Duck-type `fileobj` / `to_httpx_send_able_tuple` instead.
- Package surface grows. README must keep the quick start on `ImageFile`.

## Open questions

- Name: `StreamedMediaFile` vs `MediaHandle` vs `IngestFile`. "Streamed" is slightly wrong (the inbound stream is already finished when the object exists). `MediaHandle` is more honest. Keep `StreamedMediaFile` if we want the annotation to match the conversation.
- Whether `MediaList[StreamedMediaFile]` is allowed or we only accept `list[StreamedMediaFile]`. Prefer `list` only, to avoid `MediaList.from_any`.
- Whether file_service allowlist/yara take a hook on `from_upload` or stay in the handler. Stay in the handler.

## Success

file_service and gateway annotate `StreamedMediaFile` and never build an `ImageFile` for a passthrough upload. Model services keep `ImageFile` and never import the new type. Local tutorials do not mention it.

## When this design wins

- You want the signature to be the contract (APIPod principle 1) and you do not want a silent behavior change on `ImageFile`.
- You cannot afford to retune `_file_info` / tests across image, audio, and video in the same release.
- Streaming is a platform concern (two apps) and should not change the object every notebook uses.

## When this design loses

- Two types for one file is the opposite of "one file API".
- Gateway already annotates `ImageFile` so APIPod will convert to `MediaFile`. Switching those generated handlers to `StreamedMediaFile` is a second migration.
- Most of the efficiency win (`fileobj` httpx tuple, no `read()` on proxy) can land on `MediaFile` without a new class.
