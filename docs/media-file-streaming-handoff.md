# MediaFile lazy ingest and outbound streaming

This document describes evolving `MediaFile` so ingest stays a view of an existing source (Starlette spool, path, URL body, BytesIO) until a method needs owned bytes or a decode. `stream_to` / `fileobj` become first-class outbound I/O. Local scripts and APIPod keep the same types.

## Problem

Today `from_starlette_upload_file` does `file.read()` into `FileContentBuffer`. `to_httpx_send_able_tuple` calls `self.read()` again. `ImageFile._file_info` calls `to_np_array()` on load. Audio and video probe (and sometimes decode) in `_file_info`.

APIPod then converts every upload through `media_from_any` before the handler. Gateway reads those bytes again and POSTs them to file_service. Three copies, one of them a typed decode the handler may never use.

`from_bytesio_or_handle(copy=False)` already exists. `from_url` already uses it after a full download. The missing piece is making the no-copy path the default for upload-like sources, and making decode / owned-copy explicit.

## Goals

- One type family: `MediaFile`, `ImageFile`, `AudioFile`, `VideoFile`.
- Local DX unchanged: `ImageFile().from_any("photo.jpg").to_np_array()` still works.
- APIPod DX unchanged: `def infer(image: ImageFile)` still works.
- Outbound stream without a second buffer: `stream_to`, `fileobj`, httpx tuple that returns a file-like.
- Magic peek (~1 KB) sets `content_type` / `extension` without decode.
- Sync core stays sync. Async is added at I/O edges, not by making every method `async`.
- APIPod queue path can force an owned copy before `add_job`.

## Non-goals

- True parse-time tee (S3 upload while the client is still transmitting). That needs Starlette `file_factory`, not a MediaFile state.
- Yara, allowlists, quotas. Those stay in file_service.
- Making `MediaFile` an async-only class.
- A new public type name for handlers.

## State machine

```
source (path | UploadFile.file | BytesIO | URL body)
        |
        v
     LAZY          fileobj + DetectionResult (1 KB peek)
        |          stream_to / fileobj / chunks / peek / save
        |
        +---- read / to_bytes / to_base64 ----+  still LAZY
        |     (pass over source, no owned copy)|  unless caller asked to own
        |
        +---- to_np_array / frames ------------+  DECODED
        |     (pixels / samples from fileobj)  |  may cache array
        |
        +---- materialize() or queue handoff --+  BUFFERED
              (FileContentBuffer owns bytes)
```

`LAZY` means we did not copy the source into our buffer. It does not mean the bytes are not on disk. Starlette may already have rolled the upload to a `SpooledTemporaryFile`.

`BUFFERED` means we own a `FileContentBuffer` (memory or `NamedTemporaryFile`) that outlives the request.

`DECODED` means cv2 / PyAV / numpy ran. Decode can read the lazy `fileobj`. It does not require BUFFERED first.

Call order is not a type. This is valid:

```python
url = await image.stream_to(sink)   # LAZY
arr = image.to_np_array()           # DECODED
```

## Public API (additive)

Keep every current method. Add:

```python
class MediaFile:
    # metadata from peek, not from decode
    @property
    def detection(self) -> DetectionResult: ...

    @property
    def is_lazy(self) -> bool: ...

    @property
    def is_decoded(self) -> bool: ...

    @property
    def fileobj(self) -> BinaryIO:
        """Seekable view of the current source (spool, path handle, or buffer)."""

    def peek(self, n: int = 1024) -> bytes: ...

    def chunks(self, n: int = 65536) -> Iterator[bytes]: ...

    def materialize(self) -> Self:
        """Copy source into an owned FileContentBuffer. Idempotent."""

    def stream_to(self, sink: ByteSink) -> Any:
        """Sync outbound copy from fileobj. Seek 0, write chunks, finalize."""

    async def stream_to_async(self, sink: AsyncByteSink) -> Any:
        """Async outbound copy. Same bytes, await sink.write."""

    async def from_url_async(self, url: str, headers: dict | None = None) -> Self:
        """Download with httpx2.AsyncClient. Stay LAZY on the response stream / spool."""
```

`to_httpx_send_able_tuple` changes to:

```python
return self.file_name, self.fileobj, self.content_type
```

httpx2 and boto accept a file-like. Returning `self.read()` is the bug.

`ByteSink` is a small protocol, not a class hierarchy:

```python
class ByteSink(Protocol):
    def write(self, data: bytes) -> None: ...
    def finalize(self) -> Any: ...

class AsyncByteSink(Protocol):
    async def write(self, data: bytes) -> None: ...
    async def finalize(self) -> Any: ...
```

S3 / fastCloud should use `fileobj` directly (`upload_fileobj_async`). Do not wrap boto in a 64 KB Python loop. `stream_to` is for sinks that only speak chunks.

## Ingest changes

| Source | Today | Proposed default |
|---|---|---|
| Starlette `UploadFile` | `file.read()` → buffer | wrap `upload.file`, peek 1 KB, `owns=False` |
| `BytesIO` / handle | `copy=True` unless caller says otherwise | `copy=False` when the handle is seekable and we do not need to outlive it |
| Path | open, copy into buffer | open as `fileobj` (LAZY) or keep copy for `use_temp_file` |
| URL | full download to BytesIO, then `copy=False` | same for sync; async variant can keep the stream/spool |
| base64 / bytes | already in memory | BUFFERED immediately (no win) |
| numpy | encode to bytes | BUFFERED + often DECODED |

`ContentDetector.detect_from_buffer(peek, file_name=...)` runs once at wrap. That sets `content_type` and `extension`. Do not call subclass `_file_info` decode on ingest.

