# SmartInvoice AI

> Intelligent Invoice Processing API — upload invoice PDFs and let
> AI agents extract, validate, and summarise them automatically.

🔗 **Live URL:** http://35.171.22.208:8000/docs
---

## What it does

Upload any invoice PDF → 4-step AI pipeline runs automatically:

| Step | Technology | What happens |
|---|---|---|
| PDF Extraction | pdfplumber | Raw text extracted from PDF |
| Extraction Agent | LangChain + Mistral-7B | LLM extracts vendor, total, line items |
| Validation Agent | Python + PostgreSQL | Checks vendor, amounts, duplicates |
| Summary Agent | LangChain + Mistral-7B | LLM writes plain-English audit report |

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI |
| AI Orchestration | LangChain Agents |
| LLM | Mistral-7B-Instruct via HuggingFace |
| Database | PostgreSQL + SQLAlchemy |
| Background Jobs | Celery + Redis |
| Auth | JWT (python-jose + bcrypt) |
| PDF Extraction | pdfplumber |
| Testing | Pytest |
| Deployment | Railway (API + DB + Redis + Worker) |
| Containers | Docker + docker-compose |

---

## Quick Start

```bash
git clone https://github.com/Ratnambar/smartinvoice-ai.git
cd smartinvoice-ai
cp .env.example .env
docker-compose up --build
# API running at http://localhost:8000/docs
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Register user |
| POST | `/api/v1/auth/login` | Get JWT token |
| POST | `/api/v1/invoices/upload` | Upload invoice PDF |
| POST | `/api/v1/invoices/{id}/process` | Trigger AI processing |
| GET | `/api/v1/invoices/{id}` | Get invoice + results |
| GET | `/api/v1/invoices/{id}/logs` | Processing audit trail |
| POST | `/api/v1/vendors/` | Add vendor to master list |

---

## Run Tests

```bash
pytest tests/ -v
```