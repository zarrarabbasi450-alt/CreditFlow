import uuid
from typing import Any

from sqlalchemy import CHAR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class GUID(TypeDecorator[uuid.UUID]):
    """Cross-dialect UUID column.

    Uses PostgreSQL's native UUID type in production. On other dialects
    (SQLite, used in tests) it stores a plain CHAR(36) hyphenated string.

    This matters: a generically-compiled `postgresql.UUID` column gets no
    recognized type-affinity keyword on SQLite, so SQLite falls back to
    NUMERIC affinity — and an all-digit UUID (e.g. "222...222", the kind
    hand-written test fixtures often use) gets silently coerced into a
    float, corrupting it. CHAR(36) forces TEXT affinity and avoids that.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return str(value)
        return str(value if isinstance(value, uuid.UUID) else uuid.UUID(str(value)))

    def process_result_value(self, value: Any, dialect: Dialect) -> uuid.UUID | None:
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
