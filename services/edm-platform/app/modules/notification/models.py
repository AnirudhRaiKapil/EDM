from sqlalchemy import JSON, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.modules.core.models import OwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin

SUPPORTED_CHANNEL_TYPES = ["webhook", "email"]


class NotificationChannel(Base, UUIDPrimaryKeyMixin, TimestampMixin, OwnedMixin):
    """Not in the original 00-vision-and-requirements.md module list as a built
    feature -- edm-alerting (ADR-0008) explicitly scoped real delivery channels out
    ("not implemented in the MVP... alerts are in-app/API-only until edm-notification
    exists"). This is that module. See ADR-0011."""

    __tablename__ = "notification_channels"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspace_projects.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
