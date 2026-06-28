import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import publish
from app.modules.core.exceptions import NotFoundError, ValidationFailedError
from app.modules.quality.expectations import SUPPORTED_EXPECTATION_TYPES, evaluate_expectation
from app.modules.quality.models import QualityRule, QualityRun

SEVERITIES = ["warning", "blocking"]


def create_rule(
    db: Session, dataset_id: str, expectation_type: str, parameters: dict, severity: str
) -> QualityRule:
    if expectation_type not in SUPPORTED_EXPECTATION_TYPES:
        raise ValidationFailedError(
            f"unsupported expectation_type '{expectation_type}'; choose from {SUPPORTED_EXPECTATION_TYPES}"
        )
    if severity not in SEVERITIES:
        raise ValidationFailedError(f"severity must be one of {SEVERITIES}")
    if not parameters.get("column"):
        raise ValidationFailedError("quality rule parameters must include 'column'")

    rule = QualityRule(
        dataset_id=dataset_id,
        expectation_type=expectation_type,
        parameters=parameters,
        severity=severity,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def list_rules(db: Session, dataset_id: str) -> list[QualityRule]:
    return list(
        db.execute(select(QualityRule).where(QualityRule.dataset_id == dataset_id)).scalars()
    )


def delete_rule(db: Session, dataset_id: str, rule_id: str) -> None:
    rule = db.get(QualityRule, rule_id)
    if rule is None or rule.dataset_id != dataset_id:
        raise NotFoundError(f"quality rule '{rule_id}' not found on dataset '{dataset_id}'")
    db.delete(rule)
    db.commit()


def evaluate_rules(
    db: Session, dataset_id: str, df: pd.DataFrame, job_id: str | None
) -> QualityRun:
    rules = list_rules(db, dataset_id)
    results = []
    has_blocking_failure = False
    has_warning_failure = False

    for rule in rules:
        passed, details = evaluate_expectation(df, rule.expectation_type, rule.parameters)
        results.append(
            {
                "ruleId": rule.id,
                "expectationType": rule.expectation_type,
                "severity": rule.severity,
                "passed": passed,
                "details": details,
            }
        )
        if not passed:
            if rule.severity == "blocking":
                has_blocking_failure = True
            else:
                has_warning_failure = True

    if has_blocking_failure:
        outcome = "failed"
    elif has_warning_failure:
        outcome = "passed_with_warnings"
    else:
        outcome = "passed"

    run = QualityRun(dataset_id=dataset_id, job_id=job_id, results=results, outcome=outcome)
    db.add(run)
    db.commit()
    db.refresh(run)
    publish("quality.evaluated", {"datasetId": dataset_id, "jobId": job_id, "outcome": outcome})
    if outcome == "failed":
        publish("quality.failed", {"datasetId": dataset_id, "jobId": job_id, "results": results})
    return run


def list_runs(db: Session, dataset_id: str) -> list[QualityRun]:
    return list(
        db.execute(
            select(QualityRun)
            .where(QualityRun.dataset_id == dataset_id)
            .order_by(QualityRun.created_at.desc())
        ).scalars()
    )
