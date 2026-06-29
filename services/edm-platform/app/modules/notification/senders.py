"""Channel senders for edm-notification (ADR-0011).

Both senders take an injectable client/SMTP-class specifically so tests can verify
real request-building logic without making a real network call or sending a real
email -- the same pattern app/modules/ingestion/rest_client.py already uses.

Delivery failures are caught and logged by the caller (notification/service.py), never
raised -- a webhook endpoint being down or an SMTP server rejecting a message must
never fail the alert creation that triggered the notification attempt.
"""

import logging
import smtplib
from email.message import EmailMessage

import httpx

from app.config import settings
from app.modules.alerting.models import Alert
from app.modules.notification.models import NotificationChannel

logger = logging.getLogger("edm.notification")


def send_webhook(channel: NotificationChannel, alert: Alert, client: httpx.Client | None = None) -> None:
    url = channel.config.get("url")
    if not url:
        raise ValueError("webhook channel is missing a 'url' in its config")
    payload = {
        "alert_id": alert.id,
        "project_id": alert.project_id,
        "severity": alert.severity,
        "message": alert.message,
        "source_entity_type": alert.source_entity_type,
        "source_entity_id": alert.source_entity_id,
    }
    owns_client = client is None
    client = client or httpx.Client(timeout=settings.webhook_timeout_seconds)
    try:
        response = client.post(url, json=payload)
        response.raise_for_status()
    finally:
        if owns_client:
            client.close()


def send_slack(channel: NotificationChannel, alert: Alert, client: httpx.Client | None = None) -> None:
    url = channel.config.get("url")
    if not url:
        raise ValueError("slack channel is missing a 'url' in its config")
    payload = {"text": f"[{alert.severity.upper()}] {alert.message}"}
    owns_client = client is None
    client = client or httpx.Client(timeout=settings.webhook_timeout_seconds)
    try:
        response = client.post(url, json=payload)
        response.raise_for_status()
    finally:
        if owns_client:
            client.close()


_TEAMS_THEME_COLORS = {"critical": "FF0000", "warning": "FFA500", "info": "0078D7"}


def send_teams(channel: NotificationChannel, alert: Alert, client: httpx.Client | None = None) -> None:
    url = channel.config.get("url")
    if not url:
        raise ValueError("teams channel is missing a 'url' in its config")
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "summary": f"EDM Platform {alert.severity} alert",
        "themeColor": _TEAMS_THEME_COLORS.get(alert.severity, "0078D7"),
        "title": f"[{alert.severity.upper()}] EDM Platform alert",
        "text": alert.message,
    }
    owns_client = client is None
    client = client or httpx.Client(timeout=settings.webhook_timeout_seconds)
    try:
        response = client.post(url, json=payload)
        response.raise_for_status()
    finally:
        if owns_client:
            client.close()


def send_email(channel: NotificationChannel, alert: Alert, smtp_cls: type = smtplib.SMTP) -> None:
    to_address = channel.config.get("to_address")
    if not to_address:
        raise ValueError("email channel is missing a 'to_address' in its config")
    if not settings.smtp_host:
        # Best-effort by design (see ADR-0011): no real SMTP server has been
        # configured, so there's nothing to deliver through. The channel and the
        # attempt both still exist; this just means delivery never leaves this
        # process. Not an error -- a $0 deployment with no mail server configured
        # is an expected, supported state, not a misconfiguration to alarm on.
        logger.info("email channel %s has no SMTP_HOST configured; skipping delivery", channel.id)
        return

    message = EmailMessage()
    message["Subject"] = f"[EDM Platform] {alert.severity.upper()} alert"
    message["From"] = settings.smtp_from_address
    message["To"] = to_address
    message.set_content(alert.message)

    with smtp_cls(settings.smtp_host, settings.smtp_port, timeout=settings.webhook_timeout_seconds) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
