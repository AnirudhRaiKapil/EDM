from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.modules.auth.models import User
from app.modules.source import service as source_service
from app.modules.source.schemas import SourceRead
from app.modules.storage.adapter import storage
from app.permissions import require_source_access

router = APIRouter(tags=["ingestion"])


@router.post("/sources/{source_id}/upload", response_model=SourceRead)
async def upload_source_file(
    source_id: str,
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_source_access(db, current_user.id, source_id)
    source = source_service.get_source(db, source_id)
    content = await file.read()
    relative_path = storage.save_raw_upload(source_id, file.filename, content)
    return source_service.attach_raw_file(db, source, relative_path)
