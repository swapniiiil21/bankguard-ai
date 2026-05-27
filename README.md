---
title: BankGuard AI
emoji: 🛡️
colorFrom: blue
colorTo: red
sdk: docker
app_port: 7860
---
# BankGuard AI 🛡️

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)
![LangGraph](https://img.shields.io/badge/LangGraph-0.1-blueviolet)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35-FF4B4B?logo=streamlit)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)
![License](https://img.shields.io/badge/License-MIT-green)

> **Intelligent Multi-Agent Fraud Detection System for Banks**  
> Powered by LangGraph · Groq Llama 3 · Pinecone · Isolation Forest · FastAPI · Streamlit

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        BankGuard AI — Agent Pipeline                     │
│                                                                           │
│  [Case Input]                                                             │
│       │                                                                   │
│       ▼                                                                   │
│  ┌─────────────┐                                                          │
│  │ Orchestrator│  ← Validates inputs, assigns case_id, inits state       │
│  └──────┬──────┘                                                          │
│         │                                                                 │
│         ▼                                                                 │
│  ┌─────────────┐                                                          │
│  │  OCR Agent  │  ← Tesseract (primary) + AWS Textract (fallback)        │
│  └──────┬──────┘                                                          │
│         │ fan-out (parallel)                                              │
│    ┌────┴─────┬──────────────┐                                            │
│    ▼          ▼              ▼                                            │
│ ┌──────┐ ┌────────┐ ┌──────────┐                                         │
│ │ KYC  │ │  Txn   │ │  Loan    │  ← All run in parallel                  │
│ │Agent │ │ Agent  │ │  Agent   │                                          │
│ └──┬───┘ └───┬────┘ └────┬─────┘                                         │
│    └─────────┴───────────┘                                                │
│                   │ fan-in                                                │
│                   ▼                                                       │
│          ┌─────────────────┐                                              │
│          │ CrossReference  │  ← Pinecone vector search + field matching   │
│          │     Agent       │                                              │
│          └────────┬────────┘                                              │
│                   ▼                                                       │
│          ┌─────────────────┐                                              │
│          │  Risk Scoring & │  ← Weighted score (0-100) + LLM report      │
│          │  Report Agent   │                                              │
│          └────────┬────────┘                                              │
│                   │                                                       │
│          ┌────────┴────────┐                                              │
│          │ score < 70?     │                                              │
│          └────┬───────┬────┘                                              │
│            Yes│    No │                                                   │
│               ▼       ▼                                                   │
│             [END]  [Human                                                 │
│                    Review] ─────► [END]                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Features

| Domain | Detection Capability |
|--------|---------------------|
| **KYC / Document Fraud** | Font inconsistency, ID format checks, DOB/Name mismatches, tampering signals via LLM |
| **Transaction Fraud** | Isolation Forest anomaly detection, structuring (just-below ₹1L), velocity fraud, geo-anomalies |
| **Loan Application Fraud** | Income vs bank credit mismatch, employer MCA registry check, LLM semantic inconsistency |
| **Cross-Reference** | Pinecone vector similarity against past fraud cases, field-level cross-document matching |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Agent Orchestration** | Hierarchical LangGraph (Supervisor/Workers) |
| **LLM** | Groq (Llama 3 70B) + LangSmith Observability |
| **Stream Processing** | Apache Kafka + Celery/Faust |
| **ML Anomaly Detection** | scikit-learn IsolationForest |
| **Vector Memory** | Pinecone + Hybrid Search (Agentic RAG) |
| **Episodic Memory** | Redis (State management) |
| **Graph Intelligence**| Neo4j (Fraud ring detection) |
| **Database** | PostgreSQL (Immutable audit trails) |
| **Backend API** | FastAPI + OAuth2 + Kong Gateway |
| **Frontend** | Next.js + Tailwind + Cytoscape.js |
| **DevOps & K8s** | Kubernetes, ArgoCD, Docker Compose |

---

## Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/yourname/bankguard-ai.git
cd bankguard-ai
cp .env.example .env
# Edit .env with your API keys
```

### 2. Run with Docker Compose

```bash
docker-compose up --build
```

| Service | URL |
|---------|-----|
| Streamlit UI | http://localhost:8501 |
| FastAPI Docs | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |

### 3. Run Locally (without Docker)

```bash
pip install -r requirements.txt
# Terminal 1 — API
python -m uvicorn api.main:app --reload --port 8000
# Terminal 2 — UI
streamlit run ui/app.py
```

---

## API Documentation

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload KYC docs + transaction CSV |
| `POST` | `/api/analyze` | Trigger fraud analysis, get full report |
| `GET` | `/api/cases` | List all past cases (paginated) |
| `GET` | `/api/cases/{id}` | Get specific case report |
| `POST` | `/api/cases/{id}/approve` | Human-in-the-loop approval |
| `GET` | `/api/health` | Health check |

### Example: Upload + Analyze

```bash
# Upload documents
CASE_ID=$(curl -s -X POST http://localhost:8000/api/upload \
  -F "aadhaar=@data/sample_docs/aadhaar.jpg" \
  -F "transactions_csv=@data/sample_transactions.csv" \
  | jq -r '.case_id')

# Trigger analysis
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d "{
    \"case_id\": \"$CASE_ID\",
    \"loan_form\": {
      \"name\": \"Rajesh Kumar Singh\",
      \"dob\": \"15/08/1985\",
      \"employer\": \"Infosys Limited\",
      \"income\": 75000,
      \"loan_amount\": 500000
    }
  }"
