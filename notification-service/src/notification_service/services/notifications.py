from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from notification_service.core.errors import NotificationError
from notification_service.models import NotificationLog, ProcessedEvent
from notification_service.schemas.events import EventEnvelope
from notification_service.schemas.notifications import (
    ActivityRow,
    NotificationCollection,
    NotificationItem,
    ProductMetric,
    ProductView,
)
from notification_service.services.directory import DirectoryClientProtocol
from notification_service.services.email import EmailClientProtocol
from notification_service.services.identity import Identity
from notification_service.services.rabbitmq import EventBusProtocol
from notification_service.services.slack import SlackClientProtocol
from notification_service.services.templates import render_email, render_slack_alert

_LABELS: dict[str, tuple[str, str]] = {
    "user.registered": ("Account", "Verification email"),
    "user.password_reset_requested": ("Account", "Password reset code"),
    "member.invited": ("Account", "Team invite sent"),
    "member.joined": ("Account", "New team member"),
    "invoice.paid": ("Credits", "Payment receipt"),
    "payment.failed": ("Credits", "Payment failed alert"),
    "post.published": ("Publishing", "LinkedIn post published"),
    "post.failed": ("Publishing", "LinkedIn post failed"),
    "usage.threshold_reached": ("Account", "Usage threshold alert"),
}


