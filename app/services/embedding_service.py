from datetime import date, datetime, timedelta

from loguru import logger
from langchain_huggingface import HuggingFaceEmbeddings
from sqlalchemy.orm import Session
from app.models.invoice_model import Invoice

_DATE_FORMATS = (
    "%d %B %Y",
    "%d %b %Y",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%B %d, %Y",
)


def parse_invoice_date(value: str | None) -> date | None:
    if not value:
        return None
    text_value = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text_value, fmt).date()
        except ValueError:
            continue
    return None


def invoice_due_date(invoice: Invoice) -> date | None:
    parsed = parse_invoice_date(invoice.invoice_date)
    if parsed is None:
        return None
    terms = invoice.payment_terms if invoice.payment_terms is not None else 30
    return parsed + timedelta(days=int(terms))


def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        encode_kwargs={"normalize_embeddings": True}
    )


def build_invoice_text(invoice: Invoice) -> str:
    due_date = invoice_due_date(invoice)
    return (
       f"Invoice number: {invoice.invoice_number} "
        f"Vendor: {invoice.vendor_name} "
        f"Amount: {invoice.total_amount} "
        f"Currency: {invoice.currency} "
        f"Tax: {invoice.tax_amount} "
        f"Invoice date: {invoice.invoice_date} "
        f"Payment terms: {invoice.payment_terms} days "
        f"Due date: {due_date} "
        f"Status: {invoice.status}"
    )

def embed_invoice(db: Session, invoice: Invoice):
    try:
        text = build_invoice_text(invoice)
        vector = get_embeddings().embed_documents([text])  # pyright: ignore[reportCallIssue]
        invoice.embedding = vector[0]
        db.commit()
        logger.info(f"Embedded invoice {invoice.id} with vector {vector}")
    except Exception as e:
        logger.error(f"Error embedding invoice {invoice.id}: {e}")