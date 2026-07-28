from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from content_service.core.errors import ContentError
from content_service.models import Content, ContentVersion, ProcessedEvent
from content_service.schemas.content import (
    ContentCollection,
    ContentCreate,
    ContentRead,
    ContentUpdate,
    ProductMetric,
    ProductView,
)
from content_service.schemas.events import EventEnvelope
from content_service.services.identity import Identity
from content_service.services.rabbitmq import EventBusProtocol


class ContentService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        events: EventBusProtocol,
    ) -> None:
        self.sessions = sessions
        self.events = events

    async def collection(self, identity: Identity) -> ContentCollection:
        async with self.sessions() as session:
            items = await self._list(session, identity.account_id)
            drafts = sum(1 for item in items if item.status == "draft")
            approved = sum(1 for item in items if item.status == "approved")
            published = sum(1 for item in items if item.status == "published")
            view = ProductView(
                title="Content library",
                eyebrow="Content operations",
                description="Create, version, approve, and prepare generated posts before scheduling.",
                action="New draft",
                metrics=[
                    ProductMetric(label="Drafts", value=str(drafts), change="Editable by members"),
                    ProductMetric(label="Approved", value=str(approved), change="Ready to schedule"),
                    ProductMetric(label="Published", value=str(published), change="Locked history"),
                ],
                rows=[
                    {
                        "title": item.title,
                        "detail": f"{item.content_type.replace('_', ' ')} · v{item.version}",
                        "status": item.status.title(),
                    }
                    for item in items[:5]
                ],
            )
            return ContentCollection(view=view, items=[ContentRead.model_validate(item) for item in items])

    async def list_content(self, identity: Identity) -> list[ContentRead]:
        async with self.sessions() as session:
            return [
                ContentRead.model_validate(item) for item in await self._list(session, identity.account_id)
            ]

    async def create(self, payload: ContentCreate, identity: Identity) -> ContentRead:
        async with self.sessions() as session:
            item = Content(
                account_id=identity.account_id,
                created_by=identity.user_id,
                title=payload.title,
                body=payload.body,
                content_type=payload.content_type,
                image_url=payload.image_url,
                image_asset_ref=payload.image_asset_ref,
            )
            session.add(item)
            await session.flush()
            session.add(self._version(item, identity.user_id))
            await session.commit()
            await session.refresh(item)
        await self._publish("content.created", item)
        return ContentRead.model_validate(item)

    async def get(self, content_id: UUID, identity: Identity) -> ContentRead:
        async with self.sessions() as session:
            return ContentRead.model_validate(await self._get_scoped(session, content_id, identity))

    async def update(self, content_id: UUID, payload: ContentUpdate, identity: Identity) -> ContentRead:
        async with self.sessions() as session:
            item = await self._get_scoped(session, content_id, identity)
            if item.status == "published":
                raise ContentError(409, "CONTENT_LOCKED", "Published content cannot be edited")
            item.title = payload.title if payload.title is not None else item.title
            item.body = payload.body if payload.body is not None else item.body
            item.image_url = payload.image_url if payload.image_url is not None else item.image_url
            item.image_asset_ref = (
                payload.image_asset_ref if payload.image_asset_ref is not None else item.image_asset_ref
            )
            item.status = "draft"
            item.version += 1
            item.updated_at = datetime.now(UTC)
            session.add(self._version(item, identity.user_id))
            await session.commit()
            await session.refresh(item)
        await self._publish("content.updated", item)
        return ContentRead.model_validate(item)

    async def delete(self, content_id: UUID, identity: Identity) -> dict[str, str]:
        async with self.sessions() as session:
            item = await self._get_scoped(session, content_id, identity)
            if item.status == "published":
                raise ContentError(409, "CONTENT_LOCKED", "Published content cannot be deleted")
            account_id = item.account_id
            await session.delete(item)
            await session.commit()
        await self._publish_deleted(content_id, account_id)
        return {"message": "Content deleted"}

    async def approve(self, content_id: UUID, identity: Identity) -> ContentRead:
        return await self._transition(content_id, identity, "approved", lambda status: status == "draft")

    async def publish(self, content_id: UUID, identity: Identity) -> ContentRead:
        if not identity.can_publish:
            raise ContentError(
                403, "PUBLISH_PERMISSION_REQUIRED", "Owner or Admin role is required to publish"
            )
        return await self._transition(content_id, identity, "published", lambda status: status == "approved")

    async def attach_image(
        self, content_id: UUID, image_url: str, asset_ref: str, identity: Identity
    ) -> ContentRead:
        return await self.update(
            content_id,
            ContentUpdate(image_url=image_url, image_asset_ref=asset_ref),
            identity,
        )

    async def consume(self, event: dict[str, Any]) -> None:
        event_type = event.get("event_type")
        if event_type not in {"ai.generation_completed", "ai.generation_deleted"}:
            raise ContentError(400, "UNSUPPORTED_EVENT", "Content Service only consumes AI completion events")
        raw_event_id = event.get("event_id") or event.get("id")
        event_id = UUID(str(raw_event_id)) if raw_event_id else None
        if event_id is not None:
            async with self.sessions() as session:
                if await session.scalar(
                    select(ProcessedEvent.id).where(ProcessedEvent.event_id == event_id)
                ):
                    return
        if event_type == "ai.generation_deleted":
            await self._handle_generation_deleted(event)
        else:
            await self._handle_generation_completed(event)
        if event_id is not None:
            try:
                async with self.sessions() as session, session.begin():
                    session.add(ProcessedEvent(event_id=event_id, event_type=event_type))
            except IntegrityError:
                pass

    async def _handle_generation_completed(self, event: dict[str, Any]) -> None:
        payload = dict(event.get("payload") or {})
        generation_type = str(payload.get("generation_type", payload.get("content_type", "post")))
        if generation_type != "post":
            return
        account_id = UUID(str(payload["account_id"]))
        user_id = UUID(str(payload["user_id"]))
        generation_id = UUID(str(payload["generation_id"]))
        prompt = str(payload.get("prompt") or "Generated post")
        response = str(payload.get("response") or payload.get("final_response") or "")
        if not response:
            return
        title = prompt.strip().splitlines()[0][:120] or "Generated post"
        async with self.sessions() as session:
            exists = await session.scalar(
                select(Content).where(Content.source_generation_id == generation_id).limit(1)
            )
            if exists:
                return
            item = Content(
                account_id=account_id,
                created_by=user_id,
                title=title,
                body=response,
                content_type="post",
                image_url=str(payload["image_url"]) if payload.get("image_url") else None,
                image_asset_ref=str(payload["image_asset_ref"]) if payload.get("image_asset_ref") else None,
                source_generation_id=generation_id,
            )
            session.add(item)
            await session.flush()
            session.add(self._version(item, user_id))
            await session.commit()
            await session.refresh(item)
        await self._publish("content.created", item)

    async def _handle_generation_deleted(self, event: dict[str, Any]) -> None:
        payload = dict(event.get("payload") or {})
        generation_id_raw = payload.get("generation_id")
        if not generation_id_raw:
            return
        generation_id = UUID(str(generation_id_raw))
        async with self.sessions() as session:
            item = await session.scalar(
                select(Content).where(Content.source_generation_id == generation_id).limit(1)
            )
            if item is None or item.status == "published":
                return
            content_id = item.id
            account_id = item.account_id
            await session.delete(item)
            await session.commit()
        await self._publish_deleted(content_id, account_id)

    async def _transition(
        self,
        content_id: UUID,
        identity: Identity,
        target: str,
        allowed: Callable[[str], bool],
    ) -> ContentRead:
        async with self.sessions() as session:
            item = await self._get_scoped(session, content_id, identity)
            if not allowed(item.status):
                raise ContentError(
                    409,
                    "INVALID_STATUS_TRANSITION",
                    f"Cannot transition content from {item.status} to {target}",
                )
            item.status = target
            item.updated_at = datetime.now(UTC)
            if target == "published":
                item.published_at = datetime.now(UTC)
            item.version += 1
            session.add(self._version(item, identity.user_id))
            await session.commit()
            await session.refresh(item)
        await self._publish("content.updated", item)
        return ContentRead.model_validate(item)

    @staticmethod
    async def _list(session: AsyncSession, account_id: UUID) -> list[Content]:
        return list(
            (
                await session.scalars(
                    select(Content)
                    .where(Content.account_id == account_id)
                    .order_by(desc(Content.updated_at))
                    .limit(200)
                )
            ).all()
        )

    @staticmethod
    async def versions_count(session: AsyncSession, content_id: UUID) -> int:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(ContentVersion)
                .where(ContentVersion.content_id == content_id)
            )
            or 0
        )

    async def _get_scoped(self, session: AsyncSession, content_id: UUID, identity: Identity) -> Content:
        item = await session.get(Content, content_id)
        if item is None:
            raise ContentError(404, "CONTENT_NOT_FOUND", "Content item was not found")
        if not identity.is_superadmin and item.account_id != identity.account_id:
            raise ContentError(403, "ACCOUNT_SCOPE_REQUIRED", "Content belongs to another account")
        return item

    @staticmethod
    def _version(item: Content, user_id: UUID) -> ContentVersion:
        return ContentVersion(
            content_id=item.id,
            version=item.version,
            title=item.title,
            body=item.body,
            status=item.status,
            image_url=item.image_url,
            image_asset_ref=item.image_asset_ref,
            edited_by=user_id,
        )

    async def _publish(self, event_type: str, item: Content) -> None:
        await self.events.publish(
            EventEnvelope(
                event_type=event_type,
                payload={
                    "content_id": str(item.id),
                    "account_id": str(item.account_id),
                    "status": item.status,
                    "content_type": item.content_type,
                    "version": item.version,
                    "image_url": item.image_url,
                    "image_asset_ref": item.image_asset_ref,
                },
            )
        )

    async def _publish_deleted(self, content_id: UUID, account_id: UUID) -> None:
        await self.events.publish(
            EventEnvelope(
                event_type="content.deleted",
                payload={"content_id": str(content_id), "account_id": str(account_id)},
            )
        )
