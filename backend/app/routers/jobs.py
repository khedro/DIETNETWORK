import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_verified_user
from app.models import Job, User
from app.schemas import JobDetailOut, JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _get_owned_job(job_id: str, user: User, db: AsyncSession) -> Job:
    job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
    if not job or job.user_id != user.id:
        # 404, not 403: don't confirm existence of other users' jobs.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


@router.get("", response_model=list[JobOut])
async def list_jobs(user: User = Depends(get_current_verified_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc()))
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobDetailOut)
async def get_job(job_id: str, user: User = Depends(get_current_verified_user), db: AsyncSession = Depends(get_db)):
    return await _get_owned_job(job_id, user, db)


@router.get("/{job_id}/download")
async def download_results(
    job_id: str, user: User = Depends(get_current_verified_user), db: AsyncSession = Depends(get_db)
):
    job = await _get_owned_job(job_id, user, db)
    if not job.results_path or not os.path.isfile(job.results_path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Results are not available for this job")
    return FileResponse(job.results_path, filename=f"{job_id}_dietnet_predictions.txt")
