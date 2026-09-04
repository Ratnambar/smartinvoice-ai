import os
import re
from datetime import date
from typing import TypedDict

from langgraph.graph import StateGraph, END
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy.orm import Session
from app.models.invoice_model import Invoice
from app.services.rag_service import (
    reterive_similar_invoices,
    build_context_from_invoices,
    get_overdue_invoices,
)
from app.services.embedding_service import invoice_due_date
from loguru import logger


class ChatState(TypedDict):
    question: str
    context: str
    answer: str
    route: str
    db: object


def retrieve_node(state: ChatState):
    invoices = reterive_similar_invoices(state["db"], state["question"])
    state["context"] = build_context_from_invoices(invoices)
    logger.info(f"Agent: context built — {len(state['context'])} chars")
    return state


def get_invoice_by_number(db: Session, invoice_number: str):
    invoice = db.query(Invoice).filter(
        Invoice.invoice_number == invoice_number
    ).first()
    
    if not invoice:
        return f"No invoice found with number {invoice_number}"
    
    return (
        f"Invoice Number: {invoice.invoice_number}\n"
        f"Vendor Name: {invoice.vendor_name}\n"
        f"Currency: {invoice.currency}\n"
        f"Tax Amount: {invoice.tax_amount}\n"
        f"Subtotal: {invoice.subtotal}\n"
        f"Total Amount: {invoice.total_amount}\n"
        f"Status: {invoice.status}"
    )


def exact_lookup_node(state: ChatState) -> ChatState:
    match = re.search(r"INV-\d{4}-\d+", state["question"])
    if not match:
        state["context"] = "No invoice number found in the question."
        return state
    state["context"] = get_invoice_by_number(state["db"], match.group())
    return state


def get_overdue_invoices_tool(state: ChatState) -> ChatState:
    invoices = get_overdue_invoices(state["db"])
    
    if not invoices:
        state["context"] = "No overdue invoices found."
        return state

    lines = []
    for inv in invoices:
        due = invoice_due_date(inv)
        if due is None:
            continue
        days_overdue = (date.today() - due).days
        lines.append(
            f"Invoice #{inv.invoice_number} | Vendor: {inv.vendor_name} "
            f"| Amount: INR {inv.total_amount} "
            f"| Due: {due} | Overdue by {days_overdue} days"
        )
    
    state["context"] = "\n".join(lines) if lines else "No overdue invoices found."
    return state


def router_node(state: ChatState) -> ChatState:
    q = state["question"].lower()
    
    if re.search(r"INV-\d{4}-\d+", state["question"]):
        state["route"] = "exact"
    elif any(word in q for word in ["overdue", "pending", "unpaid", "due"]):
        state["route"] = "overdue"
    else:
        state["route"] = "semantic"
    return state


def route_decision(state: ChatState) -> str:
    return state["route"]


def generate_node(state: ChatState):
    endpoint = HuggingFaceEndpoint(
    repo_id="meta-llama/Llama-3.1-8B-Instruct",
            huggingfacehub_api_token=os.getenv("HF_TOKEN"),
            temperature=0.1,
            max_new_tokens=300,
    )
    llm = ChatHuggingFace(llm=endpoint)
    prompt = ChatPromptTemplate.from_template("""
        You are a smart invoice assistant for a finance team.
        Answer the user's question using ONLY the invoice data below.
        If the answer is not in the data, say "I don't have enough data to answer that."
        Be concise and factual.

        Invoice Data:
        {context}

        Question: {question}
        Answer:
    """)
    chain = prompt | llm
    response = chain.invoke({
        "context": state["context"],
        "question": state["question"]
    })
    state["answer"] = response.content
    logger.info(f"Agent context:\n{state['context']}")
    return state


def build_chat_graph():
    graph = StateGraph(ChatState)
    graph.add_node("router", router_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("exact_lookup", exact_lookup_node)
    graph.add_node("overdue_lookup", get_overdue_invoices_tool)
    graph.add_node("generate", generate_node)

    graph.set_entry_point("router")
    graph.add_conditional_edges(
        "router",
        route_decision,
        {
            "exact": "exact_lookup",
            "overdue": "overdue_lookup",
            "semantic": "retrieve",
        },
    )
    graph.add_edge("exact_lookup", "generate")
    graph.add_edge("overdue_lookup", "generate")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


chat_graph = build_chat_graph()


def ask_invoice_question(db: Session, question: str) -> str:
    result = chat_graph.invoke({
        "question": question,
        "context": "",
        "answer": "",
        "route": "",
        "db": db
    })
    return result["answer"]
