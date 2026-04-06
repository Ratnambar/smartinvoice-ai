from sqlalchemy.orm import Session
from fastapi import UploadFile
from fastapi import HTTPException, status
from app.models.invoice_model import Vendor

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