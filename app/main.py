from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.invoice import router as invoice_router

app = FastAPI()
from app.core.config import engine, Base
from app.models.invoice_model import User  # ← must import models so Base knows about them

def create_tables():
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")
app.include_router(auth_router)
app.include_router(invoice_router)
create_tables()