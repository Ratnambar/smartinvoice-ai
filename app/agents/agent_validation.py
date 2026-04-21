# from app.core.app_security import get_current_user
# from typing import Annotated
# from sqlalchemy.orm import Session
# from fastapi import APIRouter, Depends, status
# from app.core.config import get_db
# from app.models.invoice_model import Invoice, InvoiceStatus, ProcessingLog, User
# from app.helper.helper_func import run_validation_agent, run_summary_agent

# router = APIRouter(prefix="/agent", tags=["Agent Validation"])


# @router.post("/validate", status_code=status.HTTP_200_OK, summary="Validate the invoice")
# async def agent_validate_invoice(db: Annotated[Session, Depends(get_db)],
#     current_user: Annotated[User, Depends(get_current_user)],  # pyright: ignore[reportUnusedParameter]
#     invoice_id: int
# ):
#     invoice = db.query(Invoice).filter(Invoice.id==invoice_id).first()
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
#     return anomaly_report
