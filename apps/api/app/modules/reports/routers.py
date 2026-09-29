import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.modules.auth.models import User
from app.modules.reports import service
from app.modules.reports.schemas import ReportResponse
from app.modules.submissions.service import SubmissionNotFoundError

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{submission_id}", response_model=ReportResponse)
async def get_report(
    submission_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    try:
        return await service.build_report(db, submission_id=submission_id, user_id=user.id)
    except SubmissionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Caso no encontrado.") from exc
    except service.ReportNotReadyError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"El reporte no está disponible (estado actual: {exc.status}).",
        ) from exc
