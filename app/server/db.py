import logging
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Type, TypeVar, Union

from bc2.lib.embedding import Embedding
from glowplug import DbDriver, MsSqlSettings, SqliteSettings
from sqlalchemy import Dialect, ForeignKey, delete, select
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.types import (
    BINARY,
    NVARCHAR,
    VARBINARY,
    DateTime,
    LargeBinary,
    String,
    TypeDecorator,
    TypeEngine,
)
from sqlalchemy.types import Enum as SQLEnum
from typing_extensions import Annotated
from uuid_utils import UUID, uuid7

from .time import NowFn, utcnow

logger = logging.getLogger(__name__)

RdbmsConfig = Union[MsSqlSettings, SqliteSettings]

BaseT = TypeVar("BaseT", bound="Base")

str_256 = Annotated[str, 256]
str_4096 = Annotated[str, 4096]
# 4 MiB is an effectively unlimited text field
# SQLAlchemy will use a vendor-specific type for this, such as LONGTEXT for MySQL
text = Annotated[str, 4_194_304]

ReviewType = Enum("ReviewType", "blind final")

Decision = Enum(
    "Decision",
    "disqualify decline charge charge_likely charge_maybe decline_likely decline_maybe",
)

Disqualifier = Enum(
    "Disqualifier",
    "assigned_to_unblind case_type_ineligible prior_knowledge_bias "
    "narrative_incomplete redaction_missing redaction_illegible other",
)


class EmbeddingType(TypeDecorator):
    """Stores embeddings compactly in a binary format."""

    MAX_SIZE = 4096
    """Maximum dimensionality of an embedding."""

    _MAX_SIZE_BITS = Embedding.calc_binary_size(MAX_SIZE)
    """Number of bits needed to store largest embedding."""

    impl = LargeBinary

    _default_type = LargeBinary(_MAX_SIZE_BITS)

    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        # MSSQL can't hang with large binary sizes in the type def -- 8000 max.
        # But, it can handle up to 2gb if we pass they keyword "MAX" instead.
        if dialect.name == "mssql":
            max_size_b = self._MAX_SIZE_BITS if self._MAX_SIZE_BITS < 8000 else None
            return dialect.type_descriptor(VARBINARY(max_size_b))
        else:
            return dialect.type_descriptor(self._default_type)

    def process_bind_param(self, value: Any | None, dialect: Dialect) -> bytes | None:
        """Convert a list of floats to bytes."""
        if value is None:
            return None

        # Coerce input to Embedding type.
        embedding: Embedding | None = None
        if isinstance(value, Embedding):
            embedding = value
        elif isinstance(value, (list, tuple)):
            embedding = Embedding(value)
        else:
            raise ValueError("Embedding must be a list, tuple, or Embedding.")

        # Check bounds
        if embedding.dimensions > self.MAX_SIZE:
            raise ValueError(f"{embedding} exceeds max size of {self.MAX_SIZE}")

        return embedding.to_binary()

    def process_result_value(
        self, value: bytes | None, dialect: Dialect
    ) -> list[float] | None:
        """Convert bytes to a list of floats."""
        if value is None:
            return None

        return Embedding.from_binary(value).to_list()


class UUID7Type(TypeDecorator):
    """UUIDv7 type for SQLAlchemy.

    Stores UUIDs as 16-byte binary values.
    """

    impl = BINARY(16)

    cache_ok = True

    def process_bind_param(self, value: Any | None, dialect: Dialect) -> bytes | None:
        """Convert a UUID to bytes."""
        if value is None:
            return None
        if isinstance(value, str):
            return UUID(value).bytes
        elif isinstance(value, UUID):
            return value.bytes
        elif isinstance(value, bytes):
            return value
        return value

    def process_result_value(self, value: Any | None, dialect: Dialect) -> UUID | None:
        """Convert bytes to a UUID."""
        if value is None:
            return None
        if isinstance(value, str):
            return UUID(value)
        elif isinstance(value, bytes):
            return UUID(value.hex())
        return value


def primary_key() -> UUID:
    """Generate a UUIDv7 primary key."""
    return uuid7()


class Base(AsyncAttrs, DeclarativeBase):
    id: Mapped[UUID]

    type_annotation_map = {
        UUID: UUID7Type,
        datetime: DateTime(timezone=True),
        Embedding: EmbeddingType,
        str_256: String(255),
        str_4096: String(4095),
        ReviewType: SQLEnum(ReviewType),
        Decision: SQLEnum(Decision),
        Disqualifier: SQLEnum(Disqualifier),
        text: String(4_194_303).with_variant(
            # NOTE: typing is wrong for mssql, "max" is valid.
            NVARCHAR("max"),  # type: ignore
            "mssql",
        ),
    }

    @classmethod
    async def get_by_id(
        cls: Type[BaseT], session: AsyncSession, id: UUID
    ) -> Optional[BaseT]:
        """Get a record by its ID."""
        q = select(cls).filter(cls.id == id)
        result = await session.execute(q)
        return result.scalar_one_or_none()


