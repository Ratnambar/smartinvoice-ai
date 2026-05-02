from collections.abc import Callable
from typing import cast

from celery import Task

from app.workers.celery_app import celery_app
from fastapi import HTTPException, status
from app.core.config import SessionLocal
from app.models.invoice_model import Invoice, InvoiceLineItem,InvoiceStatus, ProcessingLog
from app.helper.helper_func import run_validation_agent, run_summary_agent
from app.core.config import get_ai_response
import pdfplumber
from datetime import datetime, timezone
from loguru import logger
import time
import json
import re


def _process_invoice_task(self: Task, invoice_id: int) -> str | None:
    db = SessionLocal()
    try:
        invoice = db.query(Invoice).filter(Invoice.id==invoice_id).first()
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
                    detail="PDF appears to be image-only (scanned). Text extraction is not supported yet. Please upload a text-based PDF.",
                )
            logger.info(f"Successfully extracted text from PDF: {pdf_path}")
            invoice.status = InvoiceStatus.PROCESSING
            db.commit()

            end_time = time.time()

            invoice.raw_text = full_text
            invoice.status = InvoiceStatus.COMPLETED
            invoice.processing_time_ms = int((end_time - start_time)*1000)
            invoice.processed_at = datetime.now(timezone.utc)
            
            db.add(ProcessingLog(
                invoice_id = invoice.id,
                step = "PDF_EXTRACTION",
                status = "SUCCESS",
                message = f"Successfully extracted text from pdf {len(full_text)} characters in {invoice.processing_time_ms}ms time."
            ))
            db.commit()

        raw_text = invoice.raw_text
        prompt = f""" 
            You are a helpful assistant that summerizes the invoice.
            Here is the invoice text:
            {raw_text[:1000] if raw_text else "No text available"}
            Please summerize the invoice in a concise manner.
            Return this exact JSON structure:
                {{
                    "invoice_number": "string or null",
                    "invoice_date":   "string or null",
                    "vendor_name":    "string or null",
                    "subtotal":       number or null,
                    "tax_amount":     number or null,
                    "total_amount":   number or null,
                    "currency":       "string or null",
                    "line_items": [
                        {{
                        "description": "string",
                        "quantity":    number,
                        "unit_price":  number,
                        "total_price": number
                        }}
                    ]
                }}
            Return ONLY a valid JSON object — no explanation, no markdown, no extra text.
        """
        response = get_ai_response(prompt)
        if not response:
            raise HTTPException(
                status_code=500,
                detail="The AI returned an empty response.",
            )
        match = re.search(r"\{.*\}", response, re.DOTALL)
        clean_response = match.group(0) if match else ""
        if not clean_response.strip():
            print("ERROR: No JSON found in the AI response.")
            raise HTTPException(
                status_code=500,
                detail="The AI failed to generate a valid JSON summary.",
            )
        if clean_response:
            line_items_len = 0
            data = json.loads(clean_response)  # pyright: ignore[reportAny]
            invoice.invoice_number = data['invoice_number']
            invoice.invoice_date = data['invoice_date']
            invoice.vendor_name = data['vendor_name']
            invoice.subtotal = data['subtotal']
            invoice.tax_amount = data['tax_amount']
            invoice.total_amount = data['total_amount']
            invoice.currency = data['currency']
            for i, item in enumerate(data['line_items'], start=1):  # pyright: ignore[reportAny]
                new_line_item = InvoiceLineItem(
                    invoice_id=invoice.id,
                    description=item['description'],
                    quantity=item['quantity'],
                    unit_price=item['unit_price'],
                    total_price=item['total_price'],
                    line_number=i,
                )
                db.add(new_line_item)

            processing_log = ProcessingLog(
                invoice_id=invoice.id,
                step="EXTRACTION_AGENT",
                status="SUCCESS" if data ["vendor_name"] else "PARTIAL",
                message=(f"Extracted: vendor={data['vendor_name']} "
                            f"total={data['total_amount']} "
                            f"line_items={line_items_len}"),
                            )
            db.add(processing_log)
            db.commit()
        else:
            raise HTTPException(status_code=500, detail="The AI failed to generate a valid JSON summary.")
        # Agent validation code
        agent_validated_data = run_validation_agent(db, invoice)
        if agent_validated_data["vendor_id"]:
            invoice.vendor_id = agent_validated_data["vendor_id"]
        if not agent_validated_data["all_failed"]:
            invoice.status = InvoiceStatus.COMPLETED
        else:
            invoice.status = InvoiceStatus.FLAGGED
        checks = agent_validated_data["checks"]
        db.add(ProcessingLog(
            invoice_id = invoice.id,
            step       = "VALIDATION_AGENT",
            status     = "SUCCESS" if not agent_validated_data["all_failed"] else "FLAGGED",
            message    = (
                    f"Vendor: {'OK' if checks['vendor']['passed'] else 'FAIL'} | "
                    f"Total: {'OK' if checks['total']['passed'] else 'FAIL'} | "
                    f"Duplicate: {'OK' if checks['duplicate']['passed'] else 'FAIL'} | "
                    f"Flags: {len(agent_validated_data['flags'])}"
                ),
            )
        )
        db.commit()
        # ----- Summary Agent
        anomaly_report = run_summary_agent(invoice, agent_validated_data)
        invoice.anomaly_report = anomaly_report # type: ignore
        db.add(ProcessingLog(
            invoice_id = invoice.id,
            step       = "SUMMARY_AGENT",
            status     = "SUCCESS",
            message    = f"Anomaly report generated ('{len(anomaly_report)}' chars)",  # type: ignore
        ))
        db.commit()
        logger.info(f"Task complete: invoice={invoice_id} status={invoice.status}")
        return anomaly_report
    except Exception as e:
        logger.error(f"Task failed: invoice={invoice_id} error={e}")
        try:
            invoice.status = InvoiceStatus.FAILED # type: ignore
            db.add(ProcessingLog(invoice_id=invoice_id,
                        step="TASK_ERROR", status="FAILED",
                        message=str(e)))
            db.commit()
        except Exception:
            pass
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()

_task_factory = cast(
    Callable[..., Callable[[Callable[..., str | None]], Task]],
    getattr(celery_app, "task"),
)
process_invoice_task: Task = _task_factory(
    bind=True,
    max_retries=10,
    name="app.workers.tasks.process_invoice_task",
)(_process_invoice_task)
