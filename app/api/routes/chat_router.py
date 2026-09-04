from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.config import get_db
from app.services.agent_service import ask_invoice_question

router_chat = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    question: str
    answer: str


@router_chat.post("/ask", response_model=ChatResponse)
def ask(request: ChatRequest, db: Session = Depends(get_db)):
    answer = ask_invoice_question(db, request.question)
    return {"question": request.question, "answer": answer}