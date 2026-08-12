from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class StoredObject:
    storage_key: str
    size: int
    sha256: str


class AttachmentStorage(Protocol):
    """Replaceable private object-storage boundary.

    Implementations own opaque storage keys and must compute size and digest from
    the bytes actually received.  A future S3 adapter can implement this contract
    without changing the attachment or messaging services.
    """

    def store(self, source: BinaryIO, *, max_bytes: int) -> StoredObject: ...

    def open(self, storage_key: str) -> BinaryIO: ...

    def delete(self, storage_key: str) -> None: ...
