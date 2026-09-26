"""Safe upload handling: streamed size limit, content sniffing, SHA-256 for de-duplication."""
import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from ..config import UPLOAD_DIR, ALLOWED_EXT, MAX_UPLOAD_MB

CHUNK = 1024 * 1024
SIGNATURES = {
    ".pdf": [b"%PDF"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".tif": [b"II*\x00", b"MM\x00*"],
    ".tiff": [b"II*\x00", b"MM\x00*"],
}


class UploadRejected(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class StoredFile:
    path: Path
    size: int
    sha256: str
    filename: str


def safe_name(name: str | None) -> str:
    name = Path(name or "document").name.strip() or "document"
    return name[:200]


def _content_matches(ext: str, head: bytes) -> bool:
    if ext == ".txt":
        if b"\x00" in head:
            return False
        try:
            head.decode("utf-8")
        except UnicodeDecodeError as e:
            # A multi-byte char may be cut at the chunk boundary; tolerate only that.
            return e.start >= len(head) - 3
        return True
    return any(head.startswith(sig) for sig in SIGNATURES.get(ext, []))


async def store_upload(upload: UploadFile) -> StoredFile:
    filename = safe_name(upload.filename)
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise UploadRejected(f"{filename}: unsupported file type. Use PDF, PNG, JPG, TIFF or TXT.")

    limit = MAX_UPLOAD_MB * 1024 * 1024
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    digest, size, first = hashlib.sha256(), 0, True
    try:
        with dest.open("wb") as out:
            while chunk := await upload.read(CHUNK):
                if first:
                    if not _content_matches(ext, chunk[:4096]):
                        raise UploadRejected(f"{filename}: file contents don't match the {ext} extension.")
                    first = False
                size += len(chunk)
                if size > limit:
                    raise UploadRejected(f"{filename} is larger than {MAX_UPLOAD_MB} MB.", 413)
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise UploadRejected(f"{filename} is empty.")
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return StoredFile(path=dest, size=size, sha256=digest.hexdigest(), filename=filename)
