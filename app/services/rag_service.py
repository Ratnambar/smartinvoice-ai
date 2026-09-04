from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.invoice_model import Invoice, InvoiceStatus
from app.services.embedding_service import get_embeddings, build_invoice_text, invoice_due_date
from rank_bm25 import BM25Okapi
from loguru import logger
from datetime import date


def get_overdue_invoices(db: Session) -> list[Invoice]:
    today = date.today()
    overdue: list[Invoice] = []
    invoices = db.query(Invoice).filter(Invoice.status != InvoiceStatus.FAILED).all()
    for inv in invoices:
        due = invoice_due_date(inv)
        if due is not None and due < today:
            overdue.append(inv)
    logger.info(f"Overdue lookup: {len(overdue)} invoices")
    return overdue


def reterive_similar_invoices(db: Session, question: str, top_k: int = 5) :
    question_embedding = get_embeddings().embed_query(question)
    results = db.execute(
        text("""
            SELECT id, 1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM invoices
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """),
        {"embedding": question_embedding, "limit": top_k}
    ).fetchall()
    invoice_ids = [row.id for row in results]
    invoices = db.query(Invoice).filter(Invoice.id.in_(invoice_ids)).all()
    logger.info(f"RAG: retrieved {len(invoices)} invoices for question: '{question}'")
    return invoices


def build_context_from_invoices(invoices: list[Invoice]) -> str:
    """Build context string to inject into LLM prompt"""
    if not invoices:
        return "No relevant invoices found."
    
    lines = []
    for inv in invoices:
        lines.append(
            f"- Invoice #{inv.invoice_number} | Vendor: {inv.vendor_name} "  # pyright: ignore[reportImplicitStringConcatenation]
            f"| Amount: INR {inv.total_amount} | Date: {inv.invoice_date} "
            f"| Status: {inv.status}"
        )
    return "\n".join(lines)


def hybrid_search(db: Session, question: str, top_k: int = 5):
    vector_results = reterive_similar_invoices(db, question, top_k=10)
    all_invoices = db.query(Invoice).all()
    corups = [build_invoice_text(inv) for inv in all_invoices]
    tokenized = [doc.lower().split() for doc in corups]
    bm25 = BM25Okapi(tokenized)
    scores = bm25.get_scores(question.lower().split())
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    bm25_results = [all_invoices[i] for i in top_indices]
    
    seen_ids = set()
    combined = []
    for inv in vector_results + bm25_results:
        if inv.id not in seen_ids:
            seen_ids.add(inv.id)
            combined.append(inv)
    
    return combined[:top_k]
