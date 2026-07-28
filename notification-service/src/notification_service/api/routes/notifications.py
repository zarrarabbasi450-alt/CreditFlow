from typing import Annotated

from fastapi import APIRouter, Depends

from notification_service.api.dependencies import get_identity, get_notification_service
from notification_service.schemas.notifications import NotificationCollection
from notification_service.services.identity import Identity
from notification_service.services.notifications import NotificationService

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=NotificationCollection, operation_id="list_notifications")
async def list_notifications(
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationCollection:
    return await service.collection(identity)
