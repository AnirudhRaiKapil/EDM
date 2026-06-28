from datetime import datetime

from pydantic import BaseModel, ConfigDict


class QualityRuleCreate(BaseModel):
    expectation_type: str
    parameters: dict
    severity: str = "blocking"


class QualityRuleRead(BaseModel):
    id: str
    dataset_id: str
    expectation_type: str
    parameters: dict
    severity: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QualityRunRead(BaseModel):
    id: str
    dataset_id: str
    job_id: str | None
    results: list[dict]
    outcome: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
