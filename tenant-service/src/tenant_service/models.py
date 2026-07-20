from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

TENANT_SCHEMA = "tenant"


class Base(DeclarativeBase):
    metadata = MetaData(schema=TENANT_SCHEMA)


class AccountType(StrEnum):
    INDIVIDUAL = "individual"
    TEAM = "team"


class MemberRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("type IN ('individual', 'team')", name="ck_tenant_accounts_type"),
        CheckConstraint("seat_count >= 1", name="ck_tenant_accounts_seat_count"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", server_default="active")
    type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AccountType.INDIVIDUAL, server_default=AccountType.INDIVIDUAL
    )
    plan_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="free", server_default="free")
    seat_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AccountMember(Base):
    __tablename__ = "account_members"
    __table_args__ = (
        UniqueConstraint("account_id", "user_id", name="uq_tenant_account_members_account_user"),
        CheckConstraint("role IN ('owner', 'admin', 'member')", name="ck_tenant_account_members_role"),
        Index("ix_tenant_account_members_account_role", "account_id", "role"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default=MemberRole.MEMBER, server_default=MemberRole.MEMBER
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Invite(Base):
    __tablename__ = "invites"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'admin', 'member')", name="ck_tenant_invites_role"),
        Index("ix_tenant_invites_account_email", "account_id", "email"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant.accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default=MemberRole.MEMBER)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