class NotificationService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        events: EventBusProtocol,
        email: EmailClientProtocol,
        slack: SlackClientProtocol,
        directory: DirectoryClientProtocol,
        frontend_url: str,
    ) -> None:
        self.sessions = sessions
        self.events = events
        self.email = email
        self.slack = slack
        self.directory = directory
        self.frontend_url = frontend_url

    async def collection(self, identity: Identity) -> NotificationCollection:
        async with self.sessions() as session:
            logs = await self._list(session, identity)
        sent = sum(1 for log in logs if log.status == "sent")
        failed = sum(1 for log in logs if log.status == "failed")
        view = ProductView(
            title="Notifications",
            eyebrow="Delivery log",
            description="Every email and alert the platform has sent, for auditing.",
            action="Refresh",
            metrics=[
                ProductMetric(label="Sent", value=str(sent), change="Delivered successfully"),
                ProductMetric(label="Failed", value=str(failed), change="Needs attention"),
                ProductMetric(label="Total", value=str(len(logs)), change="All channels"),
            ],
            rows=[
                ActivityRow(
                    title=self._item(log).title, detail=self._item(log).detail, status=log.status.title()
                )
                for log in logs[:5]
            ],
        )
        return NotificationCollection(view=view, items=[self._item(log) for log in logs])

    async def consume(self, event: dict[str, Any]) -> None:
        event_type = str(event.get("event_type") or "")
        if event_type not in _LABELS:
            return
        raw_event_id = event.get("event_id") or event.get("id")
        event_id = self._as_uuid(raw_event_id)
        if event_id is not None:
            async with self.sessions() as session:
                if await session.scalar(
                    select(ProcessedEvent.id).where(ProcessedEvent.event_id == event_id)
                ):
                    return
        payload = dict(event.get("payload") or {})
        correlation_id = event.get("correlation_id")
        await self._handle(event_type, payload, correlation_id)
        if event_id is not None:
            try:
                async with self.sessions() as session, session.begin():
                    session.add(ProcessedEvent(event_id=event_id, event_type=event_type))
            except IntegrityError:
                pass

    async def _handle(self, event_type: str, payload: dict[str, Any], correlation_id: str | None) -> None:
        account_id = self._as_uuid(payload.get("account_id"))
        user_id = self._as_uuid(payload.get("user_id"))
        recipient = await self._resolve_recipient(event_type, payload)
        # member.joined has no email template by design (it's logged for the audit
        # feed, not emailed); every other consumed event type has one.
        content = render_email(event_type, payload, self.frontend_url) if recipient else None
        no_template_by_design = event_type == "member.joined"

        if content is None or recipient is None:
            error = None if no_template_by_design else "recipient email could not be resolved"
            await self._record(
                account_id, user_id, event_type, "email", recipient, None, "skipped", None, None, error,
                correlation_id,
            )
        else:
            try:
                result = await self.email.send(recipient, content.subject, content.html, content.text)
                await self._record(
                    account_id,
                    user_id,
                    event_type,
                    "email",
                    recipient,
                    content.subject,
                    "sent",
                    "resend",
                    result.provider_message_id,
                    None,
                    correlation_id,
                )
                await self._emit_sent(event_type, account_id, "email", recipient)
            except NotificationError as exc:
                await self._record(
                    account_id,
                    user_id,
                    event_type,
                    "email",
                    recipient,
                    content.subject,
                    "failed",
                    "resend",
                    None,
                    exc.message,
                    correlation_id,
                )

        slack_text = render_slack_alert(event_type, payload)
        if slack_text:
            try:
                await self.slack.send(slack_text)
                await self._record(
                    account_id, user_id, event_type, "slack", "ops-alerts", None, "sent", "slack", None, None,
                    correlation_id,
                )
                await self._emit_sent(event_type, account_id, "slack", "ops-alerts")
            except NotificationError as exc:
                await self._record(
                    account_id, user_id, event_type, "slack", "ops-alerts", None, "failed", "slack", None,
                    exc.message, correlation_id,
                )

    async def _resolve_recipient(self, event_type: str, payload: dict[str, Any]) -> str | None:
        if event_type in {"user.registered", "member.invited", "user.password_reset_requested"}:
            return str(payload.get("email")) if payload.get("email") else None
        if event_type == "member.joined":
            user_id = self._as_uuid(payload.get("user_id"))
            return await self.directory.get_user_email(user_id) if user_id else None
        account_id = self._as_uuid(payload.get("account_id"))
        return await self.directory.get_account_owner_email(account_id) if account_id else None

    async def _record(
        self,
        account_id: UUID | None,
        user_id: UUID | None,
        event_type: str,
        channel: str,
        recipient: str | None,
        subject: str | None,
        status: str,
        provider: str | None,
        provider_message_id: str | None,
        error: str | None,
        correlation_id: str | None,
    ) -> None:
        async with self.sessions() as session:
            session.add(
                NotificationLog(
                    account_id=account_id,
                    user_id=user_id,
                    event_type=event_type,
                    channel=channel,
                    recipient=recipient,
                    subject=subject,
                    status=status,
                    provider=provider,
                    provider_message_id=provider_message_id,
                    error=error,
                    correlation_id=correlation_id,
                )
            )
            await session.commit()

    async def _emit_sent(
        self, event_type: str, account_id: UUID | None, channel: str, recipient: str
    ) -> None:
        await self.events.publish(
            EventEnvelope(
                event_type="notification.sent",
                payload={
                    "source_event_type": event_type,
                    "account_id": str(account_id) if account_id else None,
                    "channel": channel,
                    "recipient": recipient,
                },
            )
        )

    @staticmethod
    async def _list(session: AsyncSession, identity: Identity) -> list[NotificationLog]:
        statement = select(NotificationLog).order_by(desc(NotificationLog.created_at)).limit(100)
        if not identity.is_superadmin:
            statement = statement.where(NotificationLog.account_id == identity.account_id)
        return list((await session.scalars(statement)).all())

    @staticmethod
    def _item(log: NotificationLog) -> NotificationItem:
        category, label = _LABELS.get(log.event_type, ("Account", log.event_type))
        detail = (
            f"{log.recipient} · {log.status}" if log.recipient else f"{log.channel} · {log.status}"
        )
        return NotificationItem(
            id=log.id,
            accountId=log.account_id,
            title=label,
            detail=detail,
            category=category,  # type: ignore[arg-type]
            status="Read" if log.status == "sent" else "Unread",
            createdAt=log.created_at,
        )

    @staticmethod
    def _as_uuid(value: Any) -> UUID | None:
        if not value:
            return None
        try:
            return UUID(str(value))
        except ValueError:
            return None