```

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | Groq LLM API key | ✅ |
| `PINECONE_API_KEY` | Pinecone vector store key | ✅ |
| `PINECONE_ENV` | Pinecone environment | ✅ |
| `PINECONE_INDEX` | Pinecone index name | ✅ |
| `AWS_ACCESS_KEY_ID` | AWS key (Textract fallback) | Optional |
| `AWS_SECRET_ACCESS_KEY` | AWS secret | Optional |
| `MONGO_URI` | MongoDB connection string | ✅ |
| `FRAUD_SCORE_THRESHOLD` | Score above which human review is required (default: 70) | Optional |

---

## Fraud Score Interpretation

| Score Range | Risk Level | Recommendation |
|-------------|-----------|----------------|
| 0 – 35 | 🟢 Low | **Approve** |
| 36 – 69 | 🟡 Medium | **Review** |
| 70 – 100 | 🔴 High | **Reject & Escalate** |

### Score Weights

| Domain | Weight |
|--------|--------|
| KYC / Document Fraud | 30% |
| Transaction Fraud | 35% |
| Loan Document Fraud | 20% |
| Cross-Reference | 15% |

---

## CI/CD Pipeline

```
Push to any branch → [Test] → pytest (3 test files, 20+ tests)
Push to main       → [Build] → Docker image built & pushed to Docker Hub
                  → [Deploy] → SSH into EC2, pull image, restart containers
```

**GitHub Secrets required:**

| Secret | Purpose |
|--------|---------|
| `DOCKER_USERNAME` | Docker Hub username |
| `DOCKER_PASSWORD` | Docker Hub access token |
| `EC2_HOST` | EC2 public IP / domain |
| `EC2_USER` | SSH username (e.g., `ubuntu`) |
| `EC2_SSH_KEY` | Private SSH key (PEM format) |

---

## Enterprise Project Structure

```
bankguard-ai/
├── k8s/                        # Kubernetes manifests & Helm charts
├── src/
│   ├── api/                    # FastAPI Gateway, auth, and routes
│   ├── agents/                 # LangGraph Nodes & specialized Agents
│   ├── core/                   # Security (Vault), Config, DB Connections
│   ├── events/                 # Kafka Producers & Consumers
│   ├── graph_db/               # Neo4j Cypher queries & models
│   ├── memory/                 # Vector, Redis, and Postgres handlers
│   └── tools/                  # Custom tools (OCR, Agentic RAG, etc.)
├── ui/                         # Next.js Enterprise Frontend
├── tests/                      # Pytest, DeepEval, Ragas frameworks
├── docker-compose.prod.yml     # Scalable distributed infrastructure
├── skaffold.yaml               # K8s local dev config
└── .env.example
```

---

## Screenshots

> _Run `docker-compose up` and visit http://localhost:8501_

| Case Submission | Investigation Dashboard | Case History |
|----------------|------------------------|--------------|
| Upload KYC docs + CSV | Gauge + Agent tracker + Risk cards | Searchable table of past cases |

---

## Running Tests

```bash
pytest tests/ -v --tb=short
```

---

## Enterprise Roadmap (Currently in Implementation)

- [x] **Agentic Orchestration** — Hierarchical Supervisor state machine
- [x] **Event-Driven Architecture** — Kafka integration for real-time transactions
- [x] **Graph Analytics** — Neo4j for synthetic identity and fraud ring detection
- [x] **Enterprise Memory** — Redis checkpointer + PostgreSQL audit logs
- [ ] **Next.js Frontend** — Live heatmaps and interactive Cytoscape.js graphs
- [ ] **AI Observability** — LangSmith tracing and OpenTelemetry
- [ ] **Cloud-Native Deployment** — Kubernetes (EKS) and HashiCorp Vault
- [ ] **Multi-language OCR** — Hindi, Tamil, Telugu document support

---

## License

MIT © 2024 BankGuard AI
