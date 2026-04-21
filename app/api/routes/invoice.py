import os
from typing import Annotated, cast
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from app.core.config import get_db
from app.core.app_security import get_current_user
from sqlalchemy.orm import Session
from app.models.invoice_model import Invoice, InvoiceStatus, ProcessingLog, User
from app.schemas.invoice_schema import InvoiceResponse, ProcessingLogResponse
from app.workers.tasks import process_invoice_task
from slowapi import Limiter
from slowapi.util import get_remote_address
import shutil
from loguru import logger
from app.helper.helper_func import validate_file


MAX_FILE_SIZE_IN_BYTES = 10 * 1024 * 1024
PDF_MAGIC_BYTES = b'\x25\x50\x44\x46'
UPLOAD_DIR = "E:/all-Project/smartInvoice/smartinvoice-ai/data/invoices"

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
    _current_user: Annotated[User, Depends(get_current_user)],
    invoice_id: int,
    request: Request
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
    # response = process_invoice_task(invoice_id)
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



    #------------------------- Old code--------------------------
    # pdf_path = invoice.file_path
    # assert pdf_path is not None  # validate_file rejects missing filename
    # if not pdf_path:
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invoice PDF with id {invoice_id} not found.")
    # full_text = ""
    # with pdfplumber.open(pdf_path) as pdf:
    #     start_time = time.time()
    #     try:
    #         for page_number, page in enumerate(pdf.pages, start=1):
    #             page_text = page.extract_text()
    #             if page_text:
    #                 full_text+=f"Page {page_number}: {page_text}\n"
    #             else:
    #                 logger.warning(f"Page {page_number} is not readable.")
    #     except Exception as e:
    #         logger.error(f"Error extracting text from PDF: {e}")
    #         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error extracting text from PDF: {e}")
    #     if not full_text.strip():
    #         raise HTTPException(
    #             status_code=422,
    #             detail="PDF appears to be image-only (scanned). Text extraction is not supported yet. Please upload a text-based PDF.",
    #         )
    #     logger.info(f"Successfully extracted text from PDF: {pdf_path}")
    #     invoice.status = InvoiceStatus.PROCESSING
    #     db.commit()

    #     end_time = time.time()

    #     invoice.raw_text = full_text
    #     invoice.status = InvoiceStatus.COMPLETED
    #     invoice.processing_time_ms = int((end_time - start_time)*1000)
    #     invoice.processed_at = datetime.now(timezone.utc)
            
    #     db.add(ProcessingLog(
    #         invoice_id = invoice.id,
    #         step = "PDF_EXTRACTION",
    #         status = "SUCCESS",
    #         message = f"Successfully extracted text from pdf {len(full_text)} characters in {invoice.processing_time_ms}ms time."
    #     ))
    #     db.commit()
        # db.refresh(invoice)
    # return invoice

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


# @router.post("/{invoice_id/summerize", status_code=status.HTTP_200_OK, summary="Summerize the invoice")
# async def summerize_invoice(
#     db: Annotated[Session, Depends(get_db)],
#     _current_user: Annotated[User, Depends(get_current_user)],
#     invoice_id: int
# ):
#     invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
#     if invoice is None:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail=f"Invoice with id {invoice_id} not found.",
#         )
#     raw_text = invoice.raw_text
#     prompt = f""" 
#         You are a helpful assistant that summerizes the invoice.
#         Here is the invoice text:
#         {raw_text[:1000] if raw_text else "No text available"}
#         Please summerize the invoice in a concise manner.
#         Return this exact JSON structure:
#             {{
#                 "invoice_number": "string or null",
#                 "invoice_date":   "string or null",
#                 "vendor_name":    "string or null",
#                 "subtotal":       number or null,
#                 "tax_amount":     number or null,
#                 "total_amount":   number or null,
#                 "currency":       "string or null",
#                 "line_items": [
#                     {{
#                     "description": "string",
#                     "quantity":    number,
#                     "unit_price":  number,
#                     "total_price": number
#                     }}
#                 ]
#             }}
#         Return ONLY a valid JSON object — no explanation, no markdown, no extra text.
#     """
#     response = get_ai_response(prompt)
#     if not response:
#         raise HTTPException(
#             status_code=500,
#             detail="The AI returned an empty response.",
#         )
#     match = re.search(r"\{.*\}", response, re.DOTALL)
#     clean_response = match.group(0) if match else ""
#     if not clean_response.strip():
#         print("ERROR: No JSON found in the AI response.")
#         raise HTTPException(
#             status_code=500,
#             detail="The AI failed to generate a valid JSON summary.",
#         )
#     if clean_response:
#         line_items_len = 0
#         data = json.loads(clean_response)  # pyright: ignore[reportAny]
#         invoice.invoice_number = data['invoice_number']
#         invoice.invoice_date = data['invoice_date']
#         invoice.vendor_name = data['vendor_name']
#         invoice.subtotal = data['subtotal']
#         invoice.tax_amount = data['tax_amount']
#         invoice.total_amount = data['total_amount']
#         invoice.currency = data['currency']
#         for i, item in enumerate(data['line_items'], start=1):  # pyright: ignore[reportAny]
#             new_line_item = InvoiceLineItem(
#                 invoice_id=invoice.id,
#                 description=item['description'],
#                 quantity=item['quantity'],
#                 unit_price=item['unit_price'],
#                 total_price=item['total_price'],
#                 line_number=i,
#             )
#             db.add(new_line_item)

#         processing_log = ProcessingLog(
#             invoice_id=invoice.id,
#             step="EXTRACTION_AGENT",
#             status="SUCCESS" if data ["vendor_name"] else "PARTIAL",
#             message=(f"Extracted: vendor={data['vendor_name']} "
#                         f"total={data['total_amount']} "
#                         f"line_items={line_items_len}"),
#                         )
#         db.add(processing_log)
#         db.commit()
#         # db.refresh(invoice)
#         # return invoice
#     else:
#         raise HTTPException(status_code=500, detail="The AI failed to generate a valid JSON summary.")
#     # Agent validation code
#     agent_validated_data = run_validation_agent(db, invoice) # pyright: ignore[reportArgumentType]
#     if agent_validated_data["vendor_id"]:
#         invoice.vendor_id = agent_validated_data["vendor_id"]
#     if not agent_validated_data["all_failed"]:
#         invoice.status = InvoiceStatus.COMPLETED
#     else:
#         invoice.status = InvoiceStatus.FLAGGED
#     checks = agent_validated_data["checks"]
#     db.add(ProcessingLog(
#         invoice_id = invoice.id,
#         step       = "VALIDATION_AGENT",
#         status     = "SUCCESS" if not agent_validated_data["all_failed"] else "FLAGGED",
#         message    = (
#                 f"Vendor: {'OK' if checks['vendor']['passed'] else 'FAIL'} | "
#                 f"Total: {'OK' if checks['total']['passed'] else 'FAIL'} | "
#                 f"Duplicate: {'OK' if checks['duplicate']['passed'] else 'FAIL'} | "
#                 f"Flags: {len(agent_validated_data['flags'])}"
#             ),
#         )
#     )
#     db.commit()
#     # ----- Summary Agent
#     anomaly_report = run_summary_agent(invoice, agent_validated_data)
#     invoice.anomaly_report = anomaly_report # type: ignore
#     db.add(ProcessingLog(
#         invoice_id = invoice.id,
#         step       = "SUMMARY_AGENT",
#         status     = "SUCCESS",
#         message    = f"Anomaly report generated ('{len(anomaly_report)}' chars)",  # type: ignore
#     ))
#     db.commit()
#     db.refresh(invoice)
#     return invoice