from typing import TypedDict, cast
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from fastapi import UploadFile
from fastapi import HTTPException, status
from app.models.invoice_model import InvoiceLineItem, Vendor, Invoice
from app.core.config import get_ai_response
from langchain_core.prompts import PromptTemplate
from loguru import logger

MAX_FILE_SIZE_IN_BYTES = 10 * 1024 * 1024


class VendorCheckResult(TypedDict):
    passed: bool
    vendor_id: int | None
    message: str


class AmountCheckResult(TypedDict):
    passed: bool
    message: str


class DuplicateCheckResult(TypedDict):
    passed: bool
    message: str


class ValidationChecks(TypedDict):
    vendor: VendorCheckResult
    total: AmountCheckResult
    duplicate: DuplicateCheckResult


class ValidationAgentResult(TypedDict):
    all_failed: int
    checks: ValidationChecks
    invoice_id: int
    vendor_id: int | None
    vendor_name: str | None
    flags: list[str]


def validate_file(db: Session, vendor_id: int, file: UploadFile):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Vendor with id {vendor_id} not found.")
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file must have a filename.")
    if not file.headers.get("content-type") == "application/pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be a PDF.")
    if file.size is not None and file.size > MAX_FILE_SIZE_IN_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="File size exceeds the maximum allowed size of 10MB.")
    return file


def validate_vendor(db: Session, vendor_name: str | None) -> VendorCheckResult:
    if not vendor_name:
        return {
            "passed": False,
            "vendor_id": None,
            "message": "Vendor name is required."
        }
    vendor = db.query(Vendor).filter(Vendor.name.ilike(f"{vendor_name}")).first()
    if not vendor:
        return {
            "passed": False,
            "vendor_id": None,
            "message": f"Vendor with name {vendor_name} not found."
        }
    return {
        "passed": True,
        "vendor_id": cast(int, cast(object, vendor.id)),
        "message": f"Vendor with id {vendor.id} found."
    }


def validate_line_items(db: Session, invoice: Invoice) -> AmountCheckResult:
    stmt = select(  # pyright: ignore[reportUnknownVariableType]
        func.sum(InvoiceLineItem.total_price).label('total_price')  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
    ).where(InvoiceLineItem.invoice_id == invoice.id)
    
    result = db.execute(stmt).scalar()
    total_price = float(result) if result is not None else 0.0

    if invoice.total_amount - (invoice.tax_amount + total_price) == 0:
        return {
            "passed": True,
            "message": f"Inline Items {total_price + invoice.tax_amount} is matching with Invoice {invoice.total_amount}. Verified."
        }
    else:
        return {
            "passed": False,
            "message": f"MISMATCH: Line items sum to INR {(total_price + invoice.tax_amount):,.2f} "
                       f"but invoice total states INR {invoice.total_amount:,.2f}. "
                       f"Discrepancy of INR {abs(invoice.total_amount - (invoice.tax_amount + total_price)):,.2f}. "
                       f"Do not process payment until resolved.",
        }


def check_duplicate(invoice: Invoice, db: Session) -> DuplicateCheckResult:
    if not invoice.invoice_number: # pyright: ignore[reportGeneralTypeIssues]
        return {
            "passed":  False,   # can't check without a number — give benefit of doubt
            "message": "Invoice number not found — duplicate check skipped.",
        }
    duplicate_invoice = db.query(Invoice).filter(Invoice.invoice_number==invoice.invoice_number,
                                       Invoice.id!=invoice.id).first()
    if duplicate_invoice:
        return {
            "passed":  False,
            "message": f"DUPLICATE: Invoice number '{invoice.invoice_number}' already exists "
                       f"in the system (Invoice ID: {duplicate_invoice.id}, "
                       f"uploaded on {duplicate_invoice.uploaded_at.strftime('%d %b %Y')}). "
                       f"Possible duplicate payment risk.",
        }
    else:
        return {
            "passed": True,
            "message": f"Invoice number '{invoice.invoice_number}' is unique. No duplicates found.",
        }   


def run_validation_agent(db: Session, invoice: Invoice) -> ValidationAgentResult:
    logger.info(f"Validation Agent: starting checks for invoice {invoice.id}")
    vendor_result = validate_vendor(db, cast(str | None, cast(object, invoice.vendor_name)))
    line_item_result = validate_line_items(db, invoice)
    invoice_duplication_check = check_duplicate(invoice, db)
    flags: list[str] = []
    all_failed = 0
    if not vendor_result["passed"]:
        flags.append(vendor_result["message"])
        all_failed+=1
    if not line_item_result["passed"]:
        flags.append(line_item_result["message"])
        all_failed+=1
    if not invoice_duplication_check["passed"]:
        flags.append(invoice_duplication_check["message"])
        all_failed+=1
    logger.info(
        f"Validation Agent: invoice={invoice.id} "
        f"vendor={'OK' if vendor_result['passed'] else 'FAIL'} "
        f"total={'OK' if line_item_result['passed'] else 'FAIL'} "
        f"duplicate={'OK' if invoice_duplication_check['passed'] else 'FAIL'} "
        f"result={'PASSED' if not all_failed else 'FLAGGED'}"
    )

    return cast(
        ValidationAgentResult,
        cast(
            object,
            {
                "all_failed": all_failed,
                "checks": {
                    "vendor": vendor_result,
                    "total": line_item_result,
                    "duplicate": invoice_duplication_check,
                },
                "invoice_id": invoice.id,
                "vendor_id": vendor_result["vendor_id"],
                "vendor_name": invoice.vendor_name,
                "flags": flags,
            },
        ),
    )


