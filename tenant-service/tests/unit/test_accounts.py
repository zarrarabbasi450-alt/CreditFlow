from collections.abc import AsyncIterator
from typing import Protocol, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from tenant_service.core.errors import TenantError
from tenant_service.models import AccountMember, Base, Invite, MemberRole
from tenant_service.schemas.accounts import AccountCreate, InviteCreate
from tenant_service.services.accounts import AccountService
from tenant_service.services.identity import Identity
from tenant_service.services.rabbitmq import InMemoryEventBus


class SQLiteConnection(Protocol):
    def execute(self, statement: str) -> object: ...


def actor(user_id: UUID, account_id: UUID, role: MemberRole, platform_role: str | None = None) -> Identity:
    return Identity(user_id, account_id, role, platform_role)


@pytest.fixture
async def accounts() -> AsyncIterator[AccountService]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine.sync_engine, "connect")
    def attach_tenant(dbapi_connection: object, _connection_record: object) -> None:
        cast(SQLiteConnection, dbapi_connection).execute("ATTACH DATABASE ':memory:' AS tenant")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield AccountService(sessions, InMemoryEventBus())
    await engine.dispose()


@pytest.mark.asyncio
async def test_account_creation_membership_and_listing(accounts: AccountService) -> None:
    owner_id = uuid4()
    account = await accounts.create(
        AccountCreate(name="Orion Team", slug="orion-team", type="team"), owner_id
    )
    assert account.name == "Orion Team" and account.type == "team"
    owner = actor(owner_id, account.id, MemberRole.OWNER)
    assert (await accounts.get(account.id, owner)).id == account.id
    assert [item.id for item in await accounts.list_for_user(owner)] == [account.id]

    members = await accounts.list_members(account.id, owner)
    assert len(members) == 1
    assert members[0].user_id == owner_id and members[0].role == MemberRole.OWNER
    publisher = cast(InMemoryEventBus, accounts.publisher)
    assert publisher.events[-1][0] == "account.created"

    with pytest.raises(TenantError) as duplicate:
        await accounts.create(AccountCreate(name="Duplicate", slug="orion-team", type="team"), uuid4())
    assert duplicate.value.code == "ACCOUNT_SLUG_EXISTS"


@pytest.mark.asyncio
async def test_role_update_validation_and_member_removal(accounts: AccountService) -> None:
    owner_id, member_id = uuid4(), uuid4()
    account = await accounts.create(AccountCreate(name="Team", slug="role-team", type="team"), owner_id)
    async with accounts.sessions() as session, session.begin():
        session.add(AccountMember(account_id=account.id, user_id=member_id, role=MemberRole.MEMBER))

    owner = actor(owner_id, account.id, MemberRole.OWNER)
    member = actor(member_id, account.id, MemberRole.MEMBER)
    updated = await accounts.update_role(account.id, member_id, MemberRole.ADMIN, owner)
    assert updated.role == MemberRole.ADMIN
    await accounts.update_role(account.id, member_id, MemberRole.MEMBER, owner)

    with pytest.raises(TenantError) as forbidden:
        await accounts.update_role(account.id, owner_id, MemberRole.MEMBER, member)
    assert forbidden.value.code == "INSUFFICIENT_ROLE"

    await accounts.remove_member(account.id, member_id, owner)
    async with accounts.sessions() as session:
        removed = await session.scalar(
            select(AccountMember).where(
                AccountMember.account_id == account.id, AccountMember.user_id == member_id
            )
        )
    assert removed is None

    with pytest.raises(TenantError) as missing:
        await accounts.remove_member(account.id, member_id, owner)
    assert missing.value.code == "MEMBER_NOT_FOUND"


