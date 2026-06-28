from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import publish
from app.modules.catalog import service as catalog_service
from app.modules.core.exceptions import NotFoundError, QualityCheckFailedError
from app.modules.core.models import utcnow
from app.modules.ingestion.connectors import load_source_dataframe
from app.modules.job.models import Job
from app.modules.lineage.service import record_edge
from app.modules.metadata.service import create_new_schema_version
from app.modules.pipeline.service import get_pipeline
from app.modules.pipeline.transformations import apply_transformation
from app.modules.quality.service import evaluate_rules
from app.modules.source.service import get_source
from app.modules.storage.adapter import storage


def run_pipeline(db: Session, owner_id: str, pipeline_id: str, trigger: str = "manual") -> Job:
    pipeline = get_pipeline(db, pipeline_id)
    source = get_source(db, pipeline.source_id)

    job = Job(
        pipeline_id=pipeline.id,
        pipeline_version=pipeline.version,
        status="running",
        trigger=trigger,
        started_at=utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    publish("pipeline.started", {"jobId": job.id, "pipelineId": pipeline.id})

    try:
        df = load_source_dataframe(source)
        rows_in = len(df)

        for transformation in pipeline.transformations:
            df = apply_transformation(df, transformation.type, transformation.parameters)
        rows_out = len(df)

        dataset = catalog_service.get_dataset_by_name(
            db, pipeline.project_id, pipeline.output_dataset_name, pipeline.output_layer
        )

        quality_outcome = None
        if dataset is not None:
            # Quality rules can only exist once a dataset has run at least once (rules are
            # defined against a Dataset, per 02-domain-model.md). Evaluated BEFORE writing
            # storage/schema, so a blocking failure leaves the previously published data
            # untouched ("prevent downstream publication" per 00-vision-and-requirements.md).
            quality_run = evaluate_rules(db, dataset.id, df, job.id)
            quality_outcome = quality_run.outcome
            if quality_outcome == "failed":
                raise QualityCheckFailedError(
                    f"data quality check failed for dataset '{dataset.id}': {quality_run.results}"
                )
        else:
            dataset = catalog_service.register_dataset(
                db, owner_id, pipeline.project_id, pipeline.output_dataset_name,
                pipeline.output_layer, physical_location="pending",
            )

        relative_path = storage.save_dataframe(pipeline.output_layer, dataset.id, df)
        dataset.physical_location = relative_path
        db.add(dataset)
        db.commit()

        schema = create_new_schema_version(db, dataset.id, df)
        catalog_service.attach_schema(db, dataset, schema.id)

        record_edge(db, "source", source.id, "dataset", dataset.id, job.id)
        record_edge(db, "pipeline", pipeline.id, "dataset", dataset.id, job.id)

        job.status = "succeeded"
        job.dataset_id = dataset.id
        job.metrics = {"rowsIn": rows_in, "rowsOut": rows_out, "qualityOutcome": quality_outcome}
        job.finished_at = utcnow()
        db.add(job)
        db.commit()
        db.refresh(job)
        publish(
            "pipeline.completed",
            {"jobId": job.id, "pipelineId": pipeline.id, "datasetId": dataset.id},
        )
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = utcnow()
        db.add(job)
        db.commit()
        db.refresh(job)
        publish("pipeline.failed", {"jobId": job.id, "pipelineId": pipeline.id, "error": str(exc)})

    return job


def list_jobs(db: Session, pipeline_id: str) -> list[Job]:
    return list(db.execute(select(Job).where(Job.pipeline_id == pipeline_id)).scalars())


def get_job(db: Session, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise NotFoundError(f"job '{job_id}' not found")
    return job
