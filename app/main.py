from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.routes.auth import router as auth_router
from app.api.routes.invoice import router as invoice_router, get_invoice
# from app.agents.agent_validation import router as agent_validation_router

app = FastAPI()
from app.core.config import engine, Base


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
from app.models.invoice_model import User, Invoice, Vendor  # ← must import models so Base knows about them

def create_tables():
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")
app.include_router(auth_router)
app.include_router(invoice_router)
# app.include_router(agent_validation_router)
create_tables()