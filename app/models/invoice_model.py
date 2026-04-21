from __future__ import annotations

from sqlalchemy import Column, Integer, BigInteger, String, Float, ForeignKey, DateTime, Boolean, Enum, Text  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
import datetime
from app.core.config import Base
from sqlalchemy.sql import func


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    FLAGGED = "flagged"

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ACCOUNTANT = "accountant"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.ACCOUNTANT)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="uploaded_by_user")

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size_bytes = Column(BigInteger, nullable=False)
    invoice_number   = Column(String(100), nullable=True)
    invoice_date     = Column(String(50),  nullable=True)     # stored as string (formats vary)
    vendor_name      = Column(String(255), nullable=True)
    subtotal         = Column(Float,       nullable=True)
    tax_amount       = Column(Float,       nullable=True)
    total_amount     = Column(Float,       nullable=True)
    currency         = Column(String(10),  nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.PENDING)
    anomaly_report = Column(Text, nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=datetime.datetime.now(datetime.timezone.utc))
    processed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_by_user = relationship("User", back_populates="invoices")
    vendor = relationship("Vendor", back_populates="invoices")
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan")
    logs             = relationship("ProcessingLog",   back_populates="invoice", cascade="all, delete-orphan")
    webhook_url = Column(String(500), nullable=True)
    
class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    description = Column(String(255), nullable=True)
    quantity = Column(Float, default=1.0)
    unit_price = Column(Float, default=0.0)
    total_price = Column(Float, default=0.0)
    line_number = Column(Integer, default=1)
    invoice = relationship("Invoice", back_populates="line_items")

class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255))
    gst_number = Column(String(50))
    payment_terms = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now(datetime.timezone.utc))
    invoices = relationship("Invoice", back_populates="vendor")

class ProcessingLog(Base):
    """
    Audit trail — every step of processing is logged here.
    Useful for debugging and showing the agent pipeline in your portfolio demo.
    """
    __tablename__ = "processing_logs"

    id         = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    step       = Column(String(100))    # e.g. "PDF_EXTRACTION", "VALIDATION", "SUMMARY"
    status     = Column(String(50))     # "SUCCESS" | "FAILED" | "SKIPPED"
    message    = Column(Text)           # detail or error message
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    invoice    = relationship("Invoice", back_populates="logs")