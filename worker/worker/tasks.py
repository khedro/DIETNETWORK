import glob
import logging
import os
import traceback

from worker.celery_app import celery_app
from worker.config import settings
from worker.db import Job, User, get_session, utcnow
from worker.email import send_job_completed_email, send_job_failed_email
from worker.pipeline import (
    PipelineError,
    cleanup_intermediate_files,
    convert_bgen_to_plink,
    convert_vcf_to_plink,
    get_snp_overlap,
    parse_predictions,
    run_infer,
)

logger = logging.getLogger("worker.tasks")


def _find_genotype_file(raw_dir: str, input_type: str) -> str:
    if input_type == "vcf":
        for pattern in ("*.vcf.gz", "*.vcf"):
            hits = glob.glob(os.path.join(raw_dir, pattern))
            if hits:
                return hits[0]
        raise PipelineError("No VCF file found in upload directory.")
    else:
        hits = glob.glob(os.path.join(raw_dir, "*.bgen"))
        if not hits:
            raise PipelineError("No bgen file found in upload directory.")
        return hits[0]


def _find_sample_file(raw_dir: str) -> str:
    hits = glob.glob(os.path.join(raw_dir, "*.sample"))
    if not hits:
        raise PipelineError("No .sample file found alongside the bgen upload.")
    return hits[0]


@celery_app.task(name="worker.tasks.run_inference_job", bind=True, max_retries=0)
def run_inference_job(self, job_id: str) -> None:
    session = get_session()
    try:
        job = session.get(Job, job_id)
        if job is None:
            logger.error("Job %s not found; nothing to do.", job_id)
            return

        user = session.get(User, job.user_id)
        job.status = "running"
        job.started_at = utcnow()
        session.commit()

        raw_dir = job.raw_path
        results_dir = os.path.join(settings.data_root, job.user_id, job.id, "results")
        convert_dir = os.path.join(raw_dir, "converted")
        os.makedirs(results_dir, exist_ok=True)
        os.makedirs(convert_dir, exist_ok=True)

        plink_prefix = os.path.join(convert_dir, "query")

        if job.input_type == "vcf":
            genotype_file = _find_genotype_file(raw_dir, "vcf")
            convert_vcf_to_plink(genotype_file, plink_prefix)
        else:
            genotype_file = _find_genotype_file(raw_dir, "bgen")
            sample_file = _find_sample_file(raw_dir)
            convert_bgen_to_plink(genotype_file, sample_file, plink_prefix)

        output_prefix = os.path.join(results_dir, "result")
        predictions_file = run_infer(plink_prefix, output_prefix)

        overlap_count, overlap_total = get_snp_overlap(output_prefix)
        is_reliable = overlap_count >= settings.min_reliable_snp_overlap
        predictions = parse_predictions(predictions_file)

        cleanup_intermediate_files(output_prefix)

        job.status = "done"
        job.results_path = predictions_file
        job.snp_overlap_count = overlap_count
        job.snp_overlap_total = overlap_total
        job.is_reliable = is_reliable
        job.predictions = {"rows": predictions}
        job.completed_at = utcnow()
        session.commit()

        if settings.delete_raw_after_success:
            _delete_raw(job, session)

        if user:
            send_job_completed_email(user.email, job.id, overlap_count, overlap_total, is_reliable)

    except Exception as exc:  # noqa: BLE001 -- top-level task boundary, must not raise
        logger.error("Job %s failed: %s\n%s", job_id, exc, traceback.format_exc())
        session.rollback()
        job = session.get(Job, job_id)
        if job is not None:
            job.status = "failed"
            # User-facing message only -- never a raw stack trace.
            job.error_message = (
                str(exc)
                if isinstance(exc, PipelineError)
                else "An unexpected error occurred while processing your file. Support has been notified."
            )
            job.completed_at = utcnow()
            session.commit()
            user = session.get(User, job.user_id)
            if user:
                send_job_failed_email(user.email, job.id)
    finally:
        session.close()


def _delete_raw(job: Job, session) -> None:
    import shutil

    if job.raw_path and os.path.exists(job.raw_path):
        shutil.rmtree(job.raw_path, ignore_errors=True)
        job.raw_path = None
        job.raw_deleted_at = utcnow()
        session.commit()
