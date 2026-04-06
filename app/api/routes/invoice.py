import os
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from app.core.config import get_db
from app.core.app_security import get_current_user
from sqlalchemy.orm import Session
from app.models.invoice_model import Invoice, InvoiceStatus, ProcessingLog, User
from app.schemas.invoice_schema import InvoiceResponse
import shutil
from loguru import logger
from app.helper.helper_func import validate_file
import pdfplumber
from datetime import datetime, timezone
import time


MAX_FILE_SIZE_IN_BYTES = 10 * 1024 * 1024
PDF_MAGIC_BYTES = b'\x25\x50\x44\x46'
UPLOAD_DIR = "C:/Users/Ratnambar/Desktop/smartInvoice/smartinvoice-ai/data/invoices"

router = APIRouter(prefix="/invoice", tags = ["Invoice"])


@router.post("/upload", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED, summary="Uplaod a new Invoice")
async def upload_file(
    db: Annotated[Session, Depends(get_db)],
    vendor_id: Annotated[int, Form(description="ID of the vendor this invoice belongs to")],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(),
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
async def process_invoice(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    invoice_id: int
):

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice with id {invoice_id} not found.",
        )
    pdf_path = invoice.file_path
    assert pdf_path is not None  # validate_file rejects missing filename
    if not pdf_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice PDF with id {invoice_id} not found.")
    
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        start_time = time.time()
        try:
            for page_number, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                if page_text:
                    full_text+=f"Page {page_number}: {page_text}\n"
                else:
                    logger.warning(f"Page {page_number} is not readable.")
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error extracting text from PDF: {e}")
        if not full_text.strip():
            raise HTTPException(
            status_code=422,
            detail="PDF appears to be image-only (scanned). Text extraction is not supported yet. "
                   "Please upload a text-based PDF."
        )
        logger.info(f"Successfully extracted text from PDF: {pdf_path}")
        invoice.status = InvoiceStatus.PROCESSING
        db.commit()

        end_time = time.time()

        invoice.raw_text = full_text
        invoice.status = InvoiceStatus.COMPLETED
        invoice.processing_time_ms = int((end_time - start_time)*1000)
        invoice.processed_at = datetime.now(timezone.utc)
        

        # invoice = Invoice(
        #     raw_text = full_text,
        #     status = InvoiceStatus.COMPLETED,
        #     processing_time_ms = int((time.time() - start_time)*1000),
        #     processed_at = datetime.now(timezone.utc)
        # )
            
        db.add(ProcessingLog(
            invoice_id = invoice.id,
            step = "PDF_EXTRACTION",
            status = "SUCCESS",
            message = f"Successfully extracted text from pdf {len(full_text)} characters in {invoice.processing_time_ms}ms time."
        ))
        db.commit()
        db.refresh(invoice)
    return invoice