from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.routes.auth import router as auth_router
from app.api.routes.invoice import router as invoice_router
from app.api.routes.chat_router import router_chat
from app.core.config import Base, SessionLocal, engine
from app.models.invoice_model import Invoice, User, Vendor  # noqa: F401 — register models
from app.services.embedding_service import embed_invoice

app = FastAPI()


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def create_tables():
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")


# def re_embed_all_invoices() -> None:
#     """One-off helper: open a real Session (do not use get_db() here)."""
#     db = SessionLocal()
#     try:
#         invoices = db.query(Invoice).all()
#         for invoice in invoices:
#             embed_invoice(db, invoice)
#         print(f"Re-embedded {len(invoices)} invoices")
#     finally:
#         db.close()


app.include_router(auth_router)
app.include_router(invoice_router)
app.include_router(router_chat)

# re_embed_all_invoices()
# create_tables()
# Run once manually when needed:
#   python -c "from app.main import re_embed_all_invoices; re_embed_all_invoices()"
# Do NOT call re_embed_all_invoices() at import time — it breaks uvicorn reload.