@pytest.mark.asyncio
async def test_registered_event_creates_individual_account_once(accounts: AccountService) -> None:
    user_id = uuid4()
    payload = {"user_id": str(user_id), "email": "avery.moore@example.com"}
    await accounts.handle_user_registered(payload)
    await accounts.handle_user_registered(payload)

    owner = actor(user_id, user_id, MemberRole.OWNER)
    owned = await accounts.list_for_user(owner)
    assert len(owned) == 1
    assert owned[0].id == user_id and owned[0].type == "individual"
    members = await accounts.list_members(user_id, owner)
    assert len(members) == 1 and members[0].role == MemberRole.OWNER
    publisher = cast(InMemoryEventBus, accounts.publisher)
    assert [event[0] for event in publisher.events].count("account.created") == 1


@pytest.mark.asyncio
async def test_invite_creation_acceptance_and_joined_event(accounts: AccountService) -> None:
    owner_id, invited_user_id = uuid4(), uuid4()
    account = await accounts.create(
        AccountCreate(name="Invite Team", slug="invite-team", type="team"), owner_id
    )
    invitation = await accounts.invite(
        account.id,
        InviteCreate(email="member@example.com", role=MemberRole.ADMIN),
        actor(owner_id, account.id, MemberRole.OWNER),
    )
    publisher = cast(InMemoryEventBus, accounts.publisher)
    invited_event = publisher.events[-1]
    assert invited_event[0] == "member.invited"
    raw_token = cast(str, invited_event[1]["invite_token"])
    assert invitation.token_hash != raw_token

    member = await accounts.accept_invite(raw_token, invited_user_id)
    assert member.role == MemberRole.ADMIN and member.user_id == invited_user_id
    assert publisher.events[-1][0] == "member.joined"
    async with accounts.sessions() as session:
        stored = await session.get(Invite, invitation.id)
    assert stored is not None and stored.accepted_at is not None

    with pytest.raises(TenantError) as reused:
        await accounts.accept_invite(raw_token, uuid4())
    assert reused.value.code == "INVALID_INVITE"


@pytest.mark.asyncio
async def test_admin_member_limits_and_superadmin_override(accounts: AccountService) -> None:
    owner_id, admin_id, member_id = uuid4(), uuid4(), uuid4()
    account = await accounts.create(AccountCreate(name="RBAC", slug="rbac", type="team"), owner_id)
    async with accounts.sessions() as session, session.begin():
        session.add_all([
            AccountMember(account_id=account.id, user_id=admin_id, role=MemberRole.ADMIN),
            AccountMember(account_id=account.id, user_id=member_id, role=MemberRole.MEMBER),
        ])
    admin = actor(admin_id, account.id, MemberRole.ADMIN)
    await accounts.update_role(account.id, member_id, MemberRole.ADMIN, admin)
    with pytest.raises(TenantError) as owner_forbidden:
        await accounts.remove_member(account.id, owner_id, admin)
    assert owner_forbidden.value.code == "ROLE_ESCALATION_FORBIDDEN"

    superadmin = actor(uuid4(), uuid4(), MemberRole.MEMBER, "SuperAdmin")
    assert (await accounts.get(account.id, superadmin)).id == account.id
    assert account.id in {value.id for value in await accounts.list_for_user(superadmin, all_accounts=True)}
    await accounts.update_role(account.id, admin_id, MemberRole.MEMBER, superadmin)


@pytest.mark.asyncio
async def test_last_owner_cannot_be_removed_or_demoted(accounts: AccountService) -> None:
    owner_id = uuid4()
    account = await accounts.create(AccountCreate(name="Safe", slug="safe", type="team"), owner_id)
    owner = actor(owner_id, account.id, MemberRole.OWNER)
    with pytest.raises(TenantError) as demote:
        await accounts.update_role(account.id, owner_id, MemberRole.MEMBER, owner)
    assert demote.value.code == "LAST_OWNER_REQUIRED"
    with pytest.raises(TenantError) as remove:
        await accounts.remove_member(account.id, owner_id, owner)
    assert remove.value.code == "LAST_OWNER_REQUIRED"
