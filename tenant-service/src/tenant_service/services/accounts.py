import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tenant_service.core.errors import TenantError
from tenant_service.models import Account, AccountMember, AccountType, Invite, MemberRole
from tenant_service.schemas.accounts import AccountCreate, InviteCreate
from tenant_service.services.identity import Identity
from tenant_service.services.rabbitmq import EventPublisherProtocol


class AccountService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        publisher: EventPublisherProtocol | None = None,
    ) -> None:
        self.sessions = sessions
        self.publisher = publisher

    async def create(self, payload: AccountCreate, creator_user_id: UUID) -> Account:
        account = Account(
            name=payload.name,
            slug=payload.slug,
            type=payload.type,
            plan_tier=payload.plan_tier,
            seat_count=payload.seat_count,
        )
        try:
            async with self.sessions() as session, session.begin():
                session.add(account)
                await session.flush()
                session.add(
                    AccountMember(
                        account_id=account.id,
                        user_id=creator_user_id,
                        role=MemberRole.OWNER,
                    )
                )
        except IntegrityError as exc:
            raise TenantError(409, "ACCOUNT_SLUG_EXISTS", "An account with this slug already exists") from exc
        await self._publish(
            "account.created",
            {"account_id": str(account.id), "name": account.name, "type": account.type},
        )
        return account

    async def handle_user_registered(self, payload: dict[str, Any]) -> None:
        try:
            user_id = UUID(str(payload["user_id"]))
            email = str(payload["email"]).strip().lower()
        except (KeyError, ValueError) as exc:
            raise TenantError(400, "INVALID_USER_EVENT", "user.registered event is invalid") from exc
        created = False
        async with self.sessions() as session, session.begin():
            account = await session.get(Account, user_id)
            if account is None:
                local_name = email.split("@", 1)[0]
                display_name = local_name.replace(".", " ").replace("_", " ").strip().title() or "Personal"
                slug_base = re.sub(r"[^a-z0-9]+", "-", local_name).strip("-") or "account"
                account = Account(
                    id=user_id,
                    name=display_name,
                    slug=f"{slug_base}-{user_id.hex[:8]}",
                    type=AccountType.INDIVIDUAL,
                    status="active",
                )
                session.add(account)
                session.add(
                    AccountMember(
                        account_id=user_id,
                        user_id=user_id,
                        role=MemberRole.OWNER,
                    )
                )
                created = True
        if created:
            await self._publish(
                "account.created",
                {"account_id": str(account.id), "name": account.name, "type": account.type},
            )

    async def get(self, account_id: UUID, actor: Identity) -> Account:
        async with self.sessions() as session:
            if not actor.is_superadmin:
                await self._membership(session, account_id, actor.user_id)
            account = await session.get(Account, account_id)
            if account is None:
                raise TenantError(404, "ACCOUNT_NOT_FOUND", "Account was not found")
            return account

    async def list_for_user(self, actor: Identity, *, all_accounts: bool = False) -> list[Account]:
        async with self.sessions() as session:
            if all_accounts:
                if not actor.is_superadmin:
                    raise TenantError(403, "SUPERADMIN_REQUIRED", "SuperAdmin access is required")
                return list((await session.scalars(select(Account).order_by(Account.created_at))).all())
            result = await session.scalars(
                select(Account)
                .join(AccountMember, AccountMember.account_id == Account.id)
                .where(AccountMember.user_id == actor.user_id)
                .order_by(Account.created_at)
            )
            return list(result.all())

    async def list_members(self, account_id: UUID, actor: Identity) -> list[AccountMember]:
        async with self.sessions() as session:
            actor_member = None
            if not actor.is_superadmin:
                actor_member = await self._membership(session, account_id, actor.user_id)
            if actor_member is not None and actor_member.role == MemberRole.MEMBER:
                return [actor_member]
            result = await session.scalars(
                select(AccountMember)
                .where(AccountMember.account_id == account_id)
                .order_by(AccountMember.created_at)
            )
            return list(result.all())

    async def get_membership(self, account_id: UUID, actor: Identity) -> AccountMember:
        async with self.sessions() as session:
            return await self._membership(session, account_id, actor.user_id)

    async def update_role(
        self, account_id: UUID, user_id: UUID, role: MemberRole, actor: Identity
    ) -> AccountMember:
        async with self.sessions() as session, session.begin():
            manager = await self._manager(session, account_id, actor)
            member = await self._membership(session, account_id, user_id)
            await self._authorize_role_change(session, account_id, member, role, manager, actor)
            previous_role = member.role
            member.role = role
        await self._publish(
            "member.role_updated",
            {
                "account_id": str(account_id),
                "change": "member.role",
                "user_id": str(user_id),
                "previous_role": previous_role,
                "role": role,
            },
        )
        return member

    async def remove_member(self, account_id: UUID, user_id: UUID, actor: Identity) -> None:
        async with self.sessions() as session, session.begin():
            manager = await self._manager(session, account_id, actor)
            member = await self._membership(session, account_id, user_id)
            await self._authorize_removal(session, account_id, member, manager, actor)
            removed_role = member.role
            await session.delete(member)
        await self._publish(
            "member.removed",
            {
                "account_id": str(account_id),
                "change": "member.removed",
                "user_id": str(user_id),
                "role": removed_role,
            },
        )

    async def invite(self, account_id: UUID, payload: InviteCreate, actor: Identity) -> Invite:
        raw_token = secrets.token_urlsafe(32)
        invitation = Invite(
            account_id=account_id,
            email=str(payload.email).strip().lower(),
            token_hash=self.hash_token(raw_token),
            role=payload.role,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        async with self.sessions() as session, session.begin():
            manager = await self._manager(session, account_id, actor)
            if (
                not actor.is_superadmin
                and manager is not None
                and manager.role == MemberRole.ADMIN
                and payload.role != MemberRole.MEMBER
            ):
                raise TenantError(403, "ROLE_ESCALATION_FORBIDDEN", "Admins may invite Members only")
            session.add(invitation)
        await self._publish(
            "member.invited",
            {
                "account_id": str(account_id),
                "email": invitation.email,
                "role": invitation.role,
                "invite_token": raw_token,
            },
        )
        return invitation

    async def accept_invite(self, raw_token: str, user_id: UUID) -> AccountMember:
        now = datetime.now(UTC)
        async with self.sessions() as session, session.begin():
            invitation = await session.scalar(
                select(Invite).where(Invite.token_hash == self.hash_token(raw_token)).with_for_update()
            )
            if invitation is None or invitation.accepted_at is not None:
                raise TenantError(400, "INVALID_INVITE", "Invitation is invalid or already accepted")
            expires_at = (
                invitation.expires_at.replace(tzinfo=UTC)
                if invitation.expires_at.tzinfo is None
                else invitation.expires_at
            )
            if expires_at <= now:
                raise TenantError(400, "INVITE_EXPIRED", "Invitation has expired")
            existing = await session.scalar(
                select(AccountMember).where(
                    AccountMember.account_id == invitation.account_id,
                    AccountMember.user_id == user_id,
                )
            )
            if existing is not None:
                raise TenantError(409, "MEMBER_ALREADY_EXISTS", "User is already an account member")
            member = AccountMember(
                account_id=invitation.account_id,
                user_id=user_id,
                role=invitation.role,
            )
            session.add(member)
            invitation.accepted_at = now
            await session.flush()
        await self._publish(
            "member.joined",
            {
                "account_id": str(member.account_id),
                "user_id": str(user_id),
                "role": member.role,
            },
        )
        return member

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    async def _publish(self, routing_key: str, payload: dict[str, Any]) -> None:
        if self.publisher is not None:
            await self.publisher.publish(routing_key, payload)

    @staticmethod
    async def _membership(session: AsyncSession, account_id: UUID, user_id: UUID) -> AccountMember:
        member = await session.scalar(
            select(AccountMember).where(
                AccountMember.account_id == account_id,
                AccountMember.user_id == user_id,
            )
        )
        if member is None:
            raise TenantError(404, "MEMBER_NOT_FOUND", "Account member was not found")
        return member

    async def _manager(
        self, session: AsyncSession, account_id: UUID, actor: Identity
    ) -> AccountMember | None:
        if actor.is_superadmin:
            return None
        member = await self._membership(session, account_id, actor.user_id)
        if member.role not in {MemberRole.OWNER, MemberRole.ADMIN}:
            raise TenantError(403, "INSUFFICIENT_ROLE", "Owner or admin role is required")
        return member

    @staticmethod
    async def _owner_count(session: AsyncSession, account_id: UUID) -> int:
        values = await session.scalars(
            select(AccountMember.id).where(
                AccountMember.account_id == account_id,
                AccountMember.role == MemberRole.OWNER,
            )
        )
        return len(list(values.all()))

    async def _authorize_role_change(
        self,
        session: AsyncSession,
        account_id: UUID,
        target: AccountMember,
        new_role: MemberRole,
        manager: AccountMember | None,
        actor: Identity,
    ) -> None:
        if actor.is_superadmin:
            return
        if manager is None:
            raise TenantError(403, "INSUFFICIENT_ROLE", "Owner or admin role is required")
        if manager.role == MemberRole.ADMIN and target.role != MemberRole.MEMBER:
            raise TenantError(403, "ROLE_ESCALATION_FORBIDDEN", "Admins may change Members only")
        if new_role == MemberRole.OWNER and manager.role != MemberRole.OWNER:
            raise TenantError(403, "OWNER_REQUIRED", "Only an Owner may assign the Owner role")
        if (
            target.role == MemberRole.OWNER
            and new_role != MemberRole.OWNER
            and await self._owner_count(session, account_id) <= 1
        ):
            raise TenantError(409, "LAST_OWNER_REQUIRED", "An account must retain at least one Owner")

    async def _authorize_removal(
        self,
        session: AsyncSession,
        account_id: UUID,
        target: AccountMember,
        manager: AccountMember | None,
        actor: Identity,
    ) -> None:
        if actor.is_superadmin:
            return
        if manager is None:
            raise TenantError(403, "INSUFFICIENT_ROLE", "Owner or admin role is required")
        if manager.role == MemberRole.ADMIN and target.role != MemberRole.MEMBER:
            raise TenantError(403, "ROLE_ESCALATION_FORBIDDEN", "Admins may remove Members only")
        if target.role == MemberRole.OWNER and await self._owner_count(session, account_id) <= 1:
            raise TenantError(409, "LAST_OWNER_REQUIRED", "An account must retain at least one Owner")
