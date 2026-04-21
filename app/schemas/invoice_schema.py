from pydantic import BaseModel, ConfigDict, Field, EmailStr  # pyright: ignore[reportMissingImports]
from datetime import datetime
from typing import ClassVar
from app.models.invoice_model import UserRole, InvoiceStatus


class UserCreate(BaseModel):
    email:      EmailStr
    password:   str = Field(min_length=6, description="Password must be at least 6 characters long")
    full_name:  str | None = None
    role:       UserRole = UserRole.ACCOUNTANT

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str | None = None
    role: UserRole
    is_active: bool
    created_at: datetime
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"

class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None

class UserInDB(UserCreate):
    hashed_password: str

class VendorCreate(BaseModel):
    name:          str
    email:         str | None = None
    gst_number:    str | None = None
    payment_terms: int = 30

class VendorResponse(BaseModel):
    id:            int
    name:          str
    email:         str | None
    gst_number:    str | None
    payment_terms: int
    is_active:     bool
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


# ── Invoice ───────────────────────────────────────────────────────────────────

class InvoiceLineItemResponse(BaseModel):
    id:          int
    description: str | None
    quantity:    float
    unit_price:  float
    total_price: float
    line_number: int
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

class InvoiceResponse(BaseModel):
    id:                  int
    file_name:   str
    file_size_bytes:     int
    status:              InvoiceStatus
    invoice_number:      str | None
    invoice_date:        str | None
    vendor_name:         str | None
    subtotal:            float | None
    tax_amount:          float | None
    total_amount:        float | None
    currency:            str | None
    anomaly_report:      str | None
    processing_time_ms:  int | None
    uploaded_at:         datetime
    processed_at:        datetime | None
    webhook_url:         str | None = None
    line_items:          list[InvoiceLineItemResponse] = []
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

class InvoiceListResponse(BaseModel):
    """Lightweight version for listing — no line_items or raw_text"""
    id:                int
    original_filename: str
    status:            InvoiceStatus
    vendor_name:       str | None
    total_amount:      float | None
    uploaded_at:       datetime
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


# ── Processing Log ────────────────────────────────────────────────────────────

class ProcessingLogResponse(BaseModel):
    id:         int
    step:       str
    status:     str
    message:    str | None
    created_at: datetime
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


# ── Analytics ─────────────────────────────────────────────────────────────────

class InvoiceStats(BaseModel):
    total_invoices:     int
    pending:            int
    completed:          int
    failed:             int
    flagged:            int
    total_amount_processed: float