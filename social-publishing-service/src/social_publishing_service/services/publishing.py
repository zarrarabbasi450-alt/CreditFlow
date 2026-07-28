import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote_plus
from uuid import UUID

import httpx
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from social_publishing_service.core.config import Settings
from social_publishing_service.core.errors import SocialPublishingError
from social_publishing_service.models import PostMedia, ProcessedEvent, PublishJob, SocialConnection, utcnow
from social_publishing_service.schemas.events import EventEnvelope
from social_publishing_service.schemas.publishing import (
    ConnectResponse,
    DevLinkedInConnectionRequest,
    ManualLinkedInPostRequest,
    ProductMetric,
    ProductView,
    PublishContentRequest,
    PublishingCollection,
    PublishJobRead,
    SocialConnectionRead,
)
from social_publishing_service.services.content_client import ContentClientProtocol, ContentSnapshot
from social_publishing_service.services.crypto import TokenCipher
from social_publishing_service.services.identity import Identity
from social_publishing_service.services.linkedin import LinkedInClientProtocol
from social_publishing_service.services.rabbitmq import EventBusProtocol


class SocialPublishingService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        events: EventBusProtocol,
        linkedin: LinkedInClientProtocol,
        content: ContentClientProtocol,
        cipher: TokenCipher | None,
        settings: Settings,
    ) -> None:
        self.sessions = sessions
        self.events = events
        self.linkedin = linkedin
        self.content = content
        self.cipher = cipher
        self.settings = settings

    async def collection(self, identity: Identity) -> PublishingCollection:
        async with self.sessions() as session:
            connections = await self._connections(session, identity)
            jobs = await self._jobs(session, identity)
        connected = sum(1 for item in connections if item.status == "connected")
        published = sum(1 for item in jobs if item.status == "published")
        failed = sum(1 for item in jobs if item.status in {"failed", "dead_letter"})
        return PublishingCollection(
            view=ProductView(
                title="Social publishing",
                eyebrow="LinkedIn",
                description=(
                    "Connect a LinkedIn profile, publish approved content, and monitor scheduled posts."
                ),
                action="Connect LinkedIn",
                metrics=[
                    ProductMetric(
                        label="Connections", value=str(connected), change="LinkedIn profiles ready"
                    ),
                    ProductMetric(label="Published", value=str(published), change="Successful posts"),
                    ProductMetric(label="Failures", value=str(failed), change="Retry or inspect"),
                ],
                rows=[
                    {
                        "title": job.caption[:80],
                        "detail": job.linkedin_post_url or "LinkedIn publishing job",
                        "status": job.status.title(),
                    }
                    for job in jobs[:5]
                ],
            ),
            connections=[self._connection_read(item) for item in connections],
            jobs=[self._job_read(item) for item in jobs],
        )

    async def connect(self, identity: Identity) -> ConnectResponse:
        if not identity.can_manage_social:
            raise SocialPublishingError(
                403, "FORBIDDEN", "Owner or Admin role is required to connect LinkedIn"
            )
        state = secrets.token_urlsafe(32)
        async with self.sessions() as session:
            connection = SocialConnection(
                account_id=identity.account_id,
                created_by=identity.user_id,
                oauth_state=state,
                scopes=" ".join(self.settings.linkedin_scopes),
            )
            session.add(connection)
            await session.commit()
        return ConnectResponse(authorization_url=self.linkedin.authorization_url(state), state=state)

    async def connect_dev(
        self, identity: Identity, payload: DevLinkedInConnectionRequest
    ) -> SocialConnectionRead:
        if not self.settings.linkedin_dev_mode:
            raise SocialPublishingError(
                403, "DEV_MODE_DISABLED", "Manual LinkedIn profile connection is disabled"
            )
        if not identity.can_manage_social:
            raise SocialPublishingError(
                403, "FORBIDDEN", "Owner or Admin role is required to connect LinkedIn"
            )
        async with self.sessions() as session:
            connection = SocialConnection(
                account_id=identity.account_id,
                created_by=identity.user_id,
                status="connected",
                profile_urn=f"dev:{payload.profile_url}",
                profile_name=payload.profile_name,
                profile_email=None,
                encrypted_access_token=None,
                encrypted_refresh_token=None,
                scopes="dev-mode",
                connected_at=utcnow(),
            )
            session.add(connection)
            await session.commit()
            await session.refresh(connection)
        return self._connection_read(connection)

    async def callback(self, state: str, code: str) -> SocialConnectionRead:
        async with self.sessions() as session:
            connection = await session.scalar(
                select(SocialConnection).where(SocialConnection.oauth_state == state)
            )
            if connection is None:
                raise SocialPublishingError(
                    404, "OAUTH_STATE_NOT_FOUND", "LinkedIn OAuth state was not found"
                )
            if self.cipher is None:
                raise SocialPublishingError(
                    503, "ENCRYPTION_KEY_REQUIRED", "Token encryption is not configured"
                )
            tokens = await self.linkedin.exchange_code(code)
            profile = await self.linkedin.profile(tokens.access_token)
            connection.status = "connected"
            connection.profile_urn = profile.urn
            connection.profile_name = profile.name
            connection.profile_email = profile.email
            connection.encrypted_access_token = self.cipher.encrypt(tokens.access_token)
            connection.encrypted_refresh_token = (
                self.cipher.encrypt(tokens.refresh_token) if tokens.refresh_token else None
            )
            connection.token_expires_at = tokens.expires_at
            connection.refresh_expires_at = tokens.refresh_expires_at
            connection.scopes = tokens.scopes
            connection.connected_at = utcnow()
            connection.oauth_state = None
            await session.commit()
            await session.refresh(connection)
        return self._connection_read(connection)

    async def callback_failed(
        self, state: str, provider_error: str, provider_error_description: str | None
    ) -> None:
        async with self.sessions() as session:
            connection = await session.scalar(
                select(SocialConnection).where(SocialConnection.oauth_state == state)
            )
            if connection is None:
                return
            connection.status = "failed"
            connection.oauth_state = None
            connection.updated_at = utcnow()
            connection.scopes = " ".join(self.settings.linkedin_scopes)
            await session.commit()

    def callback_result_url(self, status: str, message: str) -> str:
        encoded_status = quote_plus(status)
        encoded_message = quote_plus(message)
        base_url = self.settings.frontend_url.rstrip("/")
        return f"{base_url}/publishing/linkedin?linkedin={encoded_status}&message={encoded_message}"

    async def disconnect(self, identity: Identity, connection_id: UUID) -> dict[str, str]:
        async with self.sessions() as session:
            connection = await self._connection_scoped(session, identity, connection_id)
            if not identity.can_manage_social:
                raise SocialPublishingError(403, "FORBIDDEN", "Owner or Admin role is required")
            connection.status = "revoked"
            connection.updated_at = utcnow()
            await session.commit()
        return {"message": "LinkedIn connection revoked"}

    async def publish_content(
        self, identity: Identity, payload: PublishContentRequest, bearer_token: str | None
    ) -> PublishJobRead:
        if not identity.can_publish:
            raise SocialPublishingError(403, "FORBIDDEN", "Owner or Admin role is required to publish")
        content = await self.content.get_content(payload.content_id, bearer_token)
        if not identity.is_superadmin and content.account_id != identity.account_id:
            raise SocialPublishingError(403, "ACCOUNT_SCOPE_REQUIRED", "Content belongs to another account")
        caption = payload.caption or content.body
        return await self._create_and_publish(
            identity.account_id, payload.content_id, None, payload.connection_id, caption, content
        )

    async def publish_manual(self, identity: Identity, payload: ManualLinkedInPostRequest) -> PublishJobRead:
        if not identity.can_publish:
            raise SocialPublishingError(403, "FORBIDDEN", "Owner or Admin role is required to publish")
        snapshot = ContentSnapshot(
            id=UUID(int=0),
            account_id=identity.account_id,
            title="Manual LinkedIn post",
            body=payload.caption,
            status="approved",
            image_url=payload.image_url,
            image_asset_ref=payload.image_asset_ref,
        )
        return await self._create_and_publish(
            identity.account_id, snapshot.id, None, payload.connection_id, payload.caption, snapshot
        )

    async def consume(self, event: dict[str, Any]) -> None:
        if event.get("event_type") != "content.scheduled":
            return
        raw_event_id = event.get("event_id") or event.get("id")
        event_id = UUID(str(raw_event_id)) if raw_event_id else None
        if event_id is not None:
            async with self.sessions() as session:
                if await session.scalar(
                    select(ProcessedEvent.id).where(ProcessedEvent.event_id == event_id)
                ):
                    return
        payload = dict(event.get("payload") or {})
        account_id = UUID(str(payload["account_id"]))
        content_id = UUID(str(payload["content_id"]))
        scheduled_post_id = UUID(str(payload["scheduled_post_id"]))
        content = await self.content.get_content(content_id)
        await self._create_and_publish(account_id, content_id, scheduled_post_id, None, content.body, content)
        if event_id is not None:
            try:
                async with self.sessions() as session, session.begin():
                    session.add(ProcessedEvent(event_id=event_id, event_type="content.scheduled"))
            except IntegrityError:
                pass

    async def refresh_expiring_tokens(self) -> int:
        if self.cipher is None:
            return 0
        cutoff = datetime.now(UTC) + timedelta(days=3)
        refreshed = 0
        async with self.sessions() as session:
            connections = list(
                (
                    await session.scalars(
                        select(SocialConnection).where(
                            SocialConnection.status == "connected",
                            SocialConnection.encrypted_refresh_token.is_not(None),
                            SocialConnection.token_expires_at <= cutoff,
                        )
                    )
                ).all()
            )
            for connection in connections:
                if not connection.encrypted_refresh_token:
                    continue
                tokens = await self.linkedin.refresh(self.cipher.decrypt(connection.encrypted_refresh_token))
                connection.encrypted_access_token = self.cipher.encrypt(tokens.access_token)
                if tokens.refresh_token:
                    connection.encrypted_refresh_token = self.cipher.encrypt(tokens.refresh_token)
                connection.token_expires_at = tokens.expires_at
                connection.refresh_expires_at = tokens.refresh_expires_at
                connection.updated_at = utcnow()
                refreshed += 1
            await session.commit()
        return refreshed

    async def _create_and_publish(
        self,
        account_id: UUID,
        content_id: UUID,
        scheduled_post_id: UUID | None,
        connection_id: UUID | None,
        caption: str,
        content: ContentSnapshot,
    ) -> PublishJobRead:
        async with self.sessions() as session:
            connection = await self._default_connection(session, account_id, connection_id)
            job = PublishJob(
                account_id=account_id,
                content_id=content_id,
                scheduled_post_id=scheduled_post_id,
                connection_id=connection.id,
                caption=caption,
                image_url=content.image_url,
                image_asset_ref=content.image_asset_ref,
            )
            session.add(job)
            await session.flush()
            if content.image_url:
                session.add(
                    PostMedia(
                        publish_job_id=job.id,
                        image_url=content.image_url,
                        image_asset_ref=content.image_asset_ref,
                    )
                )
            await session.commit()
            await session.refresh(job)
        await self._publish_job(job.id)
        async with self.sessions() as session:
            final = await session.get(PublishJob, job.id)
            if final is None:
                raise SocialPublishingError(404, "PUBLISH_JOB_NOT_FOUND", "Publish job was not found")
            return self._job_read(final)

    async def _publish_job(self, job_id: UUID) -> None:
        async with self.sessions() as session:
            job = await session.get(PublishJob, job_id)
            if job is None:
                return
            connection = await session.get(SocialConnection, job.connection_id) if job.connection_id else None
            if connection is None or connection.status != "connected":
                await self._fail(session, job, "No connected LinkedIn profile is available")
                return
            job.status = "publishing"
            job.attempts += 1
            await session.commit()
            try:
                result_url: str | None
                asset_urn: str | None
                if connection.profile_urn and connection.profile_urn.startswith("dev:"):
                    result_id = f"dev-linkedin-{job.id}"
                    result_url = connection.profile_urn.removeprefix("dev:")
                    asset_urn = f"dev-image-{job.id}" if job.image_url else None
                else:
                    if (
                        self.cipher is None
                        or not connection.encrypted_access_token
                        or not connection.profile_urn
                    ):
                        raise SocialPublishingError(
                            503, "LINKEDIN_TOKEN_MISSING", "LinkedIn connection token is missing"
                        )
                    result = await self.linkedin.publish(
                        self.cipher.decrypt(connection.encrypted_access_token),
                        connection.profile_urn,
                        job.caption,
                        job.image_url,
                    )
                    result_id = result.post_id
                    result_url = result.post_url
                    asset_urn = result.asset_urn
                job.status = "published"
                job.linkedin_post_id = result_id
                job.linkedin_post_url = result_url
                job.published_at = utcnow()
                job.updated_at = utcnow()
                await self._mark_media_uploaded(session, job.id, asset_urn)
                await session.commit()
                await self._emit("post.published", job)
            except httpx.HTTPError as exc:
                await self._retry_or_dead_letter(session, job, str(exc))
            except SocialPublishingError as exc:
                await self._fail(session, job, exc.message)

    async def _retry_or_dead_letter(self, session: AsyncSession, job: PublishJob, reason: str) -> None:
        if job.attempts >= self.settings.publish_max_attempts:
            job.status = "dead_letter"
            job.failure_reason = reason
            await session.commit()
            await self._emit("post.failed", job)
            return
        job.status = "failed"
        job.failure_reason = reason
        job.next_attempt_at = utcnow() + timedelta(seconds=min(300, 2**job.attempts * 10))
        await session.commit()
        await self._emit("post.failed", job)

    async def _fail(self, session: AsyncSession, job: PublishJob, reason: str) -> None:
        job.status = "failed"
        job.failure_reason = reason
        job.updated_at = utcnow()
        await self._mark_media_failed(session, job.id)
        await session.commit()
        await self._emit("post.failed", job)

    @staticmethod
    async def _mark_media_uploaded(session: AsyncSession, job_id: UUID, asset_urn: str | None) -> None:
        media = await session.scalar(select(PostMedia).where(PostMedia.publish_job_id == job_id))
        if media is None:
            return
        media.linkedin_asset_urn = asset_urn
        media.upload_status = "uploaded" if asset_urn else "not_required"

    @staticmethod
    async def _mark_media_failed(session: AsyncSession, job_id: UUID) -> None:
        media = await session.scalar(select(PostMedia).where(PostMedia.publish_job_id == job_id))
        if media is not None:
            media.upload_status = "failed"

    async def _emit(self, event_type: str, job: PublishJob) -> None:
        await self.events.publish(
            EventEnvelope(
                event_type=event_type,
                payload={
                    "publish_job_id": str(job.id),
                    "account_id": str(job.account_id),
                    "content_id": str(job.content_id),
                    "scheduled_post_id": str(job.scheduled_post_id) if job.scheduled_post_id else None,
                    "linkedin_post_id": job.linkedin_post_id,
                    "linkedin_post_url": job.linkedin_post_url,
                    "status": job.status,
                    "reason": job.failure_reason,
                },
            )
        )

    @staticmethod
    async def _connections(session: AsyncSession, identity: Identity) -> list[SocialConnection]:
        statement = select(SocialConnection).order_by(desc(SocialConnection.created_at)).limit(50)
        if not identity.is_superadmin:
            statement = statement.where(SocialConnection.account_id == identity.account_id)
        return list((await session.scalars(statement)).all())

    @staticmethod
    async def _jobs(session: AsyncSession, identity: Identity) -> list[PublishJob]:
        statement = select(PublishJob).order_by(desc(PublishJob.created_at)).limit(100)
        if not identity.is_superadmin:
            statement = statement.where(PublishJob.account_id == identity.account_id)
        return list((await session.scalars(statement)).all())

    async def _connection_scoped(
        self, session: AsyncSession, identity: Identity, connection_id: UUID
    ) -> SocialConnection:
        connection = await session.get(SocialConnection, connection_id)
        if connection is None:
            raise SocialPublishingError(404, "CONNECTION_NOT_FOUND", "LinkedIn connection was not found")
        if not identity.is_superadmin and connection.account_id != identity.account_id:
            raise SocialPublishingError(
                403, "ACCOUNT_SCOPE_REQUIRED", "LinkedIn connection belongs to another account"
            )
        return connection

    async def _default_connection(
        self, session: AsyncSession, account_id: UUID, connection_id: UUID | None
    ) -> SocialConnection:
        statement = select(SocialConnection).where(
            SocialConnection.account_id == account_id,
            SocialConnection.status == "connected",
        )
        if connection_id:
            statement = statement.where(SocialConnection.id == connection_id)
        connection = await session.scalar(statement.order_by(desc(SocialConnection.connected_at)).limit(1))
        if connection is None:
            raise SocialPublishingError(409, "LINKEDIN_NOT_CONNECTED", "Connect LinkedIn before publishing")
        return connection

    @staticmethod
    def _connection_read(item: SocialConnection) -> SocialConnectionRead:
        return SocialConnectionRead(
            id=item.id,
            account_id=item.account_id,
            provider=item.provider,
            profile_name=item.profile_name or "LinkedIn profile",
            profile_urn=item.profile_urn,
            status=item.status,
            connected_at=item.connected_at,
        )

    @staticmethod
    def _job_read(item: PublishJob) -> PublishJobRead:
        return PublishJobRead(
            id=item.id,
            account_id=item.account_id,
            content_id=item.content_id,
            scheduled_post_id=item.scheduled_post_id,
            connection_id=item.connection_id,
            status=item.status,
            caption=item.caption,
            image_url=item.image_url,
            linkedin_post_id=item.linkedin_post_id,
            linkedin_post_url=item.linkedin_post_url,
            failure_reason=item.failure_reason,
            attempts=item.attempts,
            created_at=item.created_at,
            published_at=item.published_at,
        )
