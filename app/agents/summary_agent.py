from fastapi import APIRouter, status, Depends
from typing import Annotated
from app.core.config import get_db, get_ai_response
from sqlalchemy.orm import Session
from app.models.invoice_model import Invoice


router = APIRouter(prefix="/summary", tags=["Summery"])

@router.post("/{invoice_id}/summary", status_code=status.HTTP_201_CREATED, summary="Summary of Invoice")
async def summary(
    db: Annotated[Session, Depends(get_db)],
    invoice_id : int):
    invoice = db.query(Invoice).filter(Invoice.id==invoice_id).first()
    anomaly_report = run_summary_agent(invoice, validation_result)
    return anomaly_report
