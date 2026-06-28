from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import publish
from app.modules.lineage.models import LineageEdge


def record_edge(
    db: Session,
    from_entity_type: str,
    from_entity_id: str,
    to_entity_type: str,
    to_entity_id: str,
    job_id: str | None = None,
) -> LineageEdge:
    edge = LineageEdge(
        from_entity_type=from_entity_type,
        from_entity_id=from_entity_id,
        to_entity_type=to_entity_type,
        to_entity_id=to_entity_id,
        job_id=job_id,
    )
    db.add(edge)
    db.commit()
    db.refresh(edge)
    publish(
        "lineage.edge_recorded",
        {
            "from": f"{from_entity_type}:{from_entity_id}",
            "to": f"{to_entity_type}:{to_entity_id}",
            "jobId": job_id,
        },
    )
    return edge


def get_upstream(db: Session, entity_type: str, entity_id: str) -> list[LineageEdge]:
    stmt = select(LineageEdge).where(
        LineageEdge.to_entity_type == entity_type, LineageEdge.to_entity_id == entity_id
    )
    return list(db.execute(stmt).scalars())


def get_downstream(db: Session, entity_type: str, entity_id: str) -> list[LineageEdge]:
    stmt = select(LineageEdge).where(
        LineageEdge.from_entity_type == entity_type, LineageEdge.from_entity_id == entity_id
    )
    return list(db.execute(stmt).scalars())