def build_invoice_data_string(invoice):
    return (
        f"Invoice Number: {invoice.invoice_number or 'Not found'}\n"
        f"Vendor Name: {invoice.vendor_name or 'Not found'}\n"
        f"Invoice Date: {invoice.invoice_date or 'Not found'}\n"
        f"Subtotal: INR {invoice.subtotal:,.2f}" if invoice.subtotal else "Subtotal: Not found\n"
        f"Tax Amount: INR {invoice.tax_amount:,.2f}" if invoice.tax_amount else "Tax Amount: Not found\n"
        f"Total Amount: INR {invoice.total_amount:,.2f}" if invoice.total_amount else "Total Amount: Not found\n"
        f"Currency: {invoice.currency or 'INR'}\n"
        f"Line Items Count: {len(invoice.line_items)}"
    )


def build_validation_string(validation_result: ValidationAgentResult) -> str:
    checks = validation_result.get("checks", {})
    vendor_check = checks.get("vendor", {})
    lines = []
    lines.append(
        f"Vendor Check - {'Passes' if vendor_check.get('passed') else 'Failed'}"
        f" - {vendor_check.get('message', '')}"
    )

    total_check = checks.get("total", {})
    lines.append(
        f"Total Amount Check: {'PASSED' if total_check.get('passed') else 'FAILED'} "
        f"— {total_check.get('message', '')}"
    )

    duplicate_check = checks.get("duplicate", {})
    lines.append(
        f"Duplicate Check: {'PASSED' if duplicate_check.get('passed') else 'FAILED'} "
        f"— {duplicate_check.get('message', '')}"
    )

    flags = validation_result.get("flags", [])

    if flags:
        lines.append(f"Total Issues Found: {len(flags)}")
    else:
        lines.append("No issues found. All checks passed.")
    return "\n".join(lines)


def run_summary_agent(invoice: Invoice, validation_result: ValidationAgentResult) -> str | None:
    invoice_data_str = build_invoice_data_string(invoice)
    validation_str   = build_validation_string(validation_result)
    status_str       = "FLAGGED — requires manual review" if validation_result["all_failed"] else "CLEARED — approved for payment"
    
    # You are a professional accounts assistant writing an invoice audit report.
    #         Write a clear, concise paragraph (4-6 sentences) summarising this invoice
    #         and its validation results. Be factual and professional.
    
    
    SUMMARY_PROMPT = PromptTemplate(
        input_variables=["invoice_data", "validation_summary", "status"],
        template="""
            You are a professional accounts assistant writing an invoice audit report.
            Write a clear, concise paragraph (4-6 sentences) summarising this invoice
            and its validation results. Be factual and professional.
            Return ONLY the paragraph — no headings, no bullet points, no extra text.

            Invoice details:
            {invoice_data}

            Validation results:
            {validation_summary}

            Overall status: {status}

            Write the audit report paragraph:
            """
            )
    prompt = SUMMARY_PROMPT.format(
            invoice_data        = invoice_data_str,
            validation_summary  = validation_str,
            status              = status_str,
        )
    # Remove any accidental prompt echo from the LLM response
    # Some models repeat the last line of the prompt before answering
    try:
        response = get_ai_response(prompt)
        logger.info(f"Summary Agent: generating report for invoice {invoice.id}...")
        if response: # pyright: ignore[reportOperatorIssue]
            response = response.strip()
            logger.info(f"Summary Agent: report generated ({len(response)} chars)")
            return response
    except Exception as e:
        # Fallback — template-based report if LLM fails
        # This ensures invoice.anomaly_report is never left empty
        logger.error(f"Summary Agent: LLM failed — using template fallback. Error: {e}")
        return fallback_report(invoice, validation_result)
    

def fallback_report(invoice: Invoice, validation_result: ValidationAgentResult) -> str:
    """
    Template-based fallback report used when LLM API is unavailable.
    No AI — just Python string formatting.
    Ensures anomaly_report is always filled even if HuggingFace is down.
    """
    flags  = validation_result.get("flags", [])
    status = "flagged for manual review" if flags else "cleared for payment"
    report = (
        f"Invoice {invoice.invoice_number or 'N/A'} from "
        f"{invoice.vendor_name or 'unknown vendor'} "
        f"dated {invoice.invoice_date or 'unknown date'} "
        f"for INR {invoice.total_amount:,.2f} has been processed and {status}. "
    )
    if flags:
        report += f"{len(flags)} issue(s) detected: "
        report += " | ".join(flags)
    else:
        report += "All validation checks passed. Vendor verified, amounts balanced, no duplicates found."
    return report