class Gater(Base):
    __tablename__ = "gater"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=primary_key)
    parent: Mapped[UUID] = mapped_column(ForeignKey("gater.id"), nullable=True)
    name: Mapped[str_256] = mapped_column(nullable=True)
    description: Mapped[text] = mapped_column(nullable=True)
    blob: Mapped[text] = mapped_column()
    author: Mapped[str_256] = mapped_column(nullable=True)
    active: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Assignment(Base):
    __tablename__ = "assignment"
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", "feature"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=primary_key)
    entity_type: Mapped[str_256] = mapped_column(index=True)
    entity_id: Mapped[str_4096] = mapped_column(index=True)
    feature: Mapped[str_256] = mapped_column(index=True)
    variant: Mapped[str_256] = mapped_column(index=True)
    value: Mapped[text] = mapped_column()
    ts: Mapped[datetime] = mapped_column()
    event_id: Mapped[str_256] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Exposure(Base):
    __tablename__ = "exposure"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=primary_key)
    jurisdiction_id: Mapped[str_256] = mapped_column()
    case_id: Mapped[str_256] = mapped_column()
    subject_id: Mapped[str_256] = mapped_column()
    document_ids: Mapped[str_4096] = mapped_column()
    reviewer_id: Mapped[str_256] = mapped_column()
    review_type: Mapped[ReviewType] = mapped_column()
    extra: Mapped[text] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Outcome(Base):
    __tablename__ = "outcome"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=primary_key)
    jurisdiction_id: Mapped[str_256] = mapped_column()
    case_id: Mapped[str_256] = mapped_column()
    subject_id: Mapped[str_256] = mapped_column()
    reviewer_id: Mapped[str_256] = mapped_column()
    document_ids: Mapped[str_4096] = mapped_column()
    review_type: Mapped[ReviewType] = mapped_column()
    decision: Mapped[Decision] = mapped_column()
    explanation: Mapped[text] = mapped_column(nullable=True)
    disqualifiers: Mapped[list["OutcomeDisqualifiers"]] = relationship(
        "OutcomeDisqualifiers",
        back_populates="outcome",
        cascade="all, delete-orphan",
        uselist=True,
        lazy="joined",
    )
    additional_evidence: Mapped[text] = mapped_column(nullable=True)
    page_open_ts: Mapped[datetime] = mapped_column()
    decision_ts: Mapped[datetime] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class OutcomeDisqualifiers(Base):
    __tablename__ = "outcome_disqualifiers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=primary_key)
    outcome_id: Mapped[UUID] = mapped_column(ForeignKey("outcome.id"))
    outcome: Mapped[Outcome] = relationship("Outcome", back_populates="disqualifiers")
    disqualifier: Mapped[Disqualifier] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class DocumentStatus(Base):
    __tablename__ = "document_status"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=primary_key)
    jurisdiction_id: Mapped[str_256] = mapped_column()
    case_id: Mapped[str_256] = mapped_column()
    document_id: Mapped[str_256] = mapped_column()
    status: Mapped[str_256] = mapped_column()
    error: Mapped[str_4096] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class DocumentEmbedding(Base):
    __tablename__ = "document_embedding"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=primary_key)
    jurisdiction_id: Mapped[str_256] = mapped_column()
    case_id: Mapped[str_256] = mapped_column()
    subject_id: Mapped[str_256] = mapped_column(nullable=True)
    document_id: Mapped[str_256] = mapped_column()
    embedding: Mapped[Embedding] = mapped_column()
    dimensions: Mapped[int] = mapped_column()
    model_vendor: Mapped[str_256] = mapped_column()
    model_name: Mapped[str_256] = mapped_column()
    model_version: Mapped[str_256] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Client(Base):
    __tablename__ = "client"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=primary_key)
    name: Mapped[str_256] = mapped_column(unique=True)
    secret_hash: Mapped[str_256] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Revocation(Base):
    __tablename__ = "revocation"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    @classmethod
    async def check(cls, session: AsyncSession, token_id: str) -> bool:
        """Check if token has been revoked given its JTI.

        Args:
            session (AsyncSession): The database session.
            token_id (str): The JTI of the token, as a hex-string.

        Returns:
            bool: Whether the token has been revoked.
        """
        q = select(cls).filter(cls.id == bytes.fromhex(token_id))
        result = await session.execute(q)
        return result.scalar_one_or_none() is not None

    @classmethod
    async def revoke(
        cls, session: AsyncSession, token_id: str, expires_at: datetime
    ) -> None:
        """Revoke a token given its JTI.

        Args:
            session (AsyncSession): The database session.
            token_id (str): The JTI of the token, as a hex-string.
            expires_at (datetime): The expiration time of the token.
        """
        r = cls(id=bytes.fromhex(token_id), expires_at=expires_at)
        session.add(r)
        await session.commit()

    @classmethod
    async def vacuum(cls, session: AsyncSession, now: NowFn = utcnow) -> None:
        """Remove expired tokens.

        Args:
            session (AsyncSession): The database session
        """
        q = delete(cls).filter(cls.expires_at < now())
        await session.execute(q)
        await session.commit()


async def init_db(driver: DbDriver, drop_first: bool = False) -> None:
    """Initialize the database and its tables.

    Args:
        driver (DbDriver): The database driver.
        drop_first (bool): Whether to drop the tables first
    """
    if not await driver.exists():
        logger.info("No database exists, creating a new one")
        await driver.create()
    else:
        logger.info("Database already exists")

    # Create the database
    if drop_first:
        logger.info("Re-creating database tables")
    else:
        logger.info("Creating database tables")
    await driver.init(Base, drop_first=drop_first)


def clear_invalid_revision(driver: DbDriver) -> None:
    """Clear the invalid revision from the database.

    Args:
        driver (DbDriver): The database driver.
    """
    with driver.sync_session() as s:
        s.execute(sql_text("DELETE FROM alembic_version"))
        s.commit()
