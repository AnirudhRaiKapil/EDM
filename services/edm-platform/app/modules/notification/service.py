import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.alerting.models import Alert
from app.modules.core.exceptions import NotFoundError, ValidationFailedError
from app.modules.notification import senders
from app.modules.notification.models import SUPPORTED_CHANNEL_TYPES, NotificationChannel

logger = logging.getLogger("edm.notification")

_SENDERS = {
    "webhook": senders.send_webhook,
    "email": senders.send_email,
}


def create_channel(
    db: Session, owner_id: str, project_id: str, channel_type: str, config: dict
) -> NotificationChannel:
    if channel_type not in SUPPORTED_CHANNEL_TYPES:
        raise ValidationFailedError(
            f"unsupported channel type '{channel_type}'; choose from {SUPPORTED_CHANNEL_TYPES}"
        )
    if channel_type == "webhook" and not config.get("url"):
        raise ValidationFailedError("webhook channel requires a 'url' in config")
    if channel_type == "email" and not config.get("to_address"):
        raise ValidationFailedError("email channel requires a 'to_address' in config")

    channel = NotificationChannel(
        project_id=project_id, type=channel_type, config=config, owner_id=owner_id
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


def list_channels(db: Session, project_id: str) -> list[NotificationChannel]:
    return list(
        db.execute(
            select(NotificationChannel).where(NotificationChannel.project_id == project_id)
        ).scalars()
    )


def get_channel(db: Session, channel_id: str) -> NotificationChannel:
    channel = db.get(NotificationChannel, channel_id)
    if channel is None:
        raise NotFoundError(f"notification channel '{channel_id}' not found")
    return channel


def delete_channel(db: Session, channel: NotificationChannel) -> None:
    db.delete(channel)
    db.commit()


def dispatch_alert(db: Session, alert: Alert) -> None:
    """Best-effort fan-out to every enabled channel on the alert's project. A channel
    failing to deliver (network error, bad SMTP creds, 4xx/5xx from a webhook) is
    logged and skipped -- it must never prevent the alert itself from existing, and
    one channel's failure must never stop the others from being tried."""
    channels = [c for c in list_channels(db, alert.project_id) if c.enabled]
    for channel in channels:
        send = _SENDERS.get(channel.type)
        if send is None:
            continue
        try:
            send(channel, alert)
        except Exception:
            logger.exception(
                "notification delivery failed for channel %s (type=%s) on alert %s",
                channel.id,
                channel.type,
                alert.id,
            )