`media_from_any(..., type_hint=ImageFile)` still constructs `ImageFile`. Magic must agree or we raise. The type parameter is a constraint, not a cast.

## Eager `_file_info` (blocker)

These must move to first access or the lazy path is fiction:

- `ImageFile._file_info` calls `to_np_array()` when `file_size() > 0`.
- `AudioFile._file_info` probes and may decode to get duration.
- `VideoFile._file_info` probes the container.

Replacement:

- Ingest: magic peek only.
- `content_type` from `DetectionResult`.
- `sample_rate` / `duration` / `channels`: compute on first property access, cache.
- `to_np_array`: decode from `fileobj`, cache the array.

Local `ImageFile().from_file("x.jpg")` still works. The first `to_np_array()` or `.width` pays the probe. Scripts that only check `content_type` stay cheap.

## Async

Lazy ingest is not async. It is "do not copy yet".

MediaToolkit is used in notebooks, CLI, OpenCV loops, and sync FastAPI wrappers. Making `from_any` / `to_np_array` / `save` async would break that DX.

Rule:

- CPU and buffer methods stay sync: `from_any`, `to_np_array`, `save`, `read`, `materialize`.
- Network and long outbound copies get async twins: `from_url_async`, `stream_to_async`.
- Sync `from_url` / `stream_to` remain. They block. That is correct for scripts.

APIPod async handlers call `await image.stream_to_async(sink)`. Sync handlers call `image.stream_to(sink)` or `to_np_array()`.

Do not detect the event loop inside `stream_to` and switch. One method, one concurrency model.

## Local use (not APIPod)

This is the DX bar. If a notebook feels harder, the design failed.

```python
# unchanged
img = ImageFile().from_any("photo.jpg")
arr = img.to_np_array()

# new, optional
img = ImageFile().from_any(upload)
await img.stream_to_async(s3)

# URL, still one liner
audio = AudioFile().from_url("https://example.com/a.wav")
```

Ownership locally: `from_file(path)` can stay a read of a path we do not own. The path outlives the object. `from_any(UploadFile)` in a raw FastAPI app has the same request-lifetime rule as APIPod. Document it: if you keep the object after the request, call `materialize()`.

`MediaList` / `MediaDict` keep working. Leaves are lazy `MediaFile`s. `to_httpx_send_able_tuple` on a list returns file-likes.

## APIPod integration

No new annotation. Signature rewrite stays `Union[LimitedUploadFile, FileModel, str]`.

P3 conversion:

```python
m = target_type()
m.from_starlette_upload_file(upload)  # wrap + peek, no full read
```

Queue path (in APIPod, not MediaToolkit):

- If the endpoint is queued, call `m.materialize()` before `add_job`, or consume with `stream_to` on the request path (gateway should upload, then enqueue URLs).
- Starlette closes `UploadFile` when the request ends. A lazy handle in Redis is a use-after-close.

RunPod: the payload is already bytes/base64. Object is BUFFERED from the start. Same methods.

Returning a `MediaFile` from an endpoint still serializes to `FileModel` (base64). That is a full read after the handler. Seek 0 if you already streamed. Document it.

## Ownership rules

| Situation | Action |
|---|---|
| Direct handler, consume before return | `owns=False`, wrap spool |
| Keep object after request | `materialize()` |
| Queued job params | APIPod `materialize()` or replace with URL |
| `from_file(path)` | lazy open, path is the owner |
| `from_bytes` / base64 | already owned |

`materialize()` is idempotent. DECODED cache survives (same bytes).

## Implementation order

1. `fileobj`, `peek`, `chunks`, `detection` on `MediaFile`. Change `to_httpx_send_able_tuple` to return `fileobj`.
2. `from_starlette_upload_file`: wrap + peek. Stop `file.read()`.
3. Move Image/Audio/Video `_file_info` decode/probe to first access.
4. `stream_to` / `stream_to_async`.
5. `materialize()`.
6. `from_url_async`.
7. APIPod: use the wrap path; `materialize()` on queue.
8. Gateway / file_service: pass `fileobj` into `upload_fileobj`, stop `media.read()`.

Each step is independently useful. 1–3 are the efficiency win for local and APIPod. 4–5 are the stream API. 7–8 are the platform proxy.

## Risks

- Hidden state. Callers assume `ImageFile` means "pixels ready". After this, pixels are ready after `to_np_array`. That matches how people already write handlers, but `_file_info` today made it true at construction. Tests that assert on `content_type` after construct still pass (magic). Tests that assert `_channels` after construct need a property access.
- `copy=False` aliasing. Mutating the Starlette spool mutates the `MediaFile`. Do not expose `truncate` on a borrowed handle.
- httpx tuple change. Callers that expect `bytes` as the second element break. That is an intended break. Document it. Offer `to_httpx_send_able_tuple(materialize=True)` if needed for one release.
- `FileContentBuffer.read()` seeks to 0, reads, seeks to 0. Fine for a full read. `chunks()` must not use that helper or every chunk restarts.
- Polyglot files. Magic is not yara. Do not sell peek as security.

## Open questions

- Default `copy` for `from_bytesio_or_handle` in local code. Changing the default is a behavior change for anyone who closes the handle after `from_any`. Safer: new default only for Starlette uploads; keep `copy=True` for generic handles unless `copy=False` is passed.
- Whether `read()` should call `materialize()` or only view the source. Prefer view. Ownership is `materialize()`.
- Whether `MediaList.from_any` should stay eager for mixed URL lists. Prefer lazy leaves, download on first access or on `stream_to`.

## Success

A 200 MB upload to a handler that only `stream_to`s S3 never enters `FileContentBuffer` and never hits cv2. A local `ImageFile().from_file(...).to_np_array()` still feels like one object. APIPod signatures do not change.
