import os
from typing import Annotated, cast
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from app.core.config import get_db
from app.core.app_security import get_current_user
from sqlalchemy.orm import Session
from app.models.invoice_model import Invoice, InvoiceStatus, ProcessingLog, User, Vendor
from app.schemas.invoice_schema import InvoiceResponse, ProcessingLogResponse, VendorCreate, VendorResponse
from app.workers.tasks import process_invoice_task
from slowapi import Limiter
from slowapi.util import get_remote_address
import shutil
from loguru import logger
from app.helper.helper_func import validate_file


MAX_FILE_SIZE_IN_BYTES = 10 * 1024 * 1024
PDF_MAGIC_BYTES = b'\x25\x50\x44\x46'
UPLOAD_DIR = "/app/data/invoices"

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/invoice", tags = ["Invoice"])

def _normalize_webhook_url(url: str | None) -> str | None:
    if url is None:
        return None
    s = url.strip()
    if not s:
        return None
    if len(s) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="webhook_url must be at most 500 characters.",
        )
    return s


@router.post("/upload", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED, summary="Uplaod a new Invoice")
async def upload_file(
    db: Annotated[Session, Depends(get_db)],
    vendor_id: Annotated[int, Form(description="ID of the vendor this invoice belongs to")],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(),
    webhook_url: Annotated[str | None, Form(description="Optional URL to notify when processing completes")] = None,
):
    try:
        result = validate_file(db, vendor_id, file)
    except HTTPException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    filename = result.filename
    assert filename is not None  # validate_file rejects missing filename
    destination_path = UPLOAD_DIR + "/" + filename
    invoice = Invoice(
        uploaded_by=current_user.id,
        vendor_id=vendor_id,
        file_name=filename,
        file_path="",
        file_size_bytes=result.size,
        status=InvoiceStatus.PENDING,
        webhook_url=_normalize_webhook_url(webhook_url),
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    updated_filename = str(invoice.id) + "_" + filename
    updated_file_path =  UPLOAD_DIR + "/" + updated_filename
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with open(updated_file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    invoice.file_path = updated_file_path
    db.commit()
    db.refresh(invoice)
    
    db.add(ProcessingLog(
        invoice_id = invoice.id,
        step       = "UPLOAD",
        status     = "SUCCESS",
        message    = f"File saved to {destination_path} ({result.size} bytes)",
    ))
    db.commit()

    logger.info(f"Invoice uploaded | id={invoice.id} file={filename} user={current_user.email}")
    return invoice


@router.post("/{invoice_id}/process", 
  response_model=InvoiceResponse,
  status_code=status.HTTP_200_OK, summary="Process an invoice")
@limiter.limit("10/minute")
async def process_invoice(
    db: Annotated[Session, Depends(get_db)],
    invoice_id: int
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice with id {invoice_id} not found.",
        )
    if invoice.status == InvoiceStatus.PROCESSING:
        raise HTTPException(status_code=400, detail="Already being processed.")
    if invoice.status == InvoiceStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Already processed.")

    process_invoice_task.delay(invoice_id) # type: ignore
    db.commit()
    db.refresh(invoice)
    webhook_url = cast(str | None, cast(object, invoice.webhook_url))
    if webhook_url:
        import httpx
        try:
            httpx.post(
                webhook_url,
                json={
                    "invoice_id":  invoice.id,
                    "status":      invoice.status,
                    "vendor_name": invoice.vendor_name,
                    "total_amount": invoice.total_amount,
                    "anomaly_report": invoice.anomaly_report,
                },
                timeout=5,
            )
            logger.info(f"Webhook sent to {webhook_url}")
        except Exception as e:
            logger.warning(f"Webhook failed: {e}")
    return invoice


@router.get("/{invoice_id}", response_model=InvoiceResponse,status_code=status.HTTP_200_OK,
            summary="Check processing status of Invoice")
async def get_invoice(
    db: Annotated[Session, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    invoice_id: int):
    invoice = db.query(Invoice).filter(Invoice.id==invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code = 404,
            detail      = f"Invoice with id {invoice_id} not found."
        )

    return invoice


@router.get("/{invoice_id}/logs", response_model=list[ProcessingLogResponse], status_code=status.HTTP_200_OK, 
            summary="Get processing logs of Invoice")
async def get_invoice_logs(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    invoice_id: int,
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=404,
            detail=f"Invoice with id {invoice_id} not found.",
        )
    logs = db.query(ProcessingLog).filter(ProcessingLog.invoice_id == invoice_id).order_by(ProcessingLog.created_at.asc()).all()
    return logs


@router.post("/create_vendor", response_model=VendorResponse, status_code=status.HTTP_201_CREATED, summary="Create a new vendor")
async def create_vendor(
    db: Annotated[Session, Depends(get_db)],
    payload: VendorCreate
):
    existing = db.query(Vendor).filter(Vendor.email==payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vendor already exists")

    new_vendor = Vendor(name=payload.name, 
                  email=payload.email, gst_number=payload.gst_number, 
                  payment_terms=payload.payment_terms, is_active=True)
    db.add(new_vendor)
    db.commit()
    db.refresh(new_vendor)
    return new_vendor