from sqlalchemy.orm import Session
from sqlalchemy import func, select, label
from fastapi import UploadFile
from fastapi import HTTPException, status
from app.models.invoice_model import InvoiceLineItem, Vendor, Invoice
from loguru import logger

MAX_FILE_SIZE_IN_BYTES = 10 * 1024 * 1024

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


def validate_vendor(db, vendor_name):
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
        "vendor_id": vendor.id,
        "message": f"Vendor with id {vendor.id} found."
    }

def validate_line_items(db, invoice):
    stmt = select(  # pyright: ignore[reportUnknownVariableType]
        InvoiceLineItem.invoice_id,
        func.sum(InvoiceLineItem.total_price).label('total_price')  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
    ).group_by(InvoiceLineItem.invoice_id)
    rows = db.execute(stmt).all()  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
    total_price = 0
    total_price = [row[1] for row in rows if row[0] == invoice.id][0]
    if invoice.total_amount - total_price == 0:
        return {
            "passed": True,
            "message": f"Inline Items {total_price} is matching with Invoice {invoice.total_amount}. Verified."
        }
    else:
        return {
            "passed": False,
            "message": f"MISMATCH: Line items sum to INR {total_price:,.2f} "
                       f"but invoice total states INR {invoice.total_amount:,.2f}. "
                       f"Discrepancy of INR {abs(invoice.total_amount - total_price):,.2f}. "
                       f"Do not process payment until resolved.",
        }

def check_duplicate(invoice, db):
    if not invoice.invoice_number: # pyright: ignore[reportGeneralTypeIssues]
        return {
            "passed":  True,   # can't check without a number — give benefit of doubt
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
    

def run_validation_agent(db, invoice):
    logger.info(f"Validation Agent: starting checks for invoice {invoice.id}")

    vendor_result = validate_vendor(db, invoice.vendor_name)
    line_item_result = validate_line_items(db, invoice)
    invoice_duplication_check = check_duplicate(invoice, db)
    flags = []
    if not vendor_result["passed"]:
        flags.append(vendor_result["message"])
    if not line_item_result["passed"]:
        flags.append(line_item_result["message"])
    if not invoice_duplication_check["passed"]:
        flags.append(invoice_duplication_check["message"])
    all_flags = 0
    all_passed = len(flags)
    logger.info(
        f"Validation Agent: invoice={invoice.id} "
        f"vendor={'OK' if vendor_result['passed'] else 'FAIL'} "
        f"total={'OK' if line_item_result['passed'] else 'FAIL'} "
        f"duplicate={'OK' if invoice_duplication_check['passed'] else 'FAIL'} "
        f"result={'PASSED' if all_passed else 'FLAGGED'}"
    )

    return {
        "all_passed": all_passed,
        "checks": {
            "vendor":     vendor_result,
            "total":      line_item_result,
            "duplicate":  invoice_duplication_check,
        },
        "vendor_id": vendor_result["vendor_id"],
        "flags": flags
    }