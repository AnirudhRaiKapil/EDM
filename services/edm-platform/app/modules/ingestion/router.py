from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.modules.auth.models import User
from app.modules.core.exceptions import PayloadTooLargeError
from app.modules.source import service as source_service
from app.modules.source.schemas import SourceRead
from app.modules.storage.adapter import storage
from app.permissions import require_source_access

router = APIRouter(tags=["ingestion"])

_READ_CHUNK_BYTES = 1024 * 1024


async def _read_within_limit(file: UploadFile) -> bytes:
    """Reads an UploadFile in bounded chunks, aborting as soon as the configured limit
    is crossed rather than buffering the whole thing first -- a bare `await file.read()`
    has no size cap at all and will happily load an arbitrarily large upload entirely
    into memory before any check can reject it."""
    max_bytes = settings.max_upload_mb * 1024 * 1024
    chunks = []
    total = 0
    while True:
        chunk = await file.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise PayloadTooLargeError(f"file exceeds the {settings.max_upload_mb}MB upload limit")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/sources/{source_id}/upload", response_model=SourceRead)
async def upload_source_file(
    source_id: str,
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_source_access(db, current_user.id, source_id)
    source = source_service.get_source(db, source_id)
    content = await _read_within_limit(file)
    relative_path = storage.save_raw_upload(source_id, file.filename, content)
    return source_service.attach_raw_file(db, source, relative_path)
