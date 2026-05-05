"""app/models/property.py — ORM table estate_mind_db."""
import uuid
from datetime import datetime
from sqlalchemy import JSON, DateTime, Double, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.engine import Base


class Property(Base):
    __tablename__ = "estate_mind_db"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    listing_id: Mapped[str] = mapped_column(String(128), nullable=False)
    transaction_type: Mapped[str | None] = mapped_column(String(32))
    property_type: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    price_value: Mapped[float | None] = mapped_column(Double)
    currency: Mapped[str | None] = mapped_column(String(8), default="TND")
    surface_m2: Mapped[float | None] = mapped_column(Double)
    bedrooms: Mapped[float | None] = mapped_column(Double)
    bathrooms: Mapped[float | None] = mapped_column(Double)
    city: Mapped[str | None] = mapped_column(String(128))
    district: Mapped[str | None] = mapped_column(String(128))
    region: Mapped[str | None] = mapped_column(String(128))
    latitude: Mapped[float | None] = mapped_column(Double)
    longitude: Mapped[float | None] = mapped_column(Double)
    url: Mapped[str | None] = mapped_column(String(512))
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extras: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("source", "listing_id", name="uq_estate_mind_db"),
        Index("ix_em_city", "city"),
        Index("ix_em_tx", "transaction_type"),
        Index("ix_em_price", "price_value"),
    )
