# 🧾 SmartInvoice AI

An AI-powered invoice processing and auditing system built with FastAPI and PostgreSQL. SmartInvoice AI automates invoice validation, detects anomalies, and provides a conversational RAG-based Q&A interface to query invoice data using natural language.

---

## 📌 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [AI Pipeline](#ai-pipeline)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Database Migrations](#database-migrations)
- [API Endpoints](#api-endpoints)
- [RAG System](#rag-system)
- [Validation Agent](#validation-agent)
- [Deployment](#deployment)
- [Contributing](#contributing)

---

## Overview

SmartInvoice AI solves a real finance team problem — manually reviewing hundreds of invoices for errors, duplicates, and vendor mismatches is slow and error-prone. This system automates the entire pipeline:

1. Upload a PDF invoice → AI extracts structured data
2. Validation Agent runs automated checks (vendor, amount, duplicate)
3. Summary Agent writes a professional audit report
4. Ask natural language questions about any invoice or vendor using the RAG chatbot

---

## Features

### Core
- 📄 **PDF Invoice Upload** — upload and parse invoice PDFs automatically
- 🏢 **Vendor Management** — full CRUD with unique name enforcement
- 🧾 **Invoice Management** — line items, tax, subtotal, total tracking
- 📊 **Status Tracking** — pending, cleared, flagged invoice lifecycle

### AI & Intelligence
- 🤖 **Validation Agent** — automated checks for vendor existence, amount mismatches, and duplicate invoice numbers
- 📝 **Summary Agent** — LLM-generated professional audit report for every invoice with a template-based fallback if LLM is unavailable
- 💬 **RAG Chatbot** — ask natural language questions about invoices and vendors
- 🔍 **Hybrid Search** — combines pgvector semantic search + BM25 keyword search for accurate retrieval
- 🗺️ **Smart Query Routing** — LangGraph agent routes to exact DB lookup, overdue check, or semantic RAG based on question type
- 📅 **Overdue Detection** — calculates overdue invoices dynamically using `invoice_date + payment_terms`

### Infrastructure
- 🗄️ **pgvector** — invoice embeddings stored directly in PostgreSQL, no separate vector DB needed
- 🔁 **Alembic Migrations** — full schema version control
- 📋 **Structured Logging** — Loguru-based logging throughout all agents

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client / API Consumer                     │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP
┌──────────────────────────────▼──────────────────────────────────┐
│                        FastAPI Application                       │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │   Invoice   │  │    Vendor    │  │      Chat Router       │ │
│  │   Router    │  │    Router    │  │   POST /chat/ask       │ │
│  └──────┬──────┘  └──────┬───────┘  └───────────┬────────────┘ │
│         │                │                        │              │
│  ┌──────▼────────────────▼────────┐  ┌───────────▼────────────┐ │
│  │         Business Logic         │  │     LangGraph Agent    │ │
│  │  • validate_file()             │  │  ┌─────────────────┐   │ │
│  │  • run_validation_agent()      │  │  │  router_node    │   │ │
│  │  • run_summary_agent()         │  │  │       │         │   │ │
│  │  • embed_invoice()             │  │  │  ┌────┴─────┐   │   │ │
│  └──────────────┬─────────────────┘  │  │  ▼    ▼    ▼   │   │ │
│                 │                    │  │exact rag overdue│   │ │
└─────────────────┼────────────────────┘  │  └────┬─────┘   │   │
                  │                       │  │generate_node  │   │
                  │                       │  └───────────────┘   │
                  │                       └───────────┬────────────┘
┌─────────────────▼───────────────────────────────────▼──────────┐
│                     PostgreSQL (AWS RDS)                         │
│                                                                  │
│   vendors  │  invoices  │  invoice_line_items  │  embeddings    │
│            │ (+ vector  │                      │  (pgvector)    │
│            │  column)   │                      │                │
└─────────────────────────────────────────────────────────────────┘
```

---

## AI Pipeline

### Invoice Processing Flow
```
PDF Upload
    │
    ▼
AI Extracts Fields (invoice_number, vendor_name, amounts, line items)
    │
    ▼
Validation Agent
    ├── Vendor Check    → is vendor in our system?
    ├── Amount Check    → do line items + tax = total?
    └── Duplicate Check → has this invoice_number been seen before?
    │
    ▼
Summary Agent → LLM writes audit report paragraph
    │
    ▼
Embedding Service → invoice text embedded + stored in pgvector
    │
    ▼
Invoice saved with status: CLEARED or FLAGGED
```

### RAG Chat Flow
```
User Question
    │
    ▼
Router Node (LangGraph)
    ├── INV-XXXX-XXX detected → Exact DB Lookup
    ├── "overdue/pending/unpaid" → Overdue Calculator
    └── General question       → Hybrid Search (BM25 + pgvector)
    │
    ▼
Context Built from Retrieved Invoices
    │
    ▼
Generate Node → HuggingFace LLM answers using context only
    │
    ▼
Answer returned to user
```

### Hybrid Search Detail
```
User Question
    ├── Vector Search  → embed question → cosine similarity in pgvector
    └── BM25 Search    → tokenize question → keyword match across invoices
    │
    ▼
Results merged + deduplicated → top K invoices returned
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **API Framework** | FastAPI |
| **Database** | PostgreSQL (AWS RDS) |
| **ORM** | SQLAlchemy |
| **Migrations** | Alembic |
| **Vector Store** | pgvector (PostgreSQL extension) |
| **LLM** | HuggingFace Inference API |
| **Embeddings** | HuggingFace Sentence Transformers |
| **AI Orchestration** | LangChain + LangGraph |
| **Keyword Search** | BM25 (rank_bm25) |
| **PDF Processing** | PyMuPDF / pdfplumber |
| **Logging** | Loguru |
| **Deployment** | AWS EC2 + RDS |
| **Process Manager** | Uvicorn / Gunicorn |

---

## Project Structure

```
smartinvoice-ai/
├── alembic/
│   ├── versions/              # migration files
│   └── env.py                 # alembic config (reads from .env)
├── app/
│   ├── core/
│   │   └── config.py          # settings, AI client setup
│   ├── models/
│   │   └── invoice_model.py   # Vendor, Invoice, InvoiceLineItem models
│   ├── routers/
│   │   ├── invoice_router.py  # invoice CRUD + upload endpoints
│   │   ├── vendor_router.py   # vendor CRUD endpoints
│   │   └── chat_router.py     # POST /chat/ask endpoint
│   ├── services/
│   │   ├── embedding_service.py  # embed invoices → pgvector
│   │   ├── rag_service.py        # hybrid search (BM25 + vector)
│   │   └── agent_service.py      # LangGraph agent with routing
│   ├── helper_func.py         # validation + summary agents
│   └── database.py            # DB engine, session, Base
├── alembic.ini
├── main.py
├── requirements.txt
└── .env.example
```

---

## Getting Started

### Prerequisites
- Python 3.10+
- PostgreSQL with pgvector extension
- HuggingFace API token (free at huggingface.co)

### Local Setup

```bash
# 1. Clone the repo
git clone https://github.com/your-username/smartinvoice-ai.git
cd smartinvoice-ai

# 2. Create and activate virtual environment
python -m venv env

# Windows
env\Scripts\activate
# Mac/Linux
source env/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your values

# 5. Enable pgvector on your PostgreSQL
psql -U postgres -d smartinvoice -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 6. Run database migrations
alembic upgrade head

# 7. Start the server
uvicorn main:app --reload
```

API docs available at: `http://localhost:8000/docs`

---

## Environment Variables

Create a `.env` file in the project root:

```env
# Database
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/smartinvoice

# HuggingFace
HUGGINGFACEHUB_API_TOKEN=hf_...

# LangSmith (optional — for tracing)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls-...
LANGCHAIN_PROJECT=smartinvoice-ai
```

---

## Database Migrations

```bash
# Create a new migration after model changes
alembic revision --autogenerate -m "describe your change"

# Apply all pending migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# Check current version
alembic current
```

---

## API Endpoints

### Vendors
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/vendors` | Create a vendor |

### Invoices
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/invoices` | List all invoices |
| `POST` | `/invoices/upload` | Upload PDF invoice (AI extraction + validation) |
| `POST` | `/invoices/{invoice_id}/process` | Process an Invoice |
| `GET` | `/invoices/{id}` | Get invoice by ID |
| `GET` | `/invoices/{invoice_id}/logs` | Get AI audit report |

### Chat (RAG)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/chat/ask` | Ask natural language question about invoices |

#### Chat Example
```bash
curl -X POST http://localhost:8000/chat/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Which invoices are overdue?"}'
```

```json
{
  "question": "Which invoices are overdue?",
  "answer": "There are 3 overdue invoices: INV-2025-003 from TestVendor3 (INR 12,000, overdue by 15 days), INV-2025-007 from ABC Supplies (INR 8,500, overdue by 4 days), INV-2025-011 from XYZ Corp (INR 22,000, overdue by 31 days)."
}
```

---

## RAG System

### How It Works

SmartInvoice uses a **Hybrid RAG** system combining semantic vector search with BM25 keyword search for accurate invoice retrieval.

**Embedding:** Every invoice is converted to a vector using HuggingFace Sentence Transformers and stored in PostgreSQL via pgvector.

**Hybrid Search:** When a question is asked, the system runs two searches in parallel — cosine similarity (pgvector) captures semantic meaning; BM25 captures exact keyword matches like invoice numbers or vendor names. Results are merged and deduplicated.

**Smart Routing:** A LangGraph agent inspects the question and routes it to the right handler:
- Invoice number detected (e.g., `INV-2025-005`) → direct DB lookup
- Keywords like "overdue", "unpaid", "due" → overdue calculator
- Everything else → hybrid semantic search

**Why Hybrid over pure vector search?** Pure vector search struggles with exact terms — asking for `INV-2025-005` might return semantically similar invoices instead of the exact one. BM25 handles exact matches; vectors handle meaning. Together they cover both cases.

### Re-embedding Invoices

If you update `build_invoice_text()`, re-embed all invoices:

```python
# Run once as a script
from app.services.embedding_service import embed_invoice
from app.database import SessionLocal
from app.models.invoice_model import Invoice

db = SessionLocal()
invoices = db.query(Invoice).all()
for invoice in invoices:
    embed_invoice(db, invoice)
print(f"Re-embedded {len(invoices)} invoices")
```

---

## Validation Agent

Every uploaded invoice runs through 3 automated checks:

| Check | What It Does | Failure Action |
|---|---|---|
| **Vendor Check** | Looks up vendor name in DB (case-insensitive) | Flags — vendor not in system |
| **Amount Check** | Verifies `line_items_sum + tax == total_amount` | Flags — amount mismatch with discrepancy value |
| **Duplicate Check** | Checks if `invoice_number` already exists | Flags — duplicate payment risk |

If any check fails, the invoice is marked `FLAGGED` and the Summary Agent writes an audit report detailing the issues. If the LLM is unavailable, a template-based fallback report is generated automatically.

---

## Deployment

### AWS Architecture
```
Internet
    │
    ▼
EC2 Instance (FastAPI + Uvicorn)
    │
    ▼
RDS PostgreSQL (private subnet, not publicly accessible)
```

### EC2 Setup

```bash
# SSH into EC2
ssh -i your-key.pem ubuntu@<EC2-PUBLIC-IP>

# Pull latest changes
cd smartinvoice-ai
git pull origin main

# Activate venv and install any new dependencies
source env/bin/activate
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Restart server
sudo systemctl restart smartinvoice
# or
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Security Notes
- RDS is in a **private subnet** — not publicly accessible from the internet
- Only EC2's Security Group is whitelisted on port 5432
- `.env` is never committed — use `.env.example` as template

---

## Contributing

```bash
# Pull latest main before starting
git checkout main
git pull origin main

# Create a feature branch
git checkout -b feature/your-feature-name

# Make changes, commit
git add .
git commit -m "feat: describe your change"

# Push and open a PR
git push origin feature/your-feature-name
```

- Always run `alembic upgrade head` after pulling if there are new migrations
- Never commit `.env` — only `.env.example`
- Test your endpoint in `/docs` before raising a PR

---

## What I Learned Building This

- Designing a **multi-agent AI pipeline** where different agents handle different concerns (validation, summarization, Q&A)
- Implementing **Hybrid RAG** (BM25 + pgvector) and understanding when pure vector search fails (exact lookups)
- Using **LangGraph** for conditional agent routing — routing to different handlers based on question type
- Production considerations: **fallback logic** when LLM is unavailable, **integrity error handling**, **race condition prevention** with `SELECT FOR UPDATE`
- AWS deployment with **security best practices** — RDS in private subnet, Security Group scoping EC2 → RDS only

---

<p align="center">Built with FastAPI · LangChain · LangGraph · PostgreSQL · pgvector · HuggingFace · AWS</p>