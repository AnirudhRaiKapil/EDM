import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.modules.core.exceptions import ValidationFailedError

logger = logging.getLogger("edm.scheduler")

_scheduler = BackgroundScheduler()
_job_prefix = "pipeline-"


def validate_cron(cron_expression: str) -> None:
    try:
        CronTrigger.from_crontab(cron_expression)
    except ValueError as exc:
        raise ValidationFailedError(f"invalid cron expression '{cron_expression}': {exc}") from exc


def _run_scheduled_pipeline(pipeline_id: str) -> None:
    # Runs on APScheduler's own background thread, outside any request -- needs its
    # own DB session rather than the get_db() FastAPI dependency.
    from app.modules.job.service import run_pipeline
    from app.modules.pipeline.service import get_pipeline

    db = SessionLocal()
    try:
        pipeline = get_pipeline(db, pipeline_id)
        run_pipeline(db, pipeline.owner_id, pipeline_id, trigger="scheduled")
    except Exception:
        logger.exception("scheduled run failed for pipeline %s", pipeline_id)
    finally:
        db.close()


def sync_schedule(pipeline_id: str, cron_expression: str | None) -> None:
    job_id = f"{_job_prefix}{pipeline_id}"
    existing = _scheduler.get_job(job_id)
    if existing:
        _scheduler.remove_job(job_id)
    if cron_expression:
        validate_cron(cron_expression)
        _scheduler.add_job(
            _run_scheduled_pipeline,
            CronTrigger.from_crontab(cron_expression),
            id=job_id,
            args=[pipeline_id],
            replace_existing=True,
        )


def list_scheduled_pipeline_ids() -> list[str]:
    return [job.id.removeprefix(_job_prefix) for job in _scheduler.get_jobs()]


def start() -> None:
    from app.database import Base, engine
    from app.modules.pipeline.models import Pipeline

    Base.metadata.create_all(bind=engine)  # safe no-op if main.py's lifespan already ran this
    if not _scheduler.running:
        _scheduler.start()

    db = SessionLocal()
    try:
        scheduled = db.query(Pipeline).filter(Pipeline.schedule_cron.is_not(None)).all()
        for pipeline in scheduled:
            sync_schedule(pipeline.id, pipeline.schedule_cron)
        logger.info("scheduler started, %d pipeline(s) scheduled", len(scheduled))
    finally:
        db.close()


def shutdown() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
