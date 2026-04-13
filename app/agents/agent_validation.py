from app.core.app_security import get_current_user
from typing import Annotated
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from app.core.config import get_db
from app.models.invoice_model import Invoice, InvoiceLineItem, InvoiceStatus, ProcessingLog, User
from app.schemas.invoice_schema import InvoiceResponse
from app.helper.helper_func import run_validation_agent

router = APIRouter(prefix="/agent", tags=["Agent Validation"])



@router.post("/validate", status_code=status.HTTP_200_OK, summary="Validate the invoice")
async def agent_validate_invoice(db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],  # pyright: ignore[reportUnusedParameter]
    invoice_id: int
):
    invoice = db.query(Invoice).filter(Invoice.id==invoice_id).first()
    agent_validated_data = run_validation_agent(db, invoice) # pyright: ignore[reportArgumentType]
    return agent_validated_data
