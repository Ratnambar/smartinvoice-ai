from pydantic import BaseModel, Field, EmailStr  # pyright: ignore[reportMissingImports]
from datetime import datetime
from typing import Optional, List
from app.models.invoice_model import UserRole, InvoiceStatus, User
from app.core.config import Base


class UserCreate(BaseModel):
    email:      EmailStr
    password:   str = Field(min_length=6, description="Password must be at least 6 characters long")
    full_name:  Optional[str] = None
    role:       UserRole = UserRole.ACCOUNTANT

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True

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
    email:         Optional[str] = None
    gst_number:    Optional[str] = None
    payment_terms: int = 30

class VendorResponse(BaseModel):
    id:            int
    name:          str
    email:         Optional[str]
    gst_number:    Optional[str]
    payment_terms: int
    is_active:     bool
    class Config:
        from_attributes = True


# ── Invoice ───────────────────────────────────────────────────────────────────

class InvoiceLineItemResponse(BaseModel):
    id:          int
    description: Optional[str]
    quantity:    float
    unit_price:  float
    total_price: float
    line_number: int
    class Config:
        from_attributes = True

class InvoiceResponse(BaseModel):
    id:                  int
    file_name:   str
    file_size_bytes:     int
    status:              InvoiceStatus
    invoice_number:      Optional[str]
    invoice_date:        Optional[str]
    vendor_name:         Optional[str]
    subtotal:            Optional[float]
    tax_amount:          Optional[float]
    total_amount:        Optional[float]
    currency:            Optional[str]
    anomaly_report:      Optional[str]
    processing_time_ms:  Optional[int]
    uploaded_at:         datetime
    processed_at:        Optional[datetime]
    line_items:          List[InvoiceLineItemResponse] = []
    class Config:
        from_attributes = True

class InvoiceListResponse(BaseModel):
    """Lightweight version for listing — no line_items or raw_text"""
    id:                int
    original_filename: str
    status:            InvoiceStatus
    vendor_name:       Optional[str]
    total_amount:      Optional[float]
    uploaded_at:       datetime
    class Config:
        from_attributes = True


# ── Processing Log ────────────────────────────────────────────────────────────

class ProcessingLogResponse(BaseModel):
    id:         int
    step:       str
    status:     str
    message:    Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True


# ── Analytics ─────────────────────────────────────────────────────────────────

class InvoiceStats(BaseModel):
    total_invoices:     int
    pending:            int
    completed:          int
    failed:             int
    flagged:            int
    total_amount_processed: float