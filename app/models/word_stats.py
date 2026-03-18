import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WordStats(Base):
    __tablename__ = "word_stats"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    word_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("words.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    box: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_practiced: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    word: Mapped["Word"] = relationship("Word", back_populates="stats")  # noqa: F821
