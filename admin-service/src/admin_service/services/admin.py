from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from admin_service.core.errors import AdminError
from admin_service.models import AuditLog
from admin_service.schemas.admin import (
    AccountSummary,
    ActivityRow,
    AdminOverview,
    AuditEntry,
    ProductView,
    SessionItem,
)
from admin_service.services.directory import DirectoryClientProtocol
from admin_service.services.health import HealthCheckerProtocol
from admin_service.services.identity import Identity
from admin_service.services.redis import SessionDirectoryProtocol


class AdminService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        session_directory: SessionDirectoryProtocol,
        directory: DirectoryClientProtocol,
        health: HealthCheckerProtocol,
    ) -> None:
        self.sessions = sessions
        self.session_directory = session_directory
        self.directory = directory
        self.health = health

    def _scope(self, identity: Identity, account_id: UUID | None) -> UUID | None:
        """SuperAdmin may pass any account_id (None = all accounts). Everyone else
        is restricted to their own account_id regardless of what was requested."""
        if identity.is_superadmin:
            return account_id
        if account_id is not None and account_id != identity.account_id:
            raise AdminError(403, "ACCOUNT_ACCESS_DENIED", "You may only view your own account")
        return identity.account_id

    async def list_sessions(self, identity: Identity, account_id: UUID | None) -> list[SessionItem]:
        return await self.session_directory.list_sessions(self._scope(identity, account_id))

    async def revoke_session(self, identity: Identity, jti: str) -> None:
        session = await self.session_directory.get_session(jti)
        if session is None:
            raise AdminError(404, "SESSION_NOT_FOUND", "Session was not found")
        if not identity.is_superadmin and session.account_id != identity.account_id:
            raise AdminError(403, "ACCOUNT_ACCESS_DENIED", "You may only revoke your own account's sessions")
        await self.session_directory.revoke_session(jti)

    async def account_summary(self, identity: Identity, account_id: UUID) -> AccountSummary:
        self._scope(identity, account_id)
        return await self.directory.get_account_summary(account_id)

    async def list_audit(
        self, identity: Identity, account_id: UUID | None, limit: int = 100
    ) -> list[AuditEntry]:
        scoped = self._scope(identity, account_id)
        async with self.sessions() as session:
            statement = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
            if scoped is not None:
                statement = statement.where(AuditLog.account_id == scoped)
            rows = (await session.scalars(statement)).all()
        return [self._entry(row) for row in rows]

    async def overview(self, identity: Identity) -> AdminOverview:
        audit = await self.list_audit(identity, None, limit=20)
        health = await self.health.check_all()
        view = ProductView(
            title="Platform operations",
            eyebrow="Admin console",
            description="Sessions, per-account health, and the platform audit trail.",
            action="Refresh",
            metrics=[],
            rows=[
                ActivityRow(title=entry.action, detail=entry.resource, status=entry.createdAt.isoformat())
                for entry in audit[:5]
            ],
        )
        return AdminOverview(view=view, health=health, audit=audit, flags=[])

    async def consume(self, event: dict[str, Any]) -> None:
        event_type = str(event.get("event_type") or "")
        if not event_type:
            return
        payload = dict(event.get("payload") or {})
        event_id = event.get("event_id")
        correlation_id = event.get("correlation_id")
        account_id = self._as_uuid(payload.get("account_id"))
        actor_id = self._as_uuid(payload.get("user_id") or payload.get("actor_id"))
        resource = event_type.split(".", 1)[0] if "." in event_type else event_type
        try:
            async with self.sessions() as session, session.begin():
                session.add(
                    AuditLog(
                        event_id=self._as_uuid(event_id),
                        account_id=account_id,
                        actor_id=actor_id,
                        action=event_type,
                        resource=resource,
                        correlation_id=str(correlation_id) if correlation_id else None,
                        payload=payload,
                    )
                )
        except IntegrityError:
            pass

    @staticmethod
    def _entry(row: AuditLog) -> AuditEntry:
        return AuditEntry(
            id=row.id,
            actorId=row.actor_id,
            accountId=row.account_id,
            action=row.action,
            resource=row.resource,
            createdAt=row.created_at,
            correlationId=row.correlation_id,
        )

    @staticmethod
    def _as_uuid(value: Any) -> UUID | None:
        if not value:
            return None
        try:
            return UUID(str(value))
        except ValueError:
            return None
