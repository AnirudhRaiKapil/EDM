import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from app.config import settings

logger = logging.getLogger("edm.events")

_subscribers: dict[str, list[Callable[[dict], None]]] = defaultdict(list)


def subscribe(topic: str, handler: Callable[[dict], None]) -> None:
    """In-process subscription. Swapped for a real Kafka consumer group per ADR-0003
    once EVENT_BUS=kafka; topic names and envelope shape do not change."""
    _subscribers[topic].append(handler)


def publish(topic: str, payload: dict) -> None:
    envelope = {
        "eventId": str(uuid4()),
        "topic": topic,
        "occurredAt": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    logger.info("event published topic=%s payload=%s", topic, payload)
    if settings.event_bus == "kafka":
        logger.warning(
            "EVENT_BUS=kafka requested but no Kafka producer is wired yet; "
            "falling back to in-process delivery for topic=%s", topic,
        )
    for handler in _subscribers.get(topic, []):
        handler(envelope)
