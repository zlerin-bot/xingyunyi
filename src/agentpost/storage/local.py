from __future__ import annotations

import hashlib
import os
import re
import secrets
from pathlib import Path
from typing import BinaryIO

from agentpost.storage.port import StoredObject


class InvalidFilenameError(ValueError):
    pass


class UploadTooLargeError(ValueError):
    pass


class StorageObjectNotFoundError(FileNotFoundError):
    pass


_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_PERCENT_ENCODED_CONTROL = re.compile(r"%(?:0[0-9a-f]|1[0-9a-f]|7f)", re.IGNORECASE)


def validate_filename(filename: str) -> str:
    if not isinstance(filename, str):
        raise InvalidFilenameError("filename must be a string")
    if not filename or len(filename) > 255:
        raise InvalidFilenameError("filename must contain 1-255 characters")
    if filename in {".", ".."}:
        raise InvalidFilenameError("filename is not valid")
    if Path(filename).is_absolute() or "/" in filename or "\\" in filename:
        raise InvalidFilenameError("filename must not contain path syntax")
    if _CONTROL_CHARACTERS.search(filename):
        raise InvalidFilenameError("filename must not contain control characters")
    if _PERCENT_ENCODED_CONTROL.search(filename):
        raise InvalidFilenameError("filename must not contain encoded control characters")
    return filename


class LocalAttachmentStorage:
    chunk_size = 64 * 1024

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.temp_root = self.root / ".tmp"
        self.temp_root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _resolve_key(self, storage_key: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{64}", storage_key):
            raise StorageObjectNotFoundError(storage_key)
        target = (self.root / storage_key[:2] / storage_key[2:]).resolve()
        if self.root not in target.parents:
            raise StorageObjectNotFoundError(storage_key)
        return target

    def store(self, source: BinaryIO, *, max_bytes: int) -> StoredObject:
        storage_key = secrets.token_hex(32)
        target = self._resolve_key(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temp = self.temp_root / f"{secrets.token_hex(16)}.upload"
        digest = hashlib.sha256()
        total = 0
        try:
            with temp.open("xb") as destination:
                while chunk := source.read(self.chunk_size):
                    total += len(chunk)
                    if total > max_bytes:
                        raise UploadTooLargeError(f"attachment exceeds the {max_bytes}-byte limit")
                    digest.update(chunk)
                    destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())
            temp.replace(target)
            target.chmod(0o600)
        except Exception:
            temp.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            raise
        return StoredObject(storage_key=storage_key, size=total, sha256=digest.hexdigest())

    def open(self, storage_key: str) -> BinaryIO:
        path = self._resolve_key(storage_key)
        try:
            return path.open("rb")
        except FileNotFoundError as exc:
            raise StorageObjectNotFoundError(storage_key) from exc

    def delete(self, storage_key: str) -> None:
        try:
            path = self._resolve_key(storage_key)
        except StorageObjectNotFoundError:
            return
        path.unlink(missing_ok=True)
