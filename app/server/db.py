from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Type, TypeVar

from sqlalchemy import ForeignKey, select
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.types import BINARY, DateTime, LargeBinary, String
from sqlalchemy.types import Enum as SQLEnum
from typing_extensions import Annotated
from uuid_utils import UUID, uuid7

BaseT = TypeVar("BaseT", bound="Base")

str_256 = Annotated[str, 256]
str_4096 = Annotated[str, 4096]

JobStatus = Enum("JobStatus", "queued processing success error")

CallbackStatus = Enum("CallbackStatus", "pending success error")

TaskState = Enum("TaskState", "unclaimed claimed")


def nowts() -> datetime:
    """Return the current datetime with the timezone set to UTC."""
    return datetime.now(timezone.utc)


def primary_key() -> bytes:
    """Generate a UUIDv7 primary key."""
    return uuid7().bytes


class Base(AsyncAttrs, DeclarativeBase):
    type_annotation_map = {
        UUID: BINARY(16),
        datetime: DateTime(timezone=True),
        str_256: String(256),
        str_4096: String(4096),
        bytes: LargeBinary,
        JobStatus: SQLEnum(JobStatus),
        CallbackStatus: SQLEnum(CallbackStatus),
        TaskState: SQLEnum(TaskState),
    }

    @classmethod
    async def get_by_id(
        cls: Type[BaseT], session: AsyncSession, id: UUID
    ) -> Optional[BaseT]:
        """Get a record by its ID."""
        q = select(cls).filter(cls.id == id)
        result = await session.execute(q)
        return result.scalar_one_or_none()


class SubjectDocument(Base):
    __tablename__ = "subject_document"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=primary_key)
    subject_id: Mapped[str] = mapped_column(
        ForeignKey("subject.subject_id"), index=True
    )
    subject: Mapped["Subject"] = relationship(lazy="joined", back_populates="documents")
    document_id: Mapped[str] = mapped_column(index=True)
    role: Mapped[str_256]
    mask: Mapped[str_256] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=nowts)
    updated_at: Mapped[datetime] = mapped_column(default=nowts, onupdate=nowts)


class Subject(Base):
    __tablename__ = "subject"

    subject_id: Mapped[str] = mapped_column(primary_key=True)
    documents: Mapped[List["SubjectDocument"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan"
    )
    aliases: Mapped[List["Alias"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan", lazy="joined"
    )
    created_at: Mapped[datetime] = mapped_column(default=nowts)
    updated_at: Mapped[datetime] = mapped_column(default=nowts, onupdate=nowts)


class Alias(Base):
    __tablename__ = "alias"
    __table_args__ = (
        UniqueConstraint(
            "subject_id",
            "title",
            "first_name",
            "middle_name",
            "last_name",
            "suffix",
            "nickname",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=primary_key)
    primary: Mapped[datetime] = mapped_column(nullable=True)
    subject_id: Mapped[str_256] = mapped_column(ForeignKey("subject.subject_id"))
    subject: Mapped["Subject"] = relationship(back_populates="aliases")
    title: Mapped[str_256] = mapped_column(nullable=True)
    first_name: Mapped[str_256] = mapped_column(nullable=True)
    middle_name: Mapped[str_256] = mapped_column(nullable=True)
    last_name: Mapped[str_256] = mapped_column(nullable=True)
    suffix: Mapped[str_256] = mapped_column(nullable=True)
    nickname: Mapped[str_256] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=nowts)
    updated_at: Mapped[datetime] = mapped_column(default=nowts, onupdate=nowts)


class Task(Base):
    __tablename__ = "task"

    task_id: Mapped[str] = mapped_column(primary_key=True)
    case_id: Mapped[str_256] = mapped_column(index=True)
    jurisdiction_id: Mapped[str_256] = mapped_column(index=True)
    document_id: Mapped[str_256] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(default=nowts)
    updated_at: Mapped[datetime] = mapped_column(default=nowts, onupdate=nowts)
    expires_at: Mapped[datetime] = mapped_column(nullable=True)